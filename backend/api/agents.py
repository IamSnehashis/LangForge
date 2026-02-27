"""
Agents API - Run ReAct agents and retrieve execution logs
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional

from backend.db.database import get_db
from backend.core.security import get_current_user
from backend.models.models import User, AgentLog
from backend.schemas.schemas import AgentRunRequest, AgentRunResponse, AgentLogResponse
from backend.services.agent_service import agent_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/run", response_model=AgentRunResponse)
async def run_agent(
    request: AgentRunRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Execute a ReAct agent on the given query."""
    try:
        result = await agent_service.run(
            db=db,
            query=request.query,
            user_id=current_user.user_id,
            agent_name=request.agent_name,
            session_id=request.session_id,
        )
        return AgentRunResponse(
            session_id=result["session_id"],
            agent_name=result["agent_name"],
            final_answer=result["final_answer"],
            steps=[AgentLogResponse.model_validate(s) for s in result["steps"]],
            total_steps=result["total_steps"],
            total_duration_ms=result["total_duration_ms"],
        )
    except Exception as e:
        logger.error(f"Agent run failed: {e}")
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")


@router.get("/logs", response_model=List[AgentLogResponse])
async def get_agent_logs(
    session_id: Optional[str] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve agent execution logs for the current user."""
    query = select(AgentLog).where(AgentLog.user_id == current_user.user_id)
    if session_id:
        query = query.where(AgentLog.session_id == session_id)
    query = query.order_by(AgentLog.timestamp.desc()).limit(limit)

    result = await db.execute(query)
    logs = result.scalars().all()
    return [AgentLogResponse.model_validate(log) for log in logs]


@router.get("/tools")
async def list_tools(current_user: User = Depends(get_current_user)):
    """List available tools for the agent."""
    return {
        "tools": [
            {"name": name, "description": tool.description}
            for name, tool in agent_service.tools.items()
        ]
    }
