"""
Pydantic Schemas - Request/Response models for all API endpoints
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Any
from datetime import datetime


# Auth Schemas

class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    user_id: int
    name: str
    email: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# Chat Schemas

class ChatCreate(BaseModel):
    title: Optional[str] = "New Chat"


class ChatResponse(BaseModel):
    chat_id: int
    user_id: int
    title: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1)
    use_rag: bool = False
    document_ids: Optional[List[int]] = None


class MessageResponse(BaseModel):
    message_id: int
    chat_id: int
    role: str
    content: str
    token_count: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class ChatHistoryResponse(BaseModel):
    chat: ChatResponse
    messages: List[MessageResponse]


# Document Schemas

class DocumentResponse(BaseModel):
    document_id: int
    user_id: int
    filename: str
    original_filename: str
    file_size: Optional[int]
    file_type: Optional[str]
    chunk_count: int
    upload_date: datetime

    class Config:
        from_attributes = True


class EmbeddingResponse(BaseModel):
    embedding_id: int
    document_id: int
    faiss_index_id: str
    vector_reference: int
    chunk_index: int
    created_at: datetime

    class Config:
        from_attributes = True


# Agent Schemas

class AgentRunRequest(BaseModel):
    query: str = Field(..., min_length=1)
    agent_name: str = "react_agent"
    tools: Optional[List[str]] = None
    session_id: Optional[str] = None


class AgentLogResponse(BaseModel):
    log_id: int
    agent_name: str
    action: str
    action_input: Optional[str]
    action_output: Optional[str]
    tool_name: Optional[str]
    step_number: int
    duration_ms: Optional[float]
    status: str
    timestamp: datetime

    class Config:
        from_attributes = True


class AgentRunResponse(BaseModel):
    session_id: str
    agent_name: str
    final_answer: str
    steps: List[AgentLogResponse]
    total_steps: int
    total_duration_ms: float


# General Schemas

class HealthResponse(BaseModel):
    status: str
    version: str
    ollama_connected: bool
    database_connected: bool
    services: dict


class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None


class RAGQueryRequest(BaseModel):
    query: str
    document_ids: Optional[List[int]] = None
    top_k: int = Field(default=5, ge=1, le=20)
