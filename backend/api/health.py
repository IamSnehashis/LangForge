"""Health Check API"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from backend.db.database import get_db
from backend.services.llm_service import ollama_service
from backend.schemas.schemas import HealthResponse
from backend.core.config import settings

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    # Check DB
    db_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    # Check Ollama
    ollama_ok = await ollama_service.is_connected()

    return HealthResponse(
        status="healthy" if (db_ok and ollama_ok) else "degraded",
        version=settings.APP_VERSION,
        ollama_connected=ollama_ok,
        database_connected=db_ok,
        services={
            "api": "running",
            "database": "connected" if db_ok else "disconnected",
            "ollama": "connected" if ollama_ok else "disconnected",
        },
    )
