"""
Agent Service - Multi-step ReAct Agent with Tool Orchestration and DB Logging
"""

import time
import uuid
import logging
from typing import List, Dict, Optional, Callable, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.models.models import AgentLog
from backend.services.llm_service import ollama_service
from backend.core.config import settings

logger = logging.getLogger(__name__)


# Tool Definitions

class Tool:
    def __init__(self, name: str, description: str, func: Callable):
        self.name = name
        self.description = description
        self.func = func

    async def run(self, input_str: str) -> str:
        try:
            if callable(self.func):
                import asyncio
                if asyncio.iscoroutinefunction(self.func):
                    return await self.func(input_str)
                return str(self.func(input_str))
        except Exception as e:
            return f"Tool error: {str(e)}"


def calculator_tool(expression: str) -> str:
    import re
    # Only allow safe math chars
    if re.match(r'^[\d\s\+\-\*\/\.\(\)\%\*\*]+$', expression):
        try:
            result = eval(expression, {"__builtins__": {}})
            return str(result)
        except Exception as e:
            return f"Calculation error: {e}"
    return "Invalid expression - only numeric operators allowed"


def string_tool(text: str) -> str:
    parts = text.split(":", 1)
    if len(parts) != 2:
        return "Format: <operation>:<text>  (operations: upper, lower, reverse, length, count_words)"
    op, content = parts[0].strip().lower(), parts[1].strip()
    ops = {
        "upper": lambda s: s.upper(),
        "lower": lambda s: s.lower(),
        "reverse": lambda s: s[::-1],
        "length": lambda s: str(len(s)),
        "count_words": lambda s: str(len(s.split())),
    }
    return ops.get(op, lambda s: f"Unknown op: {op}")(content)


def current_time_tool(_: str) -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %Human:%M:%S UTC")


def search_knowledge_tool(query: str) -> str:
    kb = {
        "python": "Python is a high-level, interpreted programming language known for readability.",
        "ai": "Artificial Intelligence is the simulation of human intelligence by machines.",
        "rag": "Retrieval-Augmented Generation combines document retrieval with LLM generation.",
        "langchain": "LangChain is a framework for developing applications powered by language models.",
        "fastapi": "FastAPI is a modern, fast web framework for building APIs with Python.",
        "faiss": "FAISS (Facebook AI Similarity Search) is a library for efficient similarity search.",
    }
    q = query.lower()
    for key, val in kb.items():
        if key in q:
            return val
    return f"No information found for: {query}"


DEFAULT_TOOLS = [
    Tool("calculator", "Evaluates math expressions. Input: arithmetic expression", calculator_tool),
    Tool("string_ops", "String operations. Input: operation:text (e.g. upper:hello)", string_tool),
    Tool("current_time", "Returns the current UTC time. Input: anything", current_time_tool),
    Tool("knowledge_search", "Looks up information about topics. Input: topic query", search_knowledge_tool),
]


# ReAct Agent

REACT_SYSTEM_PROMPT = """You are a helpful AI agent. You solve problems step by step using available tools.

Available tools:
{tools}

Follow this EXACT format for each step:
Thought: <your reasoning about what to do next>
Action: <tool_name>
Action Input: <input for the tool>

When you have the final answer, respond with:
Thought: I now have the final answer
Final Answer: <your complete answer>

Rules:
- Use tools when needed, don't assume answers
- Always start with Thought:
- Use exactly one tool per step
- Stop when you have Final Answer:
"""

class AgentService:
    def __init__(self, tools: List[Tool] = None):
        self.tools = {t.name: t for t in (tools or DEFAULT_TOOLS)}

    def _build_system_prompt(self) -> str:
        tool_descriptions = "\n".join(
            f"- {name}: {tool.description}"
            for name, tool in self.tools.items()
        )
        return REACT_SYSTEM_PROMPT.format(tools=tool_descriptions)

    def _parse_agent_output(self, text: str) -> Dict[str, Optional[str]]:
        import re
        result = {"thought": None, "action": None, "action_input": None, "final_answer": None}

        thought_match = re.search(r"Thought:\s*(.+?)(?=Action:|Final Answer:|$)", text, re.DOTALL | re.IGNORECASE)
        if thought_match:
            result["thought"] = thought_match.group(1).strip()

        action_match = re.search(r"Action:\s*(.+?)(?=Action Input:|$)", text, re.DOTALL | re.IGNORECASE)
        if action_match:
            result["action"] = action_match.group(1).strip()

        input_match = re.search(r"Action Input:\s*(.+?)(?=Thought:|Final Answer:|$)", text, re.DOTALL | re.IGNORECASE)
        if input_match:
            result["action_input"] = input_match.group(1).strip()

        final_match = re.search(r"Final Answer:\s*(.+)", text, re.DOTALL | re.IGNORECASE)
        if final_match:
            result["final_answer"] = final_match.group(1).strip()

        return result

    async def run(
        self,
        db: AsyncSession,
        query: str,
        user_id: Optional[int] = None,
        agent_name: str = "react_agent",
        session_id: Optional[str] = None,
        max_steps: int = 8,
    ) -> Dict[str, Any]:
        """Execute the ReAct agent loop and return structured results."""
        session_id = session_id or str(uuid.uuid4())
        total_start = time.time()
        logs: List[AgentLog] = []
        messages = [
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "user", "content": query},
        ]

        final_answer = None
        step = 0

        while step < max_steps:
            step += 1
            step_start = time.time()

            # LLM call
            llm_response = await ollama_service.chat_complete(messages, temperature=0.1)
            parsed = self._parse_agent_output(llm_response)
            duration = (time.time() - step_start) * 1000

            # Log: LLM reasoning step
            reasoning_log = AgentLog(
                user_id=user_id,
                session_id=session_id,
                agent_name=agent_name,
                action="think",
                action_input=query if step == 1 else None,
                action_output=parsed.get("thought"),
                step_number=step,
                duration_ms=duration,
                status="success",
            )
            db.add(reasoning_log)
            logs.append(reasoning_log)

            # Final answer reached
            if parsed.get("final_answer"):
                final_answer = parsed["final_answer"]
                final_log = AgentLog(
                    user_id=user_id,
                    session_id=session_id,
                    agent_name=agent_name,
                    action="final_answer",
                    action_output=final_answer,
                    step_number=step,
                    status="success",
                )
                db.add(final_log)
                logs.append(final_log)
                break

            # Execute tool action
            action = parsed.get("action")
            action_input = parsed.get("action_input", "")

            if action and action in self.tools:
                tool_start = time.time()
                tool_result = await self.tools[action].run(action_input or "")
                tool_duration = (time.time() - tool_start) * 1000

                # Log: tool execution
                tool_log = AgentLog(
                    user_id=user_id,
                    session_id=session_id,
                    agent_name=agent_name,
                    action="tool_call",
                    action_input=action_input,
                    action_output=tool_result,
                    tool_name=action,
                    step_number=step,
                    duration_ms=tool_duration,
                    status="success",
                )
                db.add(tool_log)
                logs.append(tool_log)

                # Add result to conversation
                messages.append({"role": "assistant", "content": llm_response})
                messages.append({"role": "user", "content": f"Observation: {tool_result}"})
            else:
                # No valid action - tell agent to try again
                messages.append({"role": "assistant", "content": llm_response})
                messages.append({
                    "role": "user",
                    "content": "Please provide a valid Action from the available tools, or provide Final Answer."
                })

        await db.flush()

        total_duration = (time.time() - total_start) * 1000

        if not final_answer:
            final_answer = "I was unable to complete the task within the step limit."

        # Refresh logs to get IDs
        from backend.schemas.schemas import AgentLogResponse
        await db.flush()

        return {
            "session_id": session_id,
            "agent_name": agent_name,
            "final_answer": final_answer,
            "steps": logs,
            "total_steps": step,
            "total_duration_ms": total_duration,
        }


agent_service = AgentService()
