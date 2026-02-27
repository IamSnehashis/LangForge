"""
Chat Service - CRUD for Chats and Messages
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime

from backend.models.models import Chat, Message


class ChatService:

    @staticmethod
    async def create_chat(db: AsyncSession, user_id: int, title: str = "New Chat") -> Chat:
        chat = Chat(user_id=user_id, title=title)
        db.add(chat)
        await db.flush()
        await db.refresh(chat)
        return chat

    @staticmethod
    async def get_user_chats(db: AsyncSession, user_id: int) -> List[Chat]:
        result = await db.execute(
            select(Chat)
            .where(Chat.user_id == user_id)
            .order_by(Chat.updated_at.desc())
        )
        return result.scalars().all()

    @staticmethod
    async def get_chat_by_id(db: AsyncSession, chat_id: int, user_id: int) -> Optional[Chat]:
        result = await db.execute(
            select(Chat)
            .where(Chat.chat_id == chat_id, Chat.user_id == user_id)
            .options(selectinload(Chat.messages))
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def delete_chat(db: AsyncSession, chat_id: int, user_id: int) -> bool:
        chat = await db.execute(
            select(Chat).where(Chat.chat_id == chat_id, Chat.user_id == user_id)
        )
        chat = chat.scalar_one_or_none()
        if not chat:
            return False
        await db.delete(chat)
        return True

    @staticmethod
    async def add_message(
        db: AsyncSession,
        chat_id: int,
        role: str,
        content: str,
        token_count: Optional[int] = None,
    ) -> Message:
        msg = Message(chat_id=chat_id, role=role, content=content, token_count=token_count)
        db.add(msg)
        # Update chat timestamp
        chat_result = await db.execute(select(Chat).where(Chat.chat_id == chat_id))
        chat = chat_result.scalar_one_or_none()
        if chat:
            chat.updated_at = datetime.utcnow()
        await db.flush()
        await db.refresh(msg)
        return msg

    @staticmethod
    async def get_chat_messages(db: AsyncSession, chat_id: int) -> List[Message]:
        result = await db.execute(
            select(Message)
            .where(Message.chat_id == chat_id)
            .order_by(Message.created_at.asc())
        )
        return result.scalars().all()

    @staticmethod
    async def update_chat_title(db: AsyncSession, chat_id: int, title: str) -> Optional[Chat]:
        result = await db.execute(select(Chat).where(Chat.chat_id == chat_id))
        chat = result.scalar_one_or_none()
        if chat:
            chat.title = title
            await db.flush()
        return chat
