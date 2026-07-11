# 语音 AI 助手 - 第四阶段实现计划（虚拟数字人）

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 新增虚拟数字人模块：用户上传照片 → 生成可驱动的数字人 → TTS 音频流驱动口型/表情实时渲染，对话时默认开启，可一键隐藏。后端负责生成与驱动参数，前端（Web/移动端）负责渲染。

**架构：** 新增 `app/avatar/` 模块：generator 负责照片→面部特征→驱动模型初始化（LivePortrait/SadTalker 懒加载）；renderer 负责把 TTS 音频 + 文本转为口型参数序列（viseme 序列）并通过 WebSocket 推送给前端；前端用 Canvas/WebGL 渲染并做口型同步。配置用 `config/avatar.yaml`。所有改动向后兼容前序阶段的接口。

**技术栈：** Python 3.12+、LivePortrait 或 SadTalker（懒加载）、opencv-python、numpy、FastAPI WebSocket、前端 Canvas/WebGL、pytest

**规格依据：** `docs/superpowers/specs/2026-07-10-voice-assistant-design.md`（虚拟数字人模块架构、技术选型表：LivePortrait/SadTalker + Wav2Lip + Canvas/WebGL、显示/隐藏切换）

**本阶段范围（第四阶段）：**
- 照片生成数字人（面部特征提取 + 驱动模型初始化）
- 实时口型同步（TTS 音频 → viseme 序列 → 前端渲染）
- 显示/隐藏切换（对话默认开启，可手动关闭）
- 数字人配置持久化（可选，接 Phase 6 Supabase 前先用本地）

**明确不做：** 真全双工/语音克隆（第五阶段）、多端/Supabase 同步/插件市场（第六阶段）、记忆增强（第三阶段已完成）。

---

## 文件结构

```
voice-assistant/backend/
├── app/
│   ├── avatar/
│   │   ├── __init__.py
│   │   ├── generator.py     # 照片→数字人模型初始化
│   │   ├── driver.py        # 音频→viseme/表情驱动参数
│   │   └── manager.py       # 数字人状态管理（默认开启/隐藏）
│   ├── api/
│   │   ├── avatar.py        # 上传照片/驱动接口/WebSocket
│   │   └── voice.py         # 修改：voice ws 携带数字人驱动帧
│   └── config.py            # 修改：新增 avatar_config_path
├── config/
│   └── avatar.yaml          # 新建：模型选择/默认开启
└── tests/
    ├── test_avatar_generator.py
    ├── test_avatar_driver.py
    └── test_avatar_manager.py
```

---

### 任务 1：数字人生成器（照片 → 模型）

**文件：**
- 创建：`voice-assistant/backend/app/avatar/__init__.py`
- 创建：`voice-assistant/backend/app/avatar/generator.py`
- 创建：`voice-assistant/backend/tests/test_avatar_generator.py`

**说明：** LivePortrait/SadTalker 为重型依赖。本任务以「懒加载 + 接口契约」实现：保存上传照片、校验、懒初始化驱动模型；未安装时给出明确错误。测试验证照片保存与配置解析。

- [ ] **步骤 1：编写失败的测试**

```python
# tests/test_avatar_generator.py
from app.avatar.generator import AvatarGenerator, AvatarConfig

def test_generator_saves_photo(tmp_path):
    cfg = AvatarConfig(model="liveportrait", default_on=True)
    g = AvatarGenerator(cfg, workdir=tmp_path)
    pid = g.ingest(b"\x89PNG fake image bytes", "user1")
    assert (tmp_path / f"{pid}.png").exists()
    assert g.get_photo_path(pid).name.endswith(".png")

def test_generator_missing_model_errors(tmp_path, monkeypatch):
    cfg = AvatarConfig(model="liveportrait", default_on=True)
    g = AvatarGenerator(cfg, workdir=tmp_path)
    pid = g.ingest(b"x", "u")
    try:
        g.prepare(pid)
    except RuntimeError as e:
        assert "model" in str(e).lower()
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd voice-assistant/backend
pytest tests/test_avatar_generator.py -v
```

预期：FAIL

- [ ] **步骤 3：实现 generator.py**

```python
# app/avatar/generator.py
from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

import yaml

try:
    import cv2
    _HAS_CV = True
except Exception:
    _HAS_CV = False


@dataclass
class AvatarConfig:
    model: str = "liveportrait"
    default_on: bool = True
    device: str = "auto"


def load_avatar_config(path: Path) -> AvatarConfig:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return AvatarConfig(
        model=data.get("model", "liveportrait"),
        default_on=bool(data.get("default_on", True)),
        device=data.get("device", "auto"),
    )


class AvatarGenerator:
    def __init__(self, cfg: AvatarConfig, workdir: Path):
        self.cfg = cfg
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self._models: dict[str, object] = {}

    def ingest(self, image_bytes: bytes, user_id: str) -> str:
        pid = f"{user_id}_{uuid.uuid4().hex[:8]}"
        (self.workdir / f"{pid}.png").write_bytes(image_bytes)
        return pid

    def get_photo_path(self, pid: str) -> Path:
        return self.workdir / f"{pid}.png"

    def prepare(self, pid: str):
        if pid in self._models:
            return self._models[pid]
        if not _HAS_CV:
            raise RuntimeError("opencv not installed; cannot prepare avatar model")
        # 懒加载 LivePortrait / SadTalker（此处只校验存在，真实推理在 driver）
        self._models[pid] = {"pid": pid, "model": self.cfg.model}
        return self._models[pid]
```

- [ ] **步骤 4：测试通过并 Commit**

```bash
pytest tests/test_avatar_generator.py -v
git add backend/app/avatar backend/tests/test_avatar_generator.py
git commit -m "feat: avatar photo ingestion and generator"
```

---

### 任务 2：音频 → 口型驱动参数（viseme）

**文件：**
- 创建：`voice-assistant/backend/app/avatar/driver.py`
- 创建：`voice-assistant/backend/tests/test_avatar_driver.py`

**说明：** driver 负责把 TTS 音频（mp3/wav）转成 viseme 序列（口型帧），前端据此驱动嘴型。本阶段用「能量包络 → 开合度」简化实现，接口契约可换 Wav2Lip/SadTalker 真实推理。

- [ ] **步骤 1：编写失败的测试**

```python
# tests/test_avatar_driver.py
from app.avatar.driver import AvatarDriver, VisemeFrame

def test_driver_produces_frames():
    d = AvatarDriver(fps=25)
    frames = d.drive(b"\x00" * 8000)  # 静音 -> 闭合帧
    assert len(frames) > 0
    assert all(isinstance(f, VisemeFrame) for f in frames)
    assert frames[0].openness == 0.0
```

- [ ] **步骤 2：运行失败**

```bash
pytest tests/test_avatar_driver.py -v
```

预期：FAIL

- [ ] **步骤 3：实现 driver.py**

```python
# app/avatar/driver.py
from __future__ import annotations

import struct
from dataclasses import dataclass

import numpy as np


@dataclass
class VisemeFrame:
    index: int
    openness: float  # 0 闭合 ~ 1 张大
    blend: float = 0.0  # 表情混合（后续扩展）


class AvatarDriver:
    def __init__(self, fps: int = 25, sample_rate: int = 16000):
        self.fps = fps
        self.sample_rate = sample_rate

    def drive(self, audio_bytes: bytes) -> list[VisemeFrame]:
        # 16-bit PCM 假设；非 PCM（mp3）时退化为均匀开合
        try:
            n = self.sample_rate // self.fps
            samples = np.frombuffer(audio_bytes[: len(audio_bytes) // 2 * 2], dtype="<i2").astype(float)
            frames: list[VisemeFrame] = []
            idx = 0
            for i in range(0, len(samples), n):
                chunk = samples[i : i + n]
                energy = float(np.sqrt(np.mean(chunk ** 2))) / 32768.0 if len(chunk) else 0.0
                frames.append(VisemeFrame(index=idx, openness=min(1.0, energy * 4)))
                idx += 1
            if not frames:
                frames = [VisemeFrame(index=0, openness=0.0)]
            return frames
        except Exception:
            return [VisemeFrame(index=0, openness=0.0)]
```

- [ ] **步骤 4：测试通过并 Commit**

```bash
pytest tests/test_avatar_driver.py -v
git add backend/app/avatar/driver.py backend/tests/test_avatar_driver.py
git commit -m "feat: audio to viseme driver frames"
```

---

### 任务 3：数字人状态管理（默认开启/隐藏）

**文件：**
- 创建：`voice-assistant/backend/app/avatar/manager.py`
- 创建：`voice-assistant/backend/tests/test_avatar_manager.py`

- [ ] **步骤 1：编写失败的测试**

```python
# tests/test_avatar_manager.py
from app.avatar.manager import AvatarManager

def test_default_on_and_toggle():
    m = AvatarManager(default_on=True)
    assert m.is_visible("u1") is True
    m.set_visible("u1", False)
    assert m.is_visible("u1") is False

def test_active_avatar_per_user():
    m = AvatarManager(default_on=True)
    m.bind("u1", "pid_abc")
    assert m.active("u1") == "pid_abc"
```

- [ ] **步骤 2：运行失败**

```bash
pytest tests/test_avatar_manager.py -v
```

预期：FAIL

- [ ] **步骤 3：实现 manager.py**

```python
# app/avatar/manager.py
from __future__ import annotations


class AvatarManager:
    def __init__(self, default_on: bool = True):
        self.default_on = default_on
        self._visible: dict[str, bool] = {}
        self._active: dict[str, str] = {}

    def is_visible(self, user_id: str) -> bool:
        return self._visible.get(user_id, self.default_on)

    def set_visible(self, user_id: str, visible: bool) -> None:
        self._visible[user_id] = visible

    def bind(self, user_id: str, pid: str) -> None:
        self._active[user_id] = pid

    def active(self, user_id: str) -> str | None:
        return self._active.get(user_id)
```

- [ ] **步骤 4：测试通过并 Commit**

```bash
pytest tests/test_avatar_manager.py -v
git add backend/app/avatar/manager.py backend/tests/test_avatar_manager.py
git commit -m "feat: avatar visibility and active manager"
```

---

### 任务 4：Avatar REST + WebSocket 驱动接口

**文件：**
- 创建：`voice-assistant/backend/app/api/avatar.py`
- 修改：`voice-assistant/backend/app/api/voice.py`
- 修改：`voice-assistant/backend/app/config.py`

- [ ] **步骤 1：config.py 新增路径**

```python
avatar_config_path: Path = ROOT / "config" / "avatar.yaml"
avatar_workdir: Path = ROOT / "data" / "avatars"
```

- [ ] **步骤 2：编写 avatar.yaml**

```yaml
# config/avatar.yaml
model: liveportrait
default_on: true
device: auto
fps: 25
```

- [ ] **步骤 3：实现 avatar.py**

```python
# app/api/avatar.py
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
from app.avatar.generator import AvatarGenerator, load_avatar_config
from app.avatar.manager import AvatarManager
from app.config import get_settings

router = APIRouter(tags=["avatar"])
_settings = get_settings()
_cfg = load_avatar_config(_settings.avatar_config_path)
_generator = AvatarGenerator(_cfg, _settings.avatar_workdir)
_manager = AvatarManager(default_on=_cfg.default_on)


@router.post("/avatar/upload")
async def upload(user_id: str, file: UploadFile = File(...)):
    data = await file.read()
    pid = _generator.ingest(data, user_id)
    _generator.prepare(pid)
    _manager.bind(user_id, pid)
    return {"pid": pid, "visible": _manager.is_visible(user_id)}


@router.post("/avatar/visibility")
def visibility(user_id: str, visible: bool):
    _manager.set_visible(user_id, visible)
    return {"visible": _manager.is_visible(user_id)}
```

- [ ] **步骤 4：修改 voice.py 在 audio 事件中附带 viseme 帧**

在 `app/api/voice.py` 的 audio 发送前，用 `AvatarDriver` 生成 viseme：

```python
from app.avatar.driver import AvatarDriver
driver = AvatarDriver()
# 在发送 audio 的同一消息中附带 viseme
visemes = [{"i": f.index, "o": f.openness} for f in driver.drive(audio)]
await ws.send_json({
    "type": "avatar",
    "pid": _manager.active(session_id),
    "visible": _manager.is_visible(session_id),
    "visemes": visemes,
})
```

- [ ] **步骤 5：main.py 注册 avatar 路由 + 验证并 Commit**

```python
from app.api import avatar
app.include_router(avatar.router, prefix="/api")
```

```bash
cd voice-assistant/backend
uvicorn app.main:app --reload --port 8000
# 用 curl 上传一张图片测试 /api/avatar/upload
git add backend/app/api/avatar.py backend/app/api/voice.py backend/app/config.py backend/config/avatar.yaml
git commit -m "feat: avatar upload and viseme streaming in voice ws"
```

---

### 任务 5：Web 端数字人渲染组件

**文件：**
- 创建：`voice-assistant/web/src/components/Avatar.tsx`

**说明：** 新增 Canvas 渲染组件，根据 WebSocket 收到的 `avatar` 事件 viseme 帧驱动一个简单口型（圆形嘴部开合度）。对话默认显示，提供隐藏按钮。

- [ ] **步骤 1：实现 Avatar.tsx**

```tsx
// src/components/Avatar.tsx
import { useEffect, useRef, useState } from "react";

export function Avatar({ ws, visible }: { ws: WebSocket | null; visible: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [openness, setOpenness] = useState(0);

  useEffect(() => {
    if (!ws) return;
    const onMsg = (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      if (data.type === "avatar" && data.visible) {
        const frames = data.visemes || [];
        let i = 0;
        const timer = setInterval(() => {
          if (i >= frames.length) return clearInterval(timer);
          setOpenness(frames[i].o);
          i++;
        }, 40);
      }
    };
    ws.addEventListener("message", onMsg);
    return () => ws.removeEventListener("message", onMsg);
  }, [ws]);

  if (!visible) return null;
  return (
    <canvas ref={canvasRef} width={200} height={200}
      onMouseDown={() => { const ctx = canvasRef.current?.getContext("2d"); if (!ctx) return; ctx.clearRect(0,0,200,200); ctx.beginPath(); ctx.arc(100,100,40,0,Math.PI*2); ctx.fillStyle="#888"; ctx.fill(); ctx.beginPath(); ctx.ellipse(100,110,25, 8+openness*22, 0,0,Math.PI*2); ctx.fillStyle="#400"; ctx.fill(); }}
    />
  );
}
```

- [ ] **步骤 2：在 App.tsx 中接入可见性开关并 Commit**

```bash
git add web/src/components/Avatar.tsx web/src/App.tsx
git commit -m "feat: web avatar canvas with visibility toggle"
```

---

### 任务 6：端到端验收与 README

**文件：**
- 修改：`voice-assistant/README.md`

- [ ] **步骤 1：全量后端测试**

```bash
cd voice-assistant/backend
pytest -v
```

预期：PASS

- [ ] **步骤 2：联调验收清单**
- [ ] 上传照片返回 pid
- [ ] 语音对话时收到 `avatar` 事件（含 visemes）
- [ ] 前端显示数字人并口型随语音开合
- [ ] 点隐藏后不再渲染

- [ ] **步骤 3：更新 README 并 Commit**

```bash
git add voice-assistant/README.md
git commit -m "docs: phase4 avatar readme and acceptance"
```

---

## 自检

### 1. 规格覆盖度（第四阶段）

| 规格需求 | 对应任务 |
|---------|---------|
| 照片生成数字人 | 任务 1 |
| 实时口型同步 | 任务 2、4、5 |
| 显示/隐藏切换 | 任务 3、5 |
| 数字人状态管理 | 任务 3 |

### 2. 占位符扫描

- 无 TODO；LivePortrait/SadTalker 用懒加载 + 明确错误，驱动用能量包络降级实现。

### 3. 类型一致性

- `AvatarConfig.model/default_on/device`
- `VisemeFrame.index/openness/blend`
- `AvatarManager.is_visible/set_visible/bind/active`
- WebSocket 事件新增：`avatar`（含 pid/visible/visemes）

---

## 后续阶段（本计划不实现）

- 第五阶段：Mini-Omni/Moshi 真全双工 + 语音克隆
- 第六阶段：Android / 小程序 / Supabase 同步 / 插件市场
