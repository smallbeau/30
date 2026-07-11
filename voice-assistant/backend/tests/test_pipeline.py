import pytest

from app.voice.pipeline import VoicePipeline, VoicePipelineConfig, AudioFrame, TranscriptionResult


def test_pipeline_default_config():
    p = VoicePipeline()
    assert p.config.asr_provider == "mock"
    assert p.config.tts_provider == "edge-tts"


@pytest.mark.asyncio
async def test_pipeline_transcribe():
    p = VoicePipeline()
    result = await p.transcribe_audio(b"")
    assert result == ""


@pytest.mark.asyncio
async def test_pipeline_synthesize():
    p = VoicePipeline()
    data = await p.synthesize("你好")
    assert isinstance(data, bytes)


@pytest.mark.asyncio
async def test_pipeline_audio_stream_empty():
    p = VoicePipeline()
    results = []
    async for r in p.process_audio_stream(aiter([])):
        results.append(r)
    assert len(results) == 0


async def aiter(items):
    for item in items:
        yield item
