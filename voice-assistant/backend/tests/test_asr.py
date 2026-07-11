from app.voice.asr import MockASR, FasterWhisperASR, create_asr


def test_mock_asr():
    asr = MockASR()
    assert asr.available
    assert asr.transcribe(b"") == ""


def test_create_asr_default_mock():
    asr = create_asr()
    assert isinstance(asr, MockASR)
    assert asr.available


def test_fasterwhisper_asr_not_loaded():
    asr = FasterWhisperASR("tiny", "cpu", "int8")
    assert not asr.available
