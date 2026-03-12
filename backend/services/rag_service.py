"""
RAG Service - Document Processing, FAISS Indexing, and Retrieval
"""

import os
import re
import json
import logging
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.config import settings
from backend.models.models import Document, Embedding
from backend.services.llm_service import ollama_service

logger = logging.getLogger(__name__)

# Attempt to import FAISS - graceful degradation if not installed
try:
    import faiss
    FAISS_AVAILABLE = True
    logger.info("✅ FAISS loaded successfully")
except ImportError:
    FAISS_AVAILABLE = False
    logger.warning("⚠️  FAISS not installed - RAG features disabled. Install: pip install faiss-cpu")

# Attempt to import PDF/text extraction libraries
try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    from docx import Document as DocxDocument
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False


class FAISSIndexManager:
    def __init__(self, index_path: str):
        self.index_path = Path(index_path)
        self.index_path.mkdir(parents=True, exist_ok=True)
        self._indexes: dict = {}  # In-memory cache of loaded indexes

    def _get_index_file(self, index_id: str) -> Path:
        return self.index_path / f"{index_id}.faiss"

    def _get_meta_file(self, index_id: str) -> Path:
        return self.index_path / f"{index_id}_meta.json"

    def create_or_load_index(self, index_id: str, dimension: int = 768) -> Optional[object]:
        if not FAISS_AVAILABLE:
            return None

        if index_id in self._indexes:
            return self._indexes[index_id]

        index_file = self._get_index_file(index_id)
        if index_file.exists():
            index = faiss.read_index(str(index_file))
            logger.info(f"Loaded FAISS index: {index_id} ({index.ntotal} vectors)")
        else:
            # Inner product index with normalization (cosine similarity)
            index = faiss.IndexFlatIP(dimension)
            logger.info(f"Created new FAISS index: {index_id} dim={dimension}")

        self._indexes[index_id] = index
        return index

    def save_index(self, index_id: str) -> bool:
        if not FAISS_AVAILABLE or index_id not in self._indexes:
            return False
        try:
            faiss.write_index(self._indexes[index_id], str(self._get_index_file(index_id)))
            return True
        except Exception as e:
            logger.error(f"Failed to save index {index_id}: {e}")
            return False

    def add_vectors(self, index_id: str, vectors: np.ndarray) -> List[int]:
        if not FAISS_AVAILABLE:
            return []
        index = self._indexes.get(index_id)
        if index is None:
            return []

        start_id = index.ntotal
        # Normalize vectors for cosine similarity
        faiss.normalize_L2(vectors)
        index.add(vectors)
        ids = list(range(start_id, index.ntotal))
        self.save_index(index_id)
        return ids

    def search(self, index_id: str, query_vector: np.ndarray, top_k: int = 5) -> List[Tuple[int, float]]:
        if not FAISS_AVAILABLE:
            return []
        index = self._indexes.get(index_id)
        if index is None or index.ntotal == 0:
            return []

        faiss.normalize_L2(query_vector)
        scores, ids = index.search(query_vector, min(top_k, index.ntotal))
        return [(int(i), float(s)) for i, s in zip(ids[0], scores[0]) if i >= 0]

    def delete_index(self, index_id: str):
        """Remove an index entirely."""
        self._indexes.pop(index_id, None)
        for f in [self._get_index_file(index_id), self._get_meta_file(index_id)]:
            if f.exists():
                f.unlink()


faiss_manager = FAISSIndexManager(settings.FAISS_INDEX_PATH)


class RAGService:

    CHUNK_SIZE = 500      # characters per chunk
    CHUNK_OVERLAP = 50    # overlap between chunks

    @staticmethod
    def _extract_text(file_path: str, file_type: str) -> str:
        """Extract plain text from various file formats."""
        text = ""
        try:
            if file_type in ("pdf", "application/pdf") and PDF_AVAILABLE:
                with open(file_path, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        text += page.extract_text() + "\n"
            elif file_type in ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document") and DOCX_AVAILABLE:
                doc = DocxDocument(file_path)
                text = "\n".join(p.text for p in doc.paragraphs)
            else:
                # Plain text / markdown / code files
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
        return text.strip()

    @staticmethod
    def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """Split text into overlapping chunks."""
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            if chunk.strip():
                chunks.append(chunk.strip())
            start += chunk_size - overlap
        return chunks

    @staticmethod
    async def ingest_document(
        db: AsyncSession,
        document: Document,
    ) -> int:
        """
        Full ingestion pipeline:
        1. Extract text from file
        2. Chunk text
        3. Generate embeddings via Ollama
        4. Store in FAISS
        5. Store references in DB
        Returns number of chunks created.
        """
        if not FAISS_AVAILABLE:
            logger.warning("FAISS not available - skipping embedding generation")
            return 0

        text = RAGService._extract_text(document.file_path, document.file_type or "")
        if not text:
            logger.warning(f"No text extracted from document {document.document_id}")
            return 0

        chunks = RAGService._chunk_text(text, RAGService.CHUNK_SIZE, RAGService.CHUNK_OVERLAP)
        logger.info(f"Document {document.document_id}: {len(chunks)} chunks")

        index_id = f"user_{document.user_id}"
        vectors = []
        chunk_texts = []

        for chunk in chunks:
            embedding = await ollama_service.get_embeddings(chunk)
            if embedding:
                vectors.append(embedding)
                chunk_texts.append(chunk)

        if not vectors:
            logger.warning("No embeddings generated - is Ollama running with embedding model?")
            return 0

        # Create/load index with correct dimension
        dimension = len(vectors[0])
        faiss_manager.create_or_load_index(index_id, dimension)

        vectors_np = np.array(vectors, dtype=np.float32)
        vector_ids = faiss_manager.add_vectors(index_id, vectors_np)

        # Store references in DB
        for i, (vid, chunk_text) in enumerate(zip(vector_ids, chunk_texts)):
            emb = Embedding(
                document_id=document.document_id,
                faiss_index_id=index_id,
                vector_reference=vid,
                chunk_text=chunk_text,
                chunk_index=i,
            )
            db.add(emb)

        # Update document chunk count
        document.chunk_count = len(chunk_texts)
        await db.flush()

        logger.info(f"Ingested {len(chunk_texts)} chunks for document {document.document_id}")
        return len(chunk_texts)

    @staticmethod
    async def retrieve_context(
        db: AsyncSession,
        user_id: int,
        query: str,
        top_k: int = 5,
        document_ids: Optional[List[int]] = None,
    ) -> List[str]:
        """
        RAG retrieval:
        1. Generate query embedding
        2. Search FAISS for nearest neighbors
        3. Filter by document_ids if specified
        4. Return relevant text chunks
        """
        if not FAISS_AVAILABLE:
            return []

        query_embedding = await ollama_service.get_embeddings(query)
        if not query_embedding:
            return []

        index_id = f"user_{user_id}"
        index = faiss_manager.create_or_load_index(index_id, len(query_embedding))
        if index is None or index.ntotal == 0:
            return []

        query_vec = np.array([query_embedding], dtype=np.float32)
        results = faiss_manager.search(index_id, query_vec, top_k * 2)

        # Look up chunk texts from DB
        vector_ids = [r[0] for r in results]
        query_result = await db.execute(
            select(Embedding).where(
                Embedding.faiss_index_id == index_id,
                Embedding.vector_reference.in_(vector_ids),
            )
        )
        embeddings = query_result.scalars().all()

        # Filter by document_ids if specified
        if document_ids:
            embeddings = [e for e in embeddings if e.document_id in document_ids]

        # Sort by FAISS score order
        score_map = {r[0]: r[1] for r in results}
        embeddings.sort(key=lambda e: score_map.get(e.vector_reference, 0), reverse=True)

        return [e.chunk_text for e in embeddings[:top_k] if e.chunk_text]


rag_service = RAGService()
