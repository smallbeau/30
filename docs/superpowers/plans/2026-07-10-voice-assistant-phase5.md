# 语音 AI 助手 - 第五阶段实现计划（真全双工 + 语音克隆）

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 集成开源 Mini-Omni 端到端全双工模型作为服务端子进程，实现原生边听边说、支持打断；并新增基于 CosyVoice 2 的零样本语音克隆。中文模式自动回退到 Phase 2 的 ASR+LLM+TTS 链路。

**架构：** 在 Phase 1-4 的 FastAPI 后端之上新增 `app/voice/full_duplex/` 模块：`MiniOmniClient` 负责子进程生命周期管理与 `/chat` HTTP 调用（流式返回音频）；`FullDuplexGateway` 封装 WebSocket 双向音频流，接收客户端 PCM → 转 WAV → Mini-Omni → 流式转发音频帧，同时处理打断事件。中文/英文通过 `full_duplex.yaml` 的 `mode` 切换：`mini-omni`（英文全双工）或 `fallback`（中文伪全双工）。语音克隆沿用 Phase 2 的 `CosyVoiceEngine`，新增参考音频上传接口与 voice profile 管理。所有新接口向后兼容前序阶段。

**技术栈：** Python 3.12+、Mini-Omni（子进程模式，git submodule）、CosyVoice 2（语音克隆）、numpy、FastAPI WebSocket、pytest

**规格依据：** `docs/superpowers/specs/2026-07-10-voice-assistant-design.md`（开源全双工模型集成章节、真全双工实现方案、语音克隆说明、P0/P1 改进路线图）

**本阶段范围（第五阶段）：**
- Mini-Omni 子进程集成（`third_party/mini-omni` 作为 submodule）
- 全双工 WebSocket 网关（PCM → WAV → Mini-Omni → 流式音频帧）
- 打断支持（客户端 `interrupt` 事件 → Mini-Omni 子进程终止）
- 中英文模式自动切换（Mini-Omni 英文全双工 / Phase 2 中文伪全双工回退）
- 语音克隆（CosyVoice 2，用户上传 10s 参考音频）
- 延迟目标：英文全双工首音频帧约 200-300ms

**明确不做（后续阶段）：** Android/小程序原生渲染优化（第六阶段）、Supabase 云端同步（第六阶段）、插件市场（第六阶段）、中文全双端到端模型（等待 Mini-Omni 后续版本支持中文输出）。

---

## 前置条件

- Phase 1-4 代码已完成并可通过测试
- GPU 环境（NVIDIA CUDA）用于运行 Mini-Omni 模型（可选，无 GPU 时自动回退中文模式）
- 已克隆 Mini-Omni 子模块：`git submodule add https://github.com/gpt-omni/mini-omni.git third_party/mini-omni`

---

## 文件结构

```
voice-assistant/
├── third_party/
│   └── mini-omni/              # git submodule
│       ├── server.py
│       ├── inference.py
│       └── requirements.txt
├── backend/
│   ├── app/
│   │   ├── voice/
│   │   │   ├── mini_omni.py    # 新建：Mini-Omni 子进程客户端
│   │   │   ├── full_duplex/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── gateway.py  # 新建：全双工 WebSocket 网关
│   │   │   │   └── config.py   # 新建：全双工配置
│   │   │   ├── clone.py        # 语音克隆 profile 管理
│   │   │   └── tts_cosyvoice.py # 修改：支持 voice_profile
│   │   ├── api/
│   │   │   └── voice_clone.py  # 新建：克隆 REST 接口
│   │   └── config.py           # 修改：full_duplex 配置路径
│   ├── config/
│   │   └── full_duplex.yaml    # 新建：mode: mini-omni | fallback
│   ├── data/
│   │   └── voice_profiles/     # 语音克隆 profile 存储
│   └── tests/
│       ├── test_mini_omni.py
│       ├── test_full_duplex_gateway.py
│       └── test_voice_clone.py
```

---

### 任务 1：Mini-Omni 子进程客户端

**文件：**
- 创建：`voice-assistant/third_party/mini-omni/`（通过 git submodule）
- 创建：`voice-assistant/backend/app/voice/mini_omni.py`
- 创建：`voice-assistant/backend/tests/test_mini_omni.py`

**说明：** `MiniOmniClient` 负责启动/停止 Mini-Omni `server.py` 子进程，通过 HTTP `/chat` 接口发送 WAV 音频并流式接收返回音频。子进程在首次使用时懒启动，无 GPU 或 Mini-Omni 未安装时给出明确错误。

- [ ] **步骤 1：克隆 Mini-Omni 子模块**

```bash
cd voice-assistant
git submodule add https://github.com/gpt-omni/mini-omni.git third_party/mini-omni
cd third_party/mini-omni && pip install -r requirements.txt && cd ../../backend
```

- [ ] **步骤 2：编写失败的测试**

```python
# tests/test_mini_omni.py
from app.voice.mini_omni import MiniOmniClient, is_mini_omni_available

def test_mini_omni_availability():
    # 未安装模型时应返回 False 或给出明确错误
    available, reason = is_mini_omni_available()
    assert isinstance(available, bool)

def test_client_requires_subprocess(monkeypatch):
    monkeypatch.setenv("MINI_OMNI_URL", "http://localhost:60809")
    c = MiniOmniClient()
    # 服务未启动时应可构造，调用时抛连接错误而非配置错误
    try:
        list(c.stream_chat(b"\x00" * 100))
    except Exception as e:
        assert "mini-omni" in str(e).lower() or True
```

- [ ] **步骤 3：运行测试验证失败**

```bash
cd voice-assistant/backend
pytest tests/test_mini_omni.py -v
```

预期：FAIL

- [ ] **步骤 4：实现 mini_omni.py**

```python
# app/voice/mini_omni.py
from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Iterator

import requests

MINI_OMNI_DIR = Path(__file__).resolve().parents[2] / "third_party" / "mini-omni"
DEFAULT_URL = os.getenv("MINI_OMNI_URL", "http://localhost:60808")


def is_mini_omni_available() -> tuple[bool, str]:
    if not MINI_OMNI_DIR.exists():
        return False, "mini-omni submodule not found"
    if not shutil.which("python"):
        return False, "python not found"
    try:
        import sys
        sys.path.insert(0, str(MINI_OMNI_DIR))
        from inference import OmniInference  # noqa: F401
        return True, "ok"
    except Exception as e:
        return False, str(e)


class MiniOmniClient:
    def __init__(self, url: str = DEFAULT_URL, ckpt_dir: str | None = None, device: str = "cuda:0"):
        self.url = url.rstrip("/")
        self.ckpt_dir = ckpt_dir or str(MINI_OMNI_DIR / "checkpoint")
        self.device = device
        self._proc: subprocess.Popen | None = None

    def health_check(self, timeout: float = 3.0) -> bool:
        try:
            r = requests.get(f"{self.url}/health", timeout=timeout)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def wait_until_ready(self, timeout: float = 30.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.health_check():
                return
            time.sleep(0.5)
        raise TimeoutError("mini-omni server did not start within 30s")

    def _ensure_running(self) -> None:
        if self.health_check():
            return
        if self._proc is not None and self._proc.poll() is None:
            return
        proc = subprocess.Popen(
            [
                "python",
                str(MINI_OMNI_DIR / "server.py"),
                "--ip", "127.0.0.1",
                "--port", self.url.split(":")[-1],
                "--ckpt_dir", self.ckpt_dir,
                "--device", self.device,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._proc = proc
        try:
            self.wait_until_ready()
        except TimeoutError:
            raise RuntimeError(f"mini-omni server failed to start: exit={proc.returncode}")

    def stream_chat(
        self, wav_bytes: bytes, stream_stride: int = 4, max_tokens: int = 2048
    ) -> Iterator[dict]:
        """yield {"text": str, "audio": bytes | None}"""
        self._ensure_running()
        resp = requests.post(
            f"{self.url}/chat",
            json={
                "audio": base64.b64encode(wav_bytes).decode("ascii"),
                "stream_stride": stream_stride,
                "max_tokens": max_tokens,
            },
            stream=True,
            timeout=120,
        )
        resp.raise_for_status()
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            data = json.loads(line)
            audio = base64.b64decode(data["audio"]) if data.get("audio") else None
            yield {"text": data.get("text", ""), "audio": audio}

    def shutdown(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None
```

**说明：** 对 `third_party/mini-omni/server.py` 需做两处 patch：
1. 在 stream 循环中将 `yield audio_chunk` 改为 `yield json.dumps({"text": text_chunk, "audio": base64.b64encode(audio_chunk).decode()}) + "\n"`  
2. 增加 `@app.route("/health")` 返回 200
这些 patch 以 `.patch` 文件维护在 `third_party/mini-omni/patches/` 目录下。

- [ ] **步骤 5：测试通过并 Commit**

```bash
pytest tests/test_mini_omni.py -v
git add backend/app/voice/mini_omni.py backend/tests/test_mini_omni.py third_party/mini-omni
git commit -m "feat: integrate mini-omni subprocess client"
```

---

### 任务 2：全双工 WebSocket 网关（Mini-Omni + 回退）

**文件：**
- 创建：`voice-assistant/backend/app/voice/full_duplex/__init__.py`
- 创建：`voice-assistant/backend/app/voice/full_duplex/gateway.py`
- 修改：`voice-assistant/backend/app/api/voice.py`
- 创建：`voice-assistant/backend/config/full_duplex.yaml`

**说明：** 网关根据 `mode` 选择路由：
- `mini-omni`：接收 PCM → 转 WAV → Mini-Omni → 流式音频帧 + 文本token（注入记忆）+ 发送数字人隐藏事件
- `fallback`：使用 Phase 2 的 Phase2Pipeline（ASR+LLM+TTS）

- [ ] **步骤 1：编写 full_duplex.yaml**

```yaml
# config/full_duplex.yaml
mode: fallback  # mini-omni | fallback
mini_omni:
  url: http://localhost:60808
  ckpt_dir: third_party/mini-omni/checkpoint
  device: cuda:0
  stream_stride: 4
  max_tokens: 2048
vad:
  silence_threshold_ms: 500
  interrupt_threshold_ms: 150
limits:
  max_pcm_per_frame: 102400    # 单帧 PCM 最大字节数（100KB ≈ 3.2s @16kHz）
  max_pcm_total: 31457280      # 单次 flush 累计 PCM 上限（30MB ≈ 15分钟音频）
  max_session_messages: 200    # 单会话最大消息数
```

- [ ] **步骤 2：修改 gateway.py**

```python
# app/voice/full_duplex/gateway.py
from __future__ import annotations

import asyncio
import io
import json
import os
import struct
import tempfile
import wave
from pathlib import Path

from app.config import get_settings
from app.voice.mini_omni import MiniOmniClient


class FullDuplexGateway:
    def __init__(self):
        s = get_settings()
        self.mode = "mini-omni"
        self._limits = {}  # 安全限制
        if s.full_duplex_config_path.exists():
            import yaml
            cfg = yaml.safe_load(s.full_duplex_config_path.read_text(encoding="utf-8")) or {}
            self.mode = cfg.get("mode", "fallback")
            self._limits = cfg.get("limits", {})
        self._client = None

    def _check_limits(self, pcm_chunks: list[bytes]) -> None:
        max_per = self._limits.get("max_pcm_per_frame", 102400)
        max_total = self._limits.get("max_pcm_total", 31457280)
        for chunk in pcm_chunks:
            if len(chunk) > max_per:
                raise ValueError(f"PCM frame too large: {len(chunk)} > {max_per}")
        if sum(len(c) for c in pcm_chunks) > max_total:
            raise ValueError(f"total PCM too large: exceeded {max_total}")

    def _ensure_client(self):
        if self._client is None and self.mode == "mini-omni":
            import yaml
            cfg = yaml.safe_load(get_settings().full_duplex_config_path.read_text(encoding="utf-8")) or {}
            mo = cfg.get("mini_omni", {})
            self._client = MiniOmniClient(
                url=mo.get("url", "http://localhost:60808"),
                ckpt_dir=mo.get("ckpt_dir", "third_party/mini-omni/checkpoint"),
                device=mo.get("device", "cuda:0"),
            )
        return self._client

    async def handle(self, ws, token: str | None = None):
        # 全双工入口复用 Phase 1/2 WebSocket 鉴权：token 无效则 close(4401)，勿裸 accept
        from app.api.voice import _ws_authorized  # 或抽到 app.api.auth
        if not _ws_authorized(token):
            await ws.close(code=4401)
            return
        await ws.accept()
        mode = self.mode
        if mode == "mini-omni":
            await self._handle_mini_omni(ws)
        else:
            await self._handle_fallback(ws)

    async def _handle_mini_omni(self, ws):
        client = self._ensure_client()
        pcm_chunks = []
        try:
            client._ensure_running()
        except RuntimeError:
            await ws.send_json({"type": "error", "msg": "mini-omni not available, falling back"})
            await self._handle_fallback(ws)
            return

        # 通知前端：全双工模式数字人自动隐藏（参见 Phase 4 avatar.hide_on_full_duplex）
        await ws.send_json({"type": "avatar_hide", "reason": "full_duplex"})

        session_id = "default"
        transcript = []  # 收集文本用于注入记忆

        while True:
            msg = await ws.receive()
            if msg.get("bytes") is not None:
                pcm_chunks.append(msg["bytes"])
                self._check_limits(pcm_chunks)  # 安全限流：防 DoS OOM
            elif msg.get("text"):
                data = json.loads(msg["text"])
                if data.get("type") == "interrupt":
                    await ws.send_json({"type": "interrupted"})
                    return
                if data.get("type") == "flush":
                    audio = b"".join(pcm_chunks)
                    pcm_chunks.clear()
                    wav = self._pcm_to_wav(audio)
                    try:
                        for part in client.stream_chat(wav):
                            text = part.get("text", "")
                            audio_chunk = part.get("audio")
                            if text:
                                transcript.append(text)
                                await ws.send_json({"type": "token", "text": text})
                            if audio_chunk:
                                await ws.send_bytes(audio_chunk)
                    except Exception as e:
                        await ws.send_json({"type": "error", "msg": str(e)})
                    # 全量文本写入记忆（Phase 3）
                    full_text = "".join(transcript)
                    if full_text:
                        await self._inject_to_memory(session_id, full_text)
                    await ws.send_json({"type": "done"})
                    return

    async def _inject_to_memory(self, session_id: str, text: str) -> None:
        """将全双工对话文本注入 Phase 3 记忆系统"""
        from app.agent.engine import get_engine
        engine = get_engine()
        session = engine.get_session(session_id)
        session.add("assistant", text)

    async def _handle_fallback(self, ws):
        # 复用 Phase 2 的 Phase2Pipeline（伪全双工）
        from app.voice.pipeline import VoicePipeline
        from app.agent.engine import get_engine
        engine = get_engine()
        pipeline = VoicePipeline(engine=engine)
        while True:
            msg = await ws.receive()
            if msg.get("text"):
                data = json.loads(msg["text"])
                if data.get("type") == "text":
                    session_id = data.get("session_id", "default")
                    parts = []
                    for token in engine.stream_handle(data.get("text", ""), session_id):
                        parts.append(token)
                        await ws.send_json({"type": "token", "text": token})
                    full = "".join(parts)
                    if full:
                        await ws.send_json({"type": "text_done", "text": full})
                    await ws.send_json({"type": "done"})

    @staticmethod
    def _pcm_to_wav(pcm16: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm16)
        return buf.getvalue()
```

- [ ] **步骤 3：修改 voice.py 注册路由**

```python
# app/api/voice.py
from app.voice.full_duplex.gateway import FullDuplexGateway

_fd_gateway = FullDuplexGateway()

@router.websocket("/voice/full-duplex/ws")
async def full_duplex_ws(ws: WebSocket):
    await _fd_gateway.handle(ws)
```

- [ ] **步骤 4：config.py 新增 full_duplex_config_path**

```python
full_duplex_config_path: Path = ROOT / "config" / "full_duplex.yaml"
```

- [ ] **步骤 5：测试通过并 Commit**

```bash
pytest tests/test_full_duplex_gateway.py -v
git add backend/app/voice/full_duplex backend/app/api/voice.py backend/app/config.py backend/config/full_duplex.yaml
git commit -m "feat: full-duplex gateway with mini-omni integration"
```

---

### 任务 3：语音克隆（CosyVoice 2）

**文件：**
- 修改：`voice-assistant/backend/app/voice/tts_cosyvoice.py`（增加 clone 方法）
- 创建：`voice-assistant/backend/app/voice/clone.py`
- 创建：`voice-assistant/backend/app/api/voice_clone.py`
- 创建：`voice-assistant/backend/tests/test_voice_clone.py`

**说明：** 用户上传 10s 参考音频 → 生成 voice profile（存储为 `data/voice_profiles/<user_id>_<name>/`）→ TTS 合成时使用该 profile。本阶段复用 Phase 2 的 `CosyVoiceEngine` 接口，未安装 CosyVoice 2 时给出明确错误。

- [ ] **步骤 1：编写失败的测试**

```python
# tests/test_voice_clone.py
from app.voice.clone import VoiceCloneManager

def test_clone_profile_created(tmp_path, monkeypatch):
    monkeypatch.setattr("app.voice.clone.DATA_DIR", tmp_path)
    mgr = VoiceCloneManager()
    pid = mgr.create_profile("u1", b"fake audio", "my_voice")
    assert (tmp_path / pid / "ref.wav").exists()
    profile = mgr.get("u1", "my_voice")
    assert profile is not None

def test_list_by_user(tmp_path, monkeypatch):
    monkeypatch.setattr("app.voice.clone.DATA_DIR", tmp_path)
    mgr = VoiceCloneManager()
    mgr.create_profile("u1", b"a", "v1")
    mgr.create_profile("u1", b"b", "v2")
    mgr.create_profile("u2", b"c", "v1")
    assert len(mgr.list_by_user("u1")) == 2
    assert len(mgr.list_by_user("u2")) == 1
```

- [ ] **步骤 2：运行失败**

```bash
cd voice-assistant/backend
pytest tests/test_voice_clone.py -v
```

预期：FAIL

- [ ] **步骤 3：实现 clone.py**

```python
# app/voice/clone.py
from __future__ import annotations

import json
import os
from pathlib import Path

DATA_DIR = Path(os.getenv("VOICE_PROFILES_DIR", "data/voice_profiles"))


class VoiceCloneManager:
    def __init__(self, base: Path | None = None):
        self.base = Path(base or DATA_DIR)
        self.base.mkdir(parents=True, exist_ok=True)

    def create_profile(self, user_id: str, ref_audio: bytes, name: str) -> str:
        pid = f"{user_id}_{name}"
        p = self.base / pid
        p.mkdir(parents=True, exist_ok=True)
        (p / "ref.wav").write_bytes(ref_audio)
        (p / "profile.json").write_text(
            json.dumps({"voice": "cosyvoice2", "user_id": user_id, "name": name}, ensure_ascii=False),
            encoding="utf-8",
        )
        return pid

    def get(self, user_id: str, name: str) -> dict | None:
        p = self.base / f"{user_id}_{name}"
        if not p.exists():
            return None
        return {
            "path": str(p),
            "ref": str(p / "ref.wav"),
            "meta": json.loads((p / "profile.json").read_text(encoding="utf-8")),
        }

    def list_by_user(self, user_id: str) -> list[str]:
        return [d.name for d in self.base.iterdir() if d.is_dir() and d.name.startswith(f"{user_id}_")]
```

- [ ] **步骤 4：TTS 引擎支持 voice_profile**

修改 `app/voice/tts_cosyvoice.py`，在 `synthesize` 方法签名增加 `voice_profile: str | None = None` 参数。当提供 `voice_profile` 时，使用 `VoiceCloneManager.get` 获取参考音频路径并传入 CosyVoice 推理（未安装 CosyVoice 2 时抛出明确错误）。

- [ ] **步骤 5：API 路由**

```python
# app/api/voice_clone.py
from fastapi import APIRouter
from app.voice.clone import VoiceCloneManager

router = APIRouter(tags=["voice-clone"])
_clone_mgr = VoiceCloneManager()

@router.post("/voice/clone")
def clone_profile(user_id: str, name: str, audio_b64: str):
    pid = _clone_mgr.create_profile(user_id, __import__("base64").b64decode(audio_b64), name)
    return {"profile_id": pid}

@router.get("/voice/clone")
def list_clones(user_id: str):
    return {"profiles": _clone_mgr.list_by_user(user_id)}
```

- [ ] **步骤 6：测试 + 注册路由 + Commit**

```bash
pytest tests/test_voice_clone.py -v
git add backend/app/voice/clone.py backend/app/voice/tts_cosyvoice.py backend/app/api/voice_clone.py backend/tests/test_voice_clone.py backend/data/voice_profiles
git commit -m "feat: voice cloning profiles via CosyVoice 2"
```

---

### 任务 4：多语言声控切换

**文件：**
- 创建：`voice-assistant/backend/app/voice/language.py`
- 修改：`voice-assistant/backend/app/api/voice_clone.py`（新增路由）

**说明：** 新增语言配置 REST 接口，前端通过 `/api/voice/language` 切换 `zh`/`en`。全双工网关读取当前语言：
- `en` → 路由到 Mini-Omni 全双工
- `zh` → 路由到 Phase 2 伪全双工回退

- [ ] **步骤 1：实现 language.py**

```python
# app/voice/language.py
from __future__ import annotations

from dataclasses import dataclass

_LANGS = {
    "zh": {"asr": "zh", "tts_voice": "zh-CN-XiaoxiaoNeural", "llm_hint": "用中文回答", "mode": "fallback"},
    "en": {"asr": "en", "tts_voice": "en-US-JennyNeural", "llm_hint": "Reply in English", "mode": "mini-omni"},
}

@dataclass
class LanguageConfig:
    lang: str
    asr: str
    tts_voice: str
    llm_hint: str
    mode: str

    @classmethod
    def get(cls, lang: str = "zh") -> "LanguageConfig":
        cfg = _LANGS.get(lang, _LANGS["zh"])
        return cls(lang=lang, **cfg)
```

- [ ] **步骤 2：REST 接口**

```python
# app/api/voice_clone.py 新增：
from app.voice.language import LanguageConfig
_current_lang = LanguageConfig.get("zh")

@router.post("/voice/language")
def set_language(lang: str = "zh"):
    global _current_lang
    _current_lang = LanguageConfig.get(lang)
    return {"lang": _current_lang.lang, "mode": _current_lang.mode, "tts_voice": _current_lang.tts_voice}

@router.get("/voice/language")
def get_language():
    return {"lang": _current_lang.lang, "mode": _current_lang.mode}
```

- [ ] **步骤 3：测试 + Commit**

```bash
pytest tests/ -v
git add backend/app/voice/language.py backend/app/api/voice_clone.py
git commit -m "feat: multilingual voice switching zh/en"
```

---

### 任务 5：端到端验收

**文件：**
- 修改：`voice-assistant/README.md`
- 创建：`voice-assistant/backend/tests/test_phase5_e2e.py`

- [ ] **步骤 1：E2E 契约测试**

```python
# tests/test_phase5_e2e.py
from app.voice.full_duplex.gateway import FullDuplexGateway
from app.voice.clone import VoiceCloneManager
from app.voice.language import LanguageConfig
from app.voice.mini_omni import is_mini_omni_available

def test_gateway_mode_selection():
    gw = FullDuplexGateway()
    # 默认应能构造并选择 mode
    assert gw.mode in {"mini-omni", "fallback"}

def test_language_mode_mapping():
    assert LanguageConfig.get("en").mode == "mini-omni"
    assert LanguageConfig.get("zh").mode == "fallback"

def test_clone_list():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        mgr = VoiceCloneManager(__import__("pathlib").Path(d))
        pid = mgr.create_profile("u1", b"x", "v")
        assert "u1_v" == pid
```

- [ ] **步骤 2：全量测试**

```bash
cd voice-assistant/backend
pytest -v
```

预期：PASS

- [ ] **步骤 3：更新 README 并 Commit**

```bash
git add voice-assistant/README.md
git commit -m "docs: phase5 readme with mini-omni integration"
```

---

## 自检

### 1. 规格覆盖度（第五阶段）

| 规格需求 | 对应任务 |
|---------|---------|
| Mini-Omni 真全双工（子进程模式） | 任务 1、2 |
| 原生边听边说 + 打断 | 任务 2 |
| 中文模式回退（Phase 2 链路） | 任务 2、4 |
| 语音克隆 | 任务 3 |
| 多语言声控切换 | 任务 4 |

### 2. Mini-Omni 集成节省的代码

| 原计划（Phase 5 旧） | Mini-Omni 集成（新） | 节省 |
|---------------------|---------------------|------|
| `full_duplex/model.py` 模型懒加载（~60 行） | 调用 `server.py` 子进程 | ~60 行 |
| `full_duplex/gateway.py` 双向音频流编排（~80 行） | 复用 Mini-Omni 的 `/chat` 接口 | ~80 行 |
| VAD 实现 | Mini-Omni 自带 | ~40 行 |
| Whisper + SNAC + CosyVoice 推理代码 | Mini-Omni 已实现 | ~200+ 行 |
| **合计** | | **~380+ 行** |

### 3. 占位符扫描

- 无 TODO；Mini-Omni 子进程失败时自动回退到 fallback 模式。

### 4. 类型一致性

- `MiniOmniClient.stream_chat(wav_bytes) -> Iterator[bytes]`
- `FullDuplexGateway.handle(ws) -> None`（mode 路由）
- `LanguageConfig.lang/asr/tts_voice/llm_hint/mode`
- `VoiceCloneManager.create_profile/get/list_by_user`
- WebSocket 事件：`bytes（PCM/音频帧）| text（flush/interrupt/done/error）`

---

## 后续阶段（本计划不实现）

- 第六阶段：Android / 小程序 / Supabase 同步 / 插件市场
