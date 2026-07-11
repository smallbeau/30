from __future__ import annotations

from collections.abc import Iterator


class ASRService:
    def transcribe(self, audio_bytes: bytes, language: str = "zh") -> str:
        raise NotImplementedError(
            "Server-side ASR not enabled; use browser speech recognition"
        )

    def stream_transcribe(self, audio_chunks: Iterator[bytes], language: str = "zh") -> Iterator[str]:
        full = b"".join(audio_chunks)
        yield self.transcribe(full, language)

    def load_model(self) -> None:
        pass

    @property
    def available(self) -> bool:
        return False


class MockASR(ASRService):
    def transcribe(self, audio_bytes: bytes, language: str = "zh") -> str:
        return ""

    @property
    def available(self) -> bool:
        return True


class FasterWhisperASR(ASRService):
    def __init__(self, model_size: str = "base", device: str = "cpu",
                 compute_type: str = "int8", language: str = "zh"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._language = language
        self._model = None

    def load_model(self) -> None:
        if self._model is not None:
            return
        try:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                self.model_size, device=self.device, compute_type=self.compute_type
            )
        except Exception:
            self._model = None

    @property
    def available(self) -> bool:
        return self._model is not None

    def transcribe(self, audio_bytes: bytes, language: str = "zh") -> str:
        self.load_model()
        if self._model is None:
            return ""
        import io
        import numpy as np
        import soundfile as sf
        data, sr = sf.read(io.BytesIO(audio_bytes))
        if len(data.shape) > 1:
            data = data.mean(axis=1)
        segments, _ = self._model.transcribe(data, language=language or self._language)
        return "".join(seg.text for seg in segments)

    def stream_transcribe(self, audio_chunks: Iterator[bytes], language: str = "zh") -> Iterator[str]:
        self.load_model()
        if self._model is None:
            return
        import io
        import numpy as np
        import soundfile as sf
        accumulated = b""
        for chunk in audio_chunks:
            accumulated += chunk
            if len(accumulated) < 32000:
                continue
            data, sr = sf.read(io.BytesIO(accumulated))
            if len(data.shape) > 1:
                data = data.mean(axis=1)
            segments, _ = self._model.transcribe(data, language=language or self._language,
                                                  vad_filter=True)
            text = "".join(seg.text for seg in segments)
            if text.strip():
                yield text
            accumulated = b""


def create_asr(provider: str = "mock", model_size: str = "base",
               device: str = "cpu", compute_type: str = "int8",
               language: str = "zh") -> ASRService:
    if provider == "faster-whisper":
        try:
            return FasterWhisperASR(model_size, device, compute_type, language)
        except Exception:
            pass
    return MockASR()
