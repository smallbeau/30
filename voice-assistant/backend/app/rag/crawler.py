from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


@dataclass
class CrawledPage:
    url: str
    title: str
    content: str
    timestamp: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class WebCrawler:
    def __init__(self, output_dir: str | Path = "knowledge/crawled",
                 max_pages: int = 10, delay: float = 1.0):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_pages = max_pages
        self.delay = delay
        self._visited: set[str] = set()

    def crawl_url(self, url: str) -> CrawledPage | None:
        try:
            import httpx
            resp = httpx.get(url, timeout=30.0, follow_redirects=True)
            resp.raise_for_status()
            html = resp.text
        except Exception:
            return None
        title = self._extract_title(html)
        content = self._extract_content(html)
        page = CrawledPage(
            url=url, title=title or url, content=content,
            timestamp=time.time(),
        )
        self._save_page(page)
        return page

    def _extract_title(self, html: str) -> str:
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        return m.group(1).strip() if m else ""

    def _extract_content(self, html: str) -> str:
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.I | re.S)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.I | re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        return "\n".join(lines)

    def _save_page(self, page: CrawledPage) -> None:
        domain = urlparse(page.url).netloc.replace(":", "_")
        path = self.output_dir / f"{domain}_{int(page.timestamp)}.md"
        path.write_text(
            f"# {page.title}\n\n> Source: {page.url}\n\n{page.content}",
            encoding="utf-8",
        )

    def list_crawled(self) -> list[Path]:
        return sorted(self.output_dir.glob("*.md"))


def crawl_url(url: str, output_dir: str | Path = "knowledge/crawled") -> CrawledPage | None:
    crawler = WebCrawler(output_dir)
    return crawler.crawl_url(url)
