"""
Chat endpoint — main interaction API.

POST /chat sends a message and gets an NPC response.
GET /chat/history/{session_id} retrieves full chat history.
"""

import time
import hashlib
import asyncio
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks
from langchain_core.messages import AIMessage, HumanMessage

from app.core.logging import logger
from app.schemas.chat import ChatRequest, ChatResponse, SafetyFlags, StateUpdate
from app.api.middleware.safety import check_safety
from app.engine.graph import engine
from app.engine.state import create_initial_state, DEFAULT_TASK_PROGRESS, create_default_emotional_memory
from app.personas.prompts import SAFETY_BLOCK_RESPONSE

router = APIRouter(prefix="/chat", tags=["Chat"])

#  IN-MEMORY CACHE (Fast access for active sessions)
# This acts as L1 cache, with PostgreSQL/MongoDB as persistent storage
_session_states: dict[str, dict] = {}
_session_metadata: dict[str, dict] = {}  # Track session info for DB sync

#  DATABASE PERSISTENCE HELPERS

async def _save_message_to_mongo(
    session_id: str,
    role: str,
    content: str,
    agent_id: Optional[str] = None,
):
    """Background task: Save message to MongoDB."""
    try:
        from app.db.mongodb.collections import save_chat_message
        await save_chat_message(
            session_id=session_id,
            role=role,
            content=content,
            metadata={"agent_id": agent_id} if agent_id else {},
        )
        logger.debug(f"Message saved to MongoDB: {session_id}")
    except Exception as e:
        logger.warning(f"MongoDB save failed (non-blocking): {e}")

async def _save_session_state_to_mongo(session_id: str, state: dict):
    """Background task: Save full session state to MongoDB."""
    try:
        from app.db.mongodb.connection import get_mongo_db
        db = await get_mongo_db()
        
        # Convert messages to serializable format
        messages_data = []
        for msg in state.get("messages", []):
            messages_data.append({
                "role": "user" if isinstance(msg, HumanMessage) else "agent",
                "content": msg.content,
                "agent_id": msg.additional_kwargs.get("agent_id") if isinstance(msg, AIMessage) else None,
            })
        
        session_doc = {
            "session_id": session_id,
            "messages": messages_data,
            "previous_speaker": state.get("previous_speaker", ""),
            "sentiment_score": state.get("sentiment_score", 0.5),
            "turn_count": state.get("turn_count", 0),
            "stuck_counter": state.get("stuck_counter", 0),
            "task_progress": state.get("task_progress", {}),
            "agent_emotions": state.get("agent_emotions", {}),
            "user_approach_style": state.get("user_approach_style", "unknown"),
            "repeated_mistakes": state.get("repeated_mistakes", []),
            "session_narrative": state.get("session_narrative", ""),
            "updated_at": datetime.utcnow(),
        }
        
        await db.simulation_states.update_one(
            {"session_id": session_id},
            {"$set": session_doc},
            upsert=True,
        )
        logger.debug(f"Session state saved to MongoDB: {session_id}")
    except Exception as e:
        logger.warning(f"MongoDB session save failed: {e}")

async def _save_interaction_to_postgres(
    user_id: str,
    session_id: str,
    agent_name: str,
    turn_count: int,
    latency_ms: int,
    sentiment_score: float,
    task_progress: dict,
    safety_flagged: bool = False,
    hint_triggered: bool = False,
):
    """
    Background task: Save interaction log to PostgreSQL.
    Also updates simulation_session state.
    """
    try:
        from app.db.postgres.connection import AsyncSessionLocal
        from app.db.postgres.crud import (
            get_or_create_user,
            create_session,
            get_active_session,
            update_session_state,
            log_interaction,
        )
        
        async with AsyncSessionLocal() as db:
            # Get or create user
            user = await get_or_create_user(db, user_id)
            
            # Get or create simulation session
            session = await get_active_session(db, user.id)
            if not session:
                session = await create_session(db, user.id, "gucci_2.0")
                logger.info(f"Created new PostgreSQL session for user {user_id}")
            
            # Update session state
            await update_session_state(
                db,
                session.id,
                current_speaker=agent_name,
                sentiment_score=sentiment_score,
                turn_count=turn_count,
                task_progress=task_progress,
            )
            
            # Log the interaction
            await log_interaction(
                db,
                session_id=session.id,
                turn_number=turn_count,
                agent_name=agent_name,
                sentiment="positive" if sentiment_score > 0.6 else "neutral" if sentiment_score > 0.4 else "frustrated",
                hint_triggered=hint_triggered,
                safety_flag=safety_flagged,
                latency_ms=latency_ms,
            )
            
            await db.commit()
            logger.debug(f"Interaction logged to PostgreSQL: user={user_id}, agent={agent_name}")
    except Exception as e:
        logger.warning(f"PostgreSQL save failed (non-blocking): {e}")

async def _load_session_from_mongo(session_id: str) -> Optional[dict]:
    """Load session state from MongoDB if exists."""
    try:
        from app.db.mongodb.connection import get_mongo_db
        db = await get_mongo_db()
        
        doc = await db.simulation_states.find_one({"session_id": session_id})
        if doc:
            # Reconstruct messages as LangChain objects
            messages = []
            for msg_data in doc.get("messages", []):
                if msg_data["role"] == "user":
                    messages.append(HumanMessage(content=msg_data["content"]))
                else:
                    messages.append(AIMessage(
                        content=msg_data["content"],
                        additional_kwargs={"agent_id": msg_data.get("agent_id", "System")},
                    ))
            
            return {
                "messages": messages,
                "previous_speaker": doc.get("previous_speaker", ""),
                "sentiment_score": doc.get("sentiment_score", 0.5),
                "turn_count": doc.get("turn_count", 0),
                "stuck_counter": doc.get("stuck_counter", 0),
                "task_progress": doc.get("task_progress", DEFAULT_TASK_PROGRESS.copy()),
                "agent_emotions": doc.get("agent_emotions", {}),
                "user_approach_style": doc.get("user_approach_style", "unknown"),
                "repeated_mistakes": doc.get("repeated_mistakes", []),
                "session_narrative": doc.get("session_narrative", ""),
            }
    except Exception as e:
        logger.warning(f"MongoDB load failed: {e}")
    return None

def _get_or_create_session_state(session_id: str) -> dict:
    """Retrieve or initialize session state (sync version for in-memory)."""
    if session_id not in _session_states:
        _session_states[session_id] = {
            "messages": [],
            "previous_speaker": "",
            "sentiment_score": 0.5,
            "turn_count": 0,
            "stuck_counter": 0,
            "task_progress": DEFAULT_TASK_PROGRESS.copy(),
            "agent_emotions": {
                "CEO": create_default_emotional_memory(),
                "CHRO": create_default_emotional_memory(),
                "RegionalManager": create_default_emotional_memory(),
            },
            "user_approach_style": "unknown",
            "repeated_mistakes": [],
            "session_narrative": "",
        }
    return _session_states[session_id]

async def _get_or_create_session_state_async(session_id: str) -> dict:
    """
    Retrieve or initialize session state with MongoDB fallback.
    
    Priority:
    1. In-memory cache (fastest)
    2. MongoDB (persistent)
    3. Create new (default)
    """
    # Check in-memory first
    if session_id in _session_states:
        return _session_states[session_id]
    
    # Try loading from MongoDB
    mongo_state = await _load_session_from_mongo(session_id)
    if mongo_state:
        _session_states[session_id] = mongo_state
        logger.info(f"Session loaded from MongoDB: {session_id}")
        return mongo_state
    
    # Create new session
    _session_states[session_id] = {
        "messages": [],
        "previous_speaker": "",
        "sentiment_score": 0.5,
        "turn_count": 0,
        "stuck_counter": 0,
        "task_progress": DEFAULT_TASK_PROGRESS.copy(),
        "agent_emotions": {
            "CEO": create_default_emotional_memory(),
            "CHRO": create_default_emotional_memory(),
            "RegionalManager": create_default_emotional_memory(),
        },
        "user_approach_style": "unknown",
        "repeated_mistakes": [],
        "session_narrative": "",
    }
    return _session_states[session_id]

@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    """
    Main chat endpoint — send a message and receive an AI co-worker's response.

    Flow:
        1. Safety check on user message
        2. Load/create session state (from cache or MongoDB)
        3. Run LangGraph engine (Supervisor → Director → Agent)
        4. Extract response and state updates
        5. Persist state (background) and return response
    """
    start_time = time.time()

    session_id = request.session_id or f"session_{hashlib.md5(request.user_id.encode()).hexdigest()[:12]}"

    safety = check_safety(request.message, user_id=request.user_id)

    if not safety.get("is_safe", True):
        latency = int((time.time() - start_time) * 1000)
        return ChatResponse(
            session_id=session_id,
            agent="System",
            response=safety.get("suggested_response", SAFETY_BLOCK_RESPONSE),
            state_update=StateUpdate(
                current_speaker="System",
                sentiment_score=0.3,
                turn_count=0,
                task_progress={},
                hint_triggered=False,
            ),
            safety_flags=SafetyFlags(
                is_safe=False,
                blocked_reason=safety.get("blocked_reason"),
                jailbreak_attempt=safety.get("jailbreak_attempt", False),
                off_topic=safety.get("off_topic", False),
            ),
            latency_ms=latency,
        )

    session_state = await _get_or_create_session_state_async(session_id)

    # Check if user explicitly chose an agent (manual mode)
    user_explicit_choice = request.target_agent in {"CEO", "CHRO", "RegionalManager"}
    
    graph_input = {
        "messages": session_state["messages"] + [HumanMessage(content=request.message)],
        "user_message": request.message,
        "next_speaker": request.target_agent or "",
        "user_explicit_choice": user_explicit_choice,  # Prevents Director override
        "previous_speaker": session_state["previous_speaker"],
        "sentiment_score": session_state["sentiment_score"],
        "turn_count": session_state["turn_count"],
        "stuck_counter": session_state["stuck_counter"],
        "task_progress": session_state["task_progress"],
        "hint_triggered": False,
        "safety_flagged": False,
        "agent_emotions": session_state.get("agent_emotions", {}),
        "user_approach_style": session_state.get("user_approach_style", "unknown"),
        "repeated_mistakes": session_state.get("repeated_mistakes", []),
        "session_narrative": session_state.get("session_narrative", ""),
    }

    logger.info(f"Processing message from user={request.user_id} session={session_id}")

    try:
        result = await engine.ainvoke(graph_input)
    except Exception as e:
        logger.error(f"Engine error: {e}")
        latency = int((time.time() - start_time) * 1000)
        return ChatResponse(
            session_id=session_id,
            agent="System",
            response="I'm having trouble processing that. Could you rephrase your question?",
            state_update=StateUpdate(
                current_speaker="System",
                sentiment_score=session_state["sentiment_score"],
                turn_count=session_state["turn_count"],
                task_progress=session_state["task_progress"],
                hint_triggered=False,
            ),
            safety_flags=SafetyFlags(is_safe=True),
            latency_ms=latency,
        )

    # Find the last AI message (the agent's response)
    agent_response = ""
    agent_name = "System"
    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, AIMessage):
            agent_response = msg.content
            agent_name = msg.additional_kwargs.get("agent_id", "System")
            break

    session_state["messages"] = result.get("messages", session_state["messages"])
    session_state["previous_speaker"] = result.get("previous_speaker", agent_name)
    session_state["sentiment_score"] = result.get("sentiment_score", session_state["sentiment_score"])
    session_state["turn_count"] = result.get("turn_count", session_state["turn_count"])
    session_state["stuck_counter"] = result.get("stuck_counter", session_state["stuck_counter"])
    session_state["task_progress"] = result.get("task_progress", session_state["task_progress"])
    session_state["agent_emotions"] = result.get("agent_emotions", session_state.get("agent_emotions", {}))
    session_state["user_approach_style"] = result.get("user_approach_style", session_state.get("user_approach_style", "unknown"))
    session_state["repeated_mistakes"] = result.get("repeated_mistakes", session_state.get("repeated_mistakes", []))
    session_state["session_narrative"] = result.get("session_narrative", session_state.get("session_narrative", ""))

    latency = int((time.time() - start_time) * 1000)

    logger.info(f"Response from {agent_name} in {latency}ms")

    # Save user message
    background_tasks.add_task(
        _save_message_to_mongo,
        session_id=session_id,
        role="user",
        content=request.message,
        agent_id=None,
    )
    # Save agent response
    background_tasks.add_task(
        _save_message_to_mongo,
        session_id=session_id,
        role="agent",
        content=agent_response,
        agent_id=agent_name,
    )
    # Save session state
    background_tasks.add_task(
        _save_session_state_to_mongo,
        session_id=session_id,
        state=session_state.copy(),
    )

    background_tasks.add_task(
        _save_interaction_to_postgres,
        user_id=request.user_id,
        session_id=session_id,
        agent_name=agent_name,
        turn_count=session_state["turn_count"],
        latency_ms=latency,
        sentiment_score=session_state["sentiment_score"],
        task_progress=session_state["task_progress"],
        safety_flagged=not safety.get("is_safe", True),
        hint_triggered=result.get("hint_triggered", False),
    )

    return ChatResponse(
        session_id=session_id,
        agent=agent_name,
        response=agent_response,
        state_update=StateUpdate(
            current_speaker=agent_name,
            sentiment_score=session_state["sentiment_score"],
            turn_count=session_state["turn_count"],
            task_progress=session_state["task_progress"],
            hint_triggered=result.get("hint_triggered", False),
        ),
        safety_flags=SafetyFlags(
            is_safe=safety.get("is_safe", True),
            blocked_reason=safety.get("blocked_reason"),
            jailbreak_attempt=safety.get("jailbreak_attempt", False),
            off_topic=safety.get("off_topic", False),
        ),
        latency_ms=latency,
    )

@router.get("/history/{session_id}")
async def get_chat_history(session_id: str):
    """
    Retrieve the chat history for a session.
    
    Checks:
    1. In-memory cache first
    2. MongoDB if not in memory
    """
    # Try in-memory first
    state = _session_states.get(session_id)
    
    # If not in memory, try MongoDB
    if not state:
        state = await _load_session_from_mongo(session_id)
        if state:
            _session_states[session_id] = state  # Cache it
    
    if not state:
        # Also try to get from chat_messages collection
        try:
            from app.db.mongodb.collections import get_chat_history as get_mongo_history
            mongo_messages = await get_mongo_history(session_id, limit=100)
            if mongo_messages:
                return {
                    "session_id": session_id,
                    "messages": [
                        {
                            "role": m.get("role"),
                            "content": m.get("content"),
                            "agent_id": m.get("metadata", {}).get("agent_id"),
                            "timestamp": m.get("timestamp"),
                        }
                        for m in mongo_messages
                    ],
                    "total": len(mongo_messages),
                    "source": "mongodb",
                }
        except Exception as e:
            logger.warning(f"MongoDB history fetch failed: {e}")
        
        return {"session_id": session_id, "messages": [], "total": 0, "source": "not_found"}

    messages = []
    for msg in state.get("messages", []):
        messages.append({
            "role": "user" if isinstance(msg, HumanMessage) else "agent",
            "content": msg.content,
            "agent_id": msg.additional_kwargs.get("agent_id", None) if isinstance(msg, AIMessage) else None,
        })

    return {
        "session_id": session_id,
        "messages": messages,
        "total": len(messages),
        "source": "memory",
    }

@router.get("/state/{session_id}")
async def get_session_state(session_id: str):
    """
    Debug endpoint — view current session state.
    
    Checks:
    1. In-memory cache first
    2. MongoDB if not in memory
    """
    state = _session_states.get(session_id)
    
    # Try MongoDB if not in memory
    if not state:
        state = await _load_session_from_mongo(session_id)
        if state:
            _session_states[session_id] = state  # Cache it
    
    if not state:
        return {"error": "Session not found", "session_id": session_id}

    return {
        "session_id": session_id,
        "previous_speaker": state.get("previous_speaker", ""),
        "sentiment_score": state.get("sentiment_score", 0.5),
        "turn_count": state.get("turn_count", 0),
        "stuck_counter": state.get("stuck_counter", 0),
        "task_progress": state.get("task_progress", {}),
        "agent_emotions": state.get("agent_emotions", {}),
        "message_count": len(state.get("messages", [])),
        "source": "memory" if session_id in _session_states else "mongodb",
    }

#  EXPORT ENDPOINT

@router.get("/export/{session_id}")
async def export_chat(session_id: str):
    """
    Export chat history as Markdown text.
    """
    state = _session_states.get(session_id)
    
    if not state:
        state = await _load_session_from_mongo(session_id)
    
    if not state:
        return {"error": "Session not found", "session_id": session_id}
    
    lines = [
        "# AI Co-Worker Engine — Chat Export",
        f"**Session:** {session_id}",
        f"**Turn Count:** {state.get('turn_count', 0)}",
        f"**Sentiment:** {state.get('sentiment_score', 0.5):.2f}",
        "",
        "## Task Progress",
    ]
    
    for task, done in state.get("task_progress", {}).items():
        status = "[x]" if done else "[ ]"
        lines.append(f"- {status} {task}")
    
    lines.append("")
    lines.append("## Conversation")
    lines.append("")
    
    for msg in state.get("messages", []):
        if isinstance(msg, HumanMessage):
            lines.append(f"**User:** {msg.content}")
        elif isinstance(msg, AIMessage):
            agent = msg.additional_kwargs.get("agent_id", "Agent")
            lines.append(f"**{agent}:** {msg.content}")
        lines.append("")
    
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        content="\n".join(lines),
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=chat_{session_id}.md"},
    )

#  ADDITIONAL ENDPOINTS

@router.get("/sessions")
async def list_sessions():
    """List all active sessions (in-memory + MongoDB)."""
    sessions = []
    
    # In-memory sessions
    for sid, state in _session_states.items():
        sessions.append({
            "session_id": sid,
            "turn_count": state.get("turn_count", 0),
            "sentiment_score": state.get("sentiment_score", 0.5),
            "previous_speaker": state.get("previous_speaker", ""),
            "message_count": len(state.get("messages", [])),
            "source": "memory",
        })
    
    # Also try MongoDB for any sessions not in memory
    try:
        from app.db.mongodb.connection import get_mongo_db
        db = await get_mongo_db()
        cursor = db.simulation_states.find({}, {"session_id": 1, "turn_count": 1, "sentiment_score": 1, "updated_at": 1})
        async for doc in cursor:
            sid = doc.get("session_id")
            if sid and sid not in _session_states:
                sessions.append({
                    "session_id": sid,
                    "turn_count": doc.get("turn_count", 0),
                    "sentiment_score": doc.get("sentiment_score", 0.5),
                    "updated_at": doc.get("updated_at"),
                    "source": "mongodb",
                })
    except Exception as e:
        logger.warning(f"MongoDB sessions list failed: {e}")
    
    return {"sessions": sessions, "total": len(sessions)}

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session from memory and MongoDB."""
    deleted_from = []
    
    # Delete from memory
    if session_id in _session_states:
        del _session_states[session_id]
        deleted_from.append("memory")
    
    # Delete from MongoDB
    try:
        from app.db.mongodb.connection import get_mongo_db
        db = await get_mongo_db()
        result = await db.simulation_states.delete_one({"session_id": session_id})
        if result.deleted_count > 0:
            deleted_from.append("mongodb_states")
        
        result = await db.chat_messages.delete_many({"session_id": session_id})
        if result.deleted_count > 0:
            deleted_from.append(f"mongodb_messages({result.deleted_count})")
    except Exception as e:
        logger.warning(f"MongoDB delete failed: {e}")
    
    if deleted_from:
        return {"message": f"Session {session_id} deleted", "deleted_from": deleted_from}
    return {"error": "Session not found", "session_id": session_id}
