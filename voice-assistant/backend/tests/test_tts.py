import pytest

from app.voice.tts import EdgeTTS, CosyVoiceTTS, MockTTS, create_tts, synthesize_mp3


@pytest.mark.asyncio
async def test_mock_tts():
    tts = MockTTS()
    data = await tts.synthesize("你好")
    assert data == b""


def test_cosyvoice_not_available():
    tts = CosyVoiceTTS()
    assert not tts.available


def test_create_tts_default_edge():
    tts = create_tts()
    assert isinstance(tts, EdgeTTS)


@pytest.mark.asyncio
async def test_synthesize_mp3_empty():
    data = await synthesize_mp3("")
    assert isinstance(data, bytes)
