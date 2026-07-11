from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Iterator

import httpx


class MiniOmniClient:
    def __init__(self, url: str = "http://localhost:60808",
                 auto_start: bool = False,
                 server_script: str = "third_party/mini-omni/server.py"):
        self.url = url
        self.auto_start = auto_start
        self.server_script = Path(server_script)
        self._proc: subprocess.Popen | None = None

    @property
    def available(self) -> bool:
        return self.health_check()

    def health_check(self, timeout: float = 3.0) -> bool:
        try:
            r = httpx.get(f"{self.url}/health", timeout=timeout)
            return r.status_code == 200
        except (httpx.HTTPError, httpx.TimeoutException):
            return False

    def wait_until_ready(self, timeout: float = 30.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.health_check():
                return
            time.sleep(0.5)
        raise TimeoutError("Mini-Omni server did not start within 30s")

    def start_server(self) -> None:
        if self._proc is not None:
            return
        if not self.server_script.exists():
            raise FileNotFoundError(f"Mini-Omni server script not found: {self.server_script}")
        self._proc = subprocess.Popen(
            ["uvicorn", "server:app", "--host", "127.0.0.1", "--port", "60808"],
            cwd=str(self.server_script.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def stop_server(self) -> None:
        if self._proc is not None:
            self._proc.terminate()
            self._proc.wait(timeout=5)
            self._proc = None

    def stream_chat(self, wav_bytes: bytes, stream_stride: int = 4,
                    max_tokens: int = 2048) -> Iterator[dict[str, Any]]:
        payload = {
            "audio": base64.b64encode(wav_bytes).decode("ascii"),
            "stream_stride": stream_stride,
            "max_tokens": max_tokens,
        }
        with httpx.Client() as client:
            resp = client.post(f"{self.url}/chat", json=payload, timeout=None)
            for line in resp.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                audio = base64.b64decode(data["audio"]) if data.get("audio") else None
                yield {"text": data.get("text", ""), "audio": audio}


def create_mini_omni(url: str = "http://localhost:60808",
                     auto_start: bool = False) -> MiniOmniClient:
    return MiniOmniClient(url=url, auto_start=auto_start)
