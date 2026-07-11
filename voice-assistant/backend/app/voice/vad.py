import numpy as np


class EnergyVAD:
    def __init__(self, threshold: float = 0.5, silence_ms: int = 500, sample_rate: int = 16000):
        self.threshold = threshold
        self.silence_ms = silence_ms
        self.sample_rate = sample_rate
        self._silent_samples = 0

    def is_speech(self, pcm16: bytes) -> bool:
        if not pcm16:
            return False
        audio = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32) / 32768.0
        energy = float(np.sqrt(np.mean(audio**2))) if len(audio) else 0.0
        if energy >= self.threshold * 0.02:
            self._silent_samples = 0
            return True
        self._silent_samples += len(audio)
        return False

    def speech_ended(self) -> bool:
        silence_samples = int(self.sample_rate * (self.silence_ms / 1000))
        return self._silent_samples >= silence_samples