from __future__ import annotations

import struct
from typing import Callable


class WakeWordDetector:
    def __init__(self, keyword: str = "小助手", sensitivity: float = 0.5,
                 model_path: str = "", on_wake: Callable[[], None] | None = None):
        self.keyword = keyword
        self.sensitivity = sensitivity
        self.model_path = model_path
        self.on_wake = on_wake
        self._porcupine = None
        self._running = False

    @property
    def available(self) -> bool:
        return False

    def start(self, audio_stream=None) -> None:
        pass

    def stop(self) -> None:
        self._running = False

    def process_frame(self, pcm_frame: bytes) -> bool:
        return False

    @staticmethod
    def list_keywords() -> list[str]:
        return ["小助手", "你好助手", "智能助手"]


class MockWakeWordDetector(WakeWordDetector):
    def process_frame(self, pcm_frame: bytes) -> bool:
        return False


def create_wake_detector(keyword: str = "小助手", sensitivity: float = 0.5,
                         model_path: str = "", on_wake: Callable[[], None] | None = None) -> WakeWordDetector:
    try:
        import pvporcupine
        detector = _PorcupineDetector(keyword, sensitivity, model_path, on_wake)
        if detector._porcupine is not None:
            return detector
    except Exception:
        pass
    return MockWakeWordDetector(keyword, sensitivity, model_path, on_wake)


class _PorcupineDetector(WakeWordDetector):
    _KEYWORD_MAP = {
        "小助手": "小助手",
        "你好助手": "你好助手",
        "智能助手": "智能助手",
    }

    def __init__(self, keyword: str = "小助手", sensitivity: float = 0.5,
                 model_path: str = "", on_wake: Callable[[], None] | None = None):
        super().__init__(keyword, sensitivity, model_path, on_wake)
        try:
            import pvporcupine
            kw = self._KEYWORD_MAP.get(keyword, keyword)
            self._porcupine = pvporcupine.create(keywords=[kw], sensitivities=[sensitivity])
            self.sample_rate = self._porcupine.sample_rate
            self.frame_length = self._porcupine.frame_length
        except Exception:
            self._porcupine = None

    @property
    def available(self) -> bool:
        return self._porcupine is not None

    def process_frame(self, pcm_frame: bytes) -> bool:
        if self._porcupine is None:
            return False
        pcm = struct.unpack_from("h" * self.frame_length, pcm_frame)
        result = self._porcupine.process(pcm)
        if result >= 0 and self.on_wake:
            self.on_wake()
        return result >= 0
