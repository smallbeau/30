from __future__ import annotations

import asyncio
import base64
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from app.voice.pipeline import VoicePipeline


class PCMBufferLimitError(Exception):
    pass


@dataclass
class FullDuplexSession:
    session_id: str
    created_at: float = 0.0
    total_pcm_bytes: int = 0
    mode: str = "fallback"
    last_activity: float = 0.0


_MAX_PCM_PER_FRAME = 102400
_MAX_PCM_TOTAL = 31457280
_MAX_SESSION_DURATION_SEC = 1800


def _check_limits(session: FullDuplexSession, frame_size: int) -> None:
    if frame_size > _MAX_PCM_PER_FRAME:
        raise PCMBufferLimitError(f"PCM frame too large: {frame_size} > {_MAX_PCM_PER_FRAME}")
    if session.total_pcm_bytes + frame_size > _MAX_PCM_TOTAL:
        raise PCMBufferLimitError(f"PCM total exceeded: {session.total_pcm_bytes + frame_size} > {_MAX_PCM_TOTAL}")
    elapsed = time.time() - session.created_at
    if elapsed > _MAX_SESSION_DURATION_SEC:
        raise PCMBufferLimitError(f"Session duration exceeded: {elapsed:.0f}s > {_MAX_SESSION_DURATION_SEC}s")


class FullDuplexGateway:
    def __init__(self, pipeline: VoicePipeline | None = None):
        self.pipeline = pipeline or VoicePipeline()
        self._sessions: dict[str, FullDuplexSession] = {}

    def create_session(self, session_id: str, mode: str = "fallback") -> FullDuplexSession:
        session = FullDuplexSession(
            session_id=session_id, created_at=time.time(),
            mode=mode, last_activity=time.time(),
        )
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> FullDuplexSession | None:
        return self._sessions.get(session_id)

    async def process_audio_frame(self, session_id: str, pcm: bytes) -> str | None:
        session = self.get_session(session_id)
        if session is None:
            return None
        _check_limits(session, len(pcm))
        session.total_pcm_bytes += len(pcm)
        session.last_activity = time.time()

        if session.mode == "fallback":
            text = self.pipeline.asr.transcribe(pcm, "zh")
            return text.strip() or None
        return None

    async def process_text(self, session_id: str, text: str,
                           stream_handler) -> AsyncIterator[str]:
        session = self.get_session(session_id)
        if session is None:
            return
        session.last_activity = time.time()
        async for token in stream_handler(text, session_id):
            yield token

    def end_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
