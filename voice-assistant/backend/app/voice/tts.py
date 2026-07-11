from __future__ import annotations

import abc


class TTSProvider(abc.ABC):
    @abc.abstractmethod
    async def synthesize(self, text: str) -> bytes:
        ...

    @property
    def available(self) -> bool:
        return True


class EdgeTTS(TTSProvider):
    def __init__(self, voice: str = "zh-CN-XiaoxiaoNeural"):
        self.voice = voice

    async def synthesize(self, text: str) -> bytes:
        import edge_tts
        communicate = edge_tts.Communicate(text, self.voice)
        chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        return b"".join(chunks)


class CosyVoiceTTS(TTSProvider):
    def __init__(self, model_name: str = "CosyVoice-300M", device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self._model = None

    @property
    def available(self) -> bool:
        return False

    async def synthesize(self, text: str) -> bytes:
        raise NotImplementedError("CosyVoice not available; use edge-tts fallback")


class MockTTS(TTSProvider):
    async def synthesize(self, text: str) -> bytes:
        return b""


async def synthesize_mp3(text: str, voice: str = "zh-CN-XiaoxiaoNeural") -> bytes:
    tts = EdgeTTS(voice)
    return await tts.synthesize(text)


def create_tts(provider: str = "edge-tts", voice: str = "zh-CN-XiaoxiaoNeural",
               model_name: str = "CosyVoice-300M") -> TTSProvider:
    if provider == "cosyvoice":
        try:
            return CosyVoiceTTS(model_name)
        except Exception:
            pass
    return EdgeTTS(voice)
