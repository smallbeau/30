import tempfile
from pathlib import Path

from app.memory.vector import VectorMemory


def test_disabled_by_default():
    vm = VectorMemory()
    assert not vm.enabled


def test_search_when_disabled():
    vm = VectorMemory()
    vm.add_entry("测试文本")
    results = vm.search("测试")
    assert results == []


def test_enabled_add_and_search():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "vm.json"
        vm = VectorMemory(db, enabled=True)
        vm.add_entry("今天北京天气很好", {"intent": "weather"})
        results = vm.search("北京天气", top_k=5)
        assert len(results) == 1
        assert results[0]["text"] == "今天北京天气很好"


def test_clear():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "vm.json"
        vm = VectorMemory(db, enabled=True)
        vm.add_entry("test")
        vm.clear()
        assert vm.search("test") == []
