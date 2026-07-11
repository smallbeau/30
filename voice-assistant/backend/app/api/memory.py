from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import get_memory
from app.memory.short_term import ShortTermMemory

router = APIRouter(tags=["memory"])


@router.get("/memory/sessions")
def list_sessions():
    m = get_memory()
    return m.list_sessions()


@router.get("/memory/sessions/{session_id}")
def get_session(session_id: str):
    m = get_memory()
    msgs = m.get_messages(session_id)
    return {"session_id": session_id, "messages": msgs}


@router.delete("/memory/sessions/{session_id}")
def delete_session(session_id: str):
    m = get_memory()
    m.delete_session(session_id)
    return {"ok": True, "session_id": session_id}


@router.post("/memory/cleanup")
def cleanup_memory():
    m = get_memory()
    deleted = m.cleanup_old()
    return {"ok": True, "deleted": deleted}
