"""
SQLAlchemy ORM Models - All database tables for LangForge
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey,
    Boolean, Float, JSON
)
from sqlalchemy.orm import relationship
from backend.db.database import Base


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    chats = relationship("Chat", back_populates="user", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User id={self.user_id} email={self.email}>"


class Chat(Base):
    __tablename__ = "chats"

    chat_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), default="New Chat")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="chats")
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Chat id={self.chat_id} user_id={self.user_id}>"


class Message(Base):
    __tablename__ = "messages"

    message_id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.chat_id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)   # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    chat = relationship("Chat", back_populates="messages")

    def __repr__(self):
        return f"<Message id={self.message_id} role={self.role}>"


class Document(Base):
    __tablename__ = "documents"

    document_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=True)   # bytes
    file_type = Column(String(50), nullable=True)
    chunk_count = Column(Integer, default=0)
    upload_date = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="documents")
    embeddings = relationship("Embedding", back_populates="document", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Document id={self.document_id} filename={self.filename}>"


class Embedding(Base):
    __tablename__ = "embeddings"

    embedding_id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.document_id", ondelete="CASCADE"), nullable=False)
    faiss_index_id = Column(String(100), nullable=False)   # FAISS index name
    vector_reference = Column(Integer, nullable=False)      # FAISS vector ID
    chunk_text = Column(Text, nullable=True)                # text chunk this embedding represents
    chunk_index = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="embeddings")

    def __repr__(self):
        return f"<Embedding id={self.embedding_id} doc_id={self.document_id}>"


class AgentLog(Base):
    __tablename__ = "agent_logs"

    log_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    session_id = Column(String(100), nullable=True, index=True)
    agent_name = Column(String(100), nullable=False)
    action = Column(String(255), nullable=False)
    action_input = Column(Text, nullable=True)
    action_output = Column(Text, nullable=True)
    tool_name = Column(String(100), nullable=True)
    step_number = Column(Integer, default=0)
    duration_ms = Column(Float, nullable=True)
    status = Column(String(20), default="success")  # success, error, running
    error_message = Column(Text, nullable=True)
    extra_metadata = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AgentLog id={self.log_id} agent={self.agent_name} action={self.action}>"


class SystemLog(Base):
    __tablename__ = "system_logs"

    log_id = Column(Integer, primary_key=True, index=True)
    level = Column(String(20), default="INFO")
    component = Column(String(100), nullable=True)
    message = Column(Text, nullable=False)
    extra_metadata = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<SystemLog id={self.log_id} level={self.level}>"
