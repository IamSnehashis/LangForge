"""
Chat API - Conversation management with streaming SSE support
"""

import json
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from backend.db.database import get_db
from backend.core.security import get_current_user
from backend.models.models import User
from backend.schemas.schemas import (
    ChatCreate, ChatResponse, MessageCreate,
    MessageResponse, ChatHistoryResponse,
)
from backend.services.chat_service import ChatService
from backend.services.llm_service import ollama_service
from backend.services.rag_service import rag_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
async def create_chat(
    chat_data: ChatCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chat = await ChatService.create_chat(db, current_user.user_id, chat_data.title)
    return ChatResponse.model_validate(chat)


@router.get("/", response_model=List[ChatResponse])
async def list_chats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chats = await ChatService.get_user_chats(db, current_user.user_id)
    return [ChatResponse.model_validate(c) for c in chats]


@router.get("/{chat_id}", response_model=ChatHistoryResponse)
async def get_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chat = await ChatService.get_chat_by_id(db, chat_id, current_user.user_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return ChatHistoryResponse(
        chat=ChatResponse.model_validate(chat),
        messages=[MessageResponse.model_validate(m) for m in chat.messages],
    )


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deleted = await ChatService.delete_chat(db, chat_id, current_user.user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Chat not found")


@router.post("/{chat_id}/messages/stream")
async def stream_message(
    chat_id: int,
    message_data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify chat ownership
    chat = await ChatService.get_chat_by_id(db, chat_id, current_user.user_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Store user message
    user_msg = await ChatService.add_message(db, chat_id, "user", message_data.content)
    await db.commit()

    # Build message history for context
    history = await ChatService.get_chat_messages(db, chat_id)
    messages = [{"role": m.role, "content": m.content} for m in history]

    # RAG augmentation
    rag_context = ""
    if message_data.use_rag:
        chunks = await rag_service.retrieve_context(
            db,
            current_user.user_id,
            message_data.content,
            top_k=5,
            document_ids=message_data.document_ids,
        )
        if chunks:
            rag_context = "\n\n".join(chunks)
            # Inject context into the last user message
            messages[-1]["content"] = (
                f"Context from documents:\n{rag_context}\n\n"
                f"User question: {message_data.content}"
            )

    async def event_generator():
        full_response = ""
        try:
            yield f"data: {json.dumps({'type': 'start', 'message_id': user_msg.message_id})}\n\n"

            async for token in ollama_service.chat_stream(messages):
                full_response += token
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

            # Save complete assistant response
            async with db.begin_nested():
                assistant_msg = await ChatService.add_message(
                    db, chat_id, "assistant", full_response
                )
                # Auto-update chat title from first exchange
                if len(history) <= 2:
                    title = message_data.content[:50] + ("..." if len(message_data.content) > 50 else "")
                    await ChatService.update_chat_title(db, chat_id, title)

            await db.commit()
            yield f"data: {json.dumps({'type': 'done', 'message_id': assistant_msg.message_id})}\n\n"

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{chat_id}/messages", response_model=MessageResponse)
async def send_message(
    chat_id: int,
    message_data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a message and receive a non-streaming response (for simpler clients)."""
    chat = await ChatService.get_chat_by_id(db, chat_id, current_user.user_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    await ChatService.add_message(db, chat_id, "user", message_data.content)

    history = await ChatService.get_chat_messages(db, chat_id)
    messages = [{"role": m.role, "content": m.content} for m in history]

    if message_data.use_rag:
        chunks = await rag_service.retrieve_context(
            db, current_user.user_id, message_data.content,
            document_ids=message_data.document_ids,
        )
        if chunks:
            messages[-1]["content"] = (
                f"Context:\n{chr(10).join(chunks)}\n\nQuestion: {message_data.content}"
            )

    response_text = await ollama_service.chat_complete(messages)
    assistant_msg = await ChatService.add_message(db, chat_id, "assistant", response_text)

    return MessageResponse.model_validate(assistant_msg)
