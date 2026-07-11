from app.voice.wake import WakeWordDetector, MockWakeWordDetector, create_wake_detector


def test_mock_wake_detector():
    d = MockWakeWordDetector("测试", 0.5)
    assert not d.process_frame(b"\x00" * 1024)
    assert not d.available


def test_wake_list_keywords():
    kws = WakeWordDetector.list_keywords()
    assert "小助手" in kws


def test_create_wake_detector_returns_nonporcupine():
    d = create_wake_detector("小助手")
    assert d is not None
    assert isinstance(d, WakeWordDetector)
