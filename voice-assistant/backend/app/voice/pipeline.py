from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from app.voice.asr import ASRService, create_asr
from app.voice.tts import create_tts, TTSProvider
from app.voice.wake import WakeWordDetector, create_wake_detector
from app.voice.vad import EnergyVAD


@dataclass
class VoicePipelineConfig:
    wake_enabled: bool = False
    wake_keyword: str = "小助手"
    wake_sensitivity: float = 0.5
    asr_provider: str = "mock"
    asr_model: str = "base"
    asr_device: str = "cpu"
    asr_language: str = "zh"
    tts_provider: str = "edge-tts"
    tts_voice: str = "zh-CN-XiaoxiaoNeural"
    auto_send_audio: bool = True
    vad_silence_ms: int = 500
    vad_threshold: float = 0.5
    vad_min_speech_ms: int = 300
    vad_min_silence_ms: int = 200
    vad_speech_pad_ms: int = 300


@dataclass
class AudioFrame:
    pcm: bytes
    sample_rate: int = 16000


@dataclass
class TranscriptionResult:
    text: str
    is_final: bool = True
    confidence: float = 1.0


class VoicePipeline:
    def __init__(self, config: VoicePipelineConfig | None = None):
        self.config = config or VoicePipelineConfig()
        self.asr: ASRService = create_asr(
            self.config.asr_provider, self.config.asr_model,
            self.config.asr_device, language=self.config.asr_language,
        )
        self.tts: TTSProvider = create_tts(
            self.config.tts_provider, self.config.tts_voice,
        )
        self.wake: WakeWordDetector = create_wake_detector(
            self.config.wake_keyword, self.config.wake_sensitivity,
        )
        self.vad = EnergyVAD(
            threshold=self.config.vad_threshold,
            silence_ms=self.config.vad_silence_ms,
            sample_rate=16000,
        )

    async def transcribe_audio(self, audio_bytes: bytes) -> str:
        return self.asr.transcribe(audio_bytes, self.config.asr_language)

    async def synthesize(self, text: str) -> bytes:
        return await self.tts.synthesize(text)

    async def process_audio_stream(
        self, audio_stream: AsyncIterator[AudioFrame],
    ) -> AsyncIterator[TranscriptionResult]:
        accumulated = b""
        async for frame in audio_stream:
            is_speech = self.vad.is_speech(frame.pcm)
            if is_speech:
                accumulated += frame.pcm
            elif accumulated:
                text = self.asr.transcribe(accumulated, self.config.asr_language)
                if text.strip():
                    yield TranscriptionResult(text=text.strip())
                accumulated = b""
