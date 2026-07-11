class ASRService:
    """第一阶段：浏览器侧 ASR 为主；服务端预留接口"""

    def transcribe(self, audio_bytes: bytes, language: str = "zh") -> str:
        raise NotImplementedError(
            "Server-side ASR not enabled in phase1; use browser speech recognition"
        )