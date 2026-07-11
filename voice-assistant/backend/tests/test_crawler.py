from pathlib import Path
import tempfile

from app.rag.crawler import WebCrawler


def test_extract_title():
    c = WebCrawler(tempfile.gettempdir())
    html = "<html><head><title>测试页面</title></head><body>内容</body></html>"
    title = c._extract_title(html)
    assert title == "测试页面"


def test_extract_content():
    c = WebCrawler(tempfile.gettempdir())
    html = "<html><body><h1>标题</h1><p>正文内容</p><script>bad</script></body></html>"
    content = c._extract_content(html)
    assert "正文内容" in content
    assert "bad" not in content
