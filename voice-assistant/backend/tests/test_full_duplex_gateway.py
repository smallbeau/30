import pytest

from app.voice.full_duplex.gateway import (
    FullDuplexGateway, FullDuplexSession,
    PCMBufferLimitError, _check_limits,
)
from app.voice.pipeline import VoicePipeline


def test_create_session():
    pipeline = VoicePipeline()
    gateway = FullDuplexGateway(pipeline)
    session = gateway.create_session("test1", "fallback")
    assert session.session_id == "test1"
    assert session.mode == "fallback"
    assert session.total_pcm_bytes == 0


def test_get_session():
    pipeline = VoicePipeline()
    gateway = FullDuplexGateway(pipeline)
    gateway.create_session("test2")
    session = gateway.get_session("test2")
    assert session is not None
    assert session.session_id == "test2"


def test_end_session():
    pipeline = VoicePipeline()
    gateway = FullDuplexGateway(pipeline)
    gateway.create_session("test3")
    gateway.end_session("test3")
    assert gateway.get_session("test3") is None


def test_check_limits_per_frame():
    s = FullDuplexSession(session_id="s1", created_at=0)
    with pytest.raises(PCMBufferLimitError):
        _check_limits(s, 200000)


def test_process_audio_empty():
    pipeline = VoicePipeline()
    gateway = FullDuplexGateway(pipeline)
    gateway.create_session("s1")
    import asyncio
    result = asyncio.run(gateway.process_audio_frame("s1", b""))
    assert result is None


def test_session_isolation():
    pipeline = VoicePipeline()
    gateway = FullDuplexGateway(pipeline)
    s1 = gateway.create_session("session_a")
    s2 = gateway.create_session("session_b")
    assert s1 is not s2
    assert s1.session_id == "session_a"
    assert s2.session_id == "session_b"
