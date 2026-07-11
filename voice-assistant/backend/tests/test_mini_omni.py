from app.voice.mini_omni import MiniOmniClient, create_mini_omni


def test_mini_omni_not_available():
    client = MiniOmniClient(url="http://localhost:1")
    assert not client.available


def test_create_mini_omni():
    client = create_mini_omni("http://localhost:1")
    assert client.url == "http://localhost:1"
    assert not client.auto_start
