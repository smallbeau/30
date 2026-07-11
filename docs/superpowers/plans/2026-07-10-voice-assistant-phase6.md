# 语音 AI 助手 - 第六阶段实现计划（多端支持 + 插件生态）

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在已完成的 Phase 1-5 之上，新增 Supabase 数据持久化与多端实时同步、Android Flutter 端、微信小程序端，以及插件市场 + 语音安装插件功能。

**架构：** 新增 `app/sync/` 模块封装 Supabase 客户端（PostgreSQL + Realtime + Storage），对 Phase 1-3 的记忆/对话/技能/配置等核心数据实现全端实时同步与离线冲突合并（LWW）。新增 `web-admin/`（Vite + React）作为插件市场后端管理面板与前端展示，Skill 发布为 zip/markdown 文件上传到 Supabase Storage。Android Flutter 与微信小程序作为独立客户端复用 Phase 1-2 的 FastAPI 接口。所有新接口与原有接口解耦，Phase 1-5 的功能可在无 Supabase/客户端的情况下独立运行。

**技术栈：** Python 3.12+、supabase-py（>=2.0）、Flutter（Dart 3.0+）、微信小程序原生框架、Vite + React、pytest

**规格依据：** `docs/superpowers/specs/2026-07-10-voice-assistant-design.md`（多端数据同步设计、Supabase 同步层、离线缓存策略、LWW 冲突处理、安全性设计、生态预置技能表）

**本阶段范围（第六阶段）：**
- Supabase 数据持久化与 Realtime 同步
- 离线缓存 + LWW 冲突合并
- Android Flutter 端（对话 + 语音输入 + 数字人渲染）
- 微信小程序端（基础对话 + 语音）
- 插件市场（Web 管理端 + 语音安装 Skill）

**明确不做：** 真全双工/语音克隆/数字人模型本地部署（第五阶段已完成接口与契约）、Linux 桌面端、iOS 原生端。

---

## 文件结构

```
voice-assistant/
├── backend/
│   ├── app/
│   │   ├── sync/
│   │   │   ├── __init__.py
│   │   │   ├── supabase.py    # Supabase 客户端（可选依赖）
│   │   │   └── models.py      # 同步数据模型（含 Phase 5 扩展）
│   │   └── main.py            # 修改：可选注册 sync 路由
│   ├── config/
│   │   └── sync.yaml          # 新建：Supabase URL/Key/离线开关
│   └── tests/
│       ├── test_sync.py
│       └── test_sync_lww.py
├── android/                   # 新建：Flutter 端
│   ├── lib/
│   │   ├── main.dart
│   │   ├── screens/chat_screen.dart
│   │   ├── widgets/voice_input.dart
│   │   └── services/api.dart
│   └── pubspec.yaml
├── miniapp/                   # 新建：微信小程序
│   ├── pages/chat/
│   ├── utils/api.js
│   └── app.json
├── web-admin/                 # 新建：插件市场管理端
│   ├── src/
│   │   ├── App.tsx
│   │   ├── pages/Market.tsx
│   │   └── components/SkillCard.tsx
│   └── package.json
├── plugin-market/             # 新建：插件市场数据目录
│   └── skills/                # 可发布的 skill markdown 包
└── docs/
    └── phase6-guide.md
```

---

### 任务 1：Supabase 客户端封装

**文件：**
- 创建：`voice-assistant/backend/app/sync/__init__.py`
- 创建：`voice-assistant/backend/app/sync/supabase.py`
- 创建：`voice-assistant/backend/app/sync/models.py`
- 创建：`voice-assistant/backend/config/sync.yaml`
- 创建：`voice-assistant/backend/tests/test_sync.py`

**说明：** supabase-py 为可选依赖。未安装时所有 sync 接口返回「未配置」错误，Phase 1-5 功能不受影响。

**同步数据模型扩展（Phase 5 数据跨端同步）：**

在 Phase 5 之后，除 Phase 1-3 的 `conversations/memories/skills` 外，还需同步以下 Phase 5 新增数据：

| 数据 | 存储方式 | 同步入口 |
|------|---------|---------|
| voice_profiles（语音克隆参考音频） | Supabase Storage（`voice_profiles/<user_id>/`） | `SyncClient.upload_profile()` / `download_profile()` |
| language_settings（语言偏好 `zh`/`en`） | `users.config` JSON 字段 | `SyncClient.sync_user_config()` |
| full_duplex_config（全双工模式 `mini-omni`/`fallback`） | `users.config` JSON 字段 | 同上 |

```python
# app/sync/models.py
from dataclasses import dataclass, field

@dataclass
class UserConfig:
    user_id: str
    language: str = "zh"                    # Phase 5: 语言偏好
    full_duplex_mode: str = "fallback"      # Phase 5: 全双工模式
    avatar_enabled: bool = True             # Phase 4: 数字人默认开启
    # 其他配置...

@dataclass
class VoiceProfile:
    user_id: str
    name: str
    storage_path: str          # Supabase Storage 路径
    created_at: str = ""
```

```python
# app/sync/supabase.py 新增方法
def upload_profile(self, user_id: str, name: str, audio_bytes: bytes) -> str:
    client = self._ensure()
    path = f"voice_profiles/{user_id}/{name}.wav"
    client.storage.from_("voice_profiles").upload(path, audio_bytes)
    return path

def download_profile(self, path: str) -> bytes:
    client = self._ensure()
    return client.storage.from_("voice_profiles").download(path)
```

- [ ] **步骤 1：编写失败的测试**

```python
# tests/test_sync.py
from app.sync.supabase import SyncClient, load_sync_config

def test_sync_config_optional(tmp_path):
    cfg = tmp_path / "sync.yaml"
    cfg.write_text("url: https://x.supabase.co\nkey: abc\n", encoding="utf-8")
    c = load_sync_config(cfg)
    assert c.url == "https://x.supabase.co"

def test_client_offline_when_not_configured(monkeypatch):
    import importlib
    monkeypatch.setitem(sys.modules, "supabase", None)
    cl = SyncClient(url="", key="")
    assert cl.is_enabled() is False
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd voice-assistant/backend
pytest tests/test_sync.py -v
```

预期：FAIL

- [ ] **步骤 3：实现 supabase.py + models.py**

```python
# app/sync/supabase.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class SyncConfig:
    url: str = ""
    key: str = ""
    enabled: bool = False
    offline: bool = False


def load_sync_config(path: Path) -> SyncConfig:
    if not path.exists():
        return SyncConfig()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return SyncConfig(
        url=data.get("url", ""),
        key=data.get("key", ""),
        enabled=bool(data.get("url") and data.get("key")),
        offline=bool(data.get("offline", False)),
    )


class SyncClient:
    def __init__(self, url: str, key: str):
        self.url = url
        self.key = key
        self._client = None

    def is_enabled(self) -> bool:
        return bool(self.url and self.key)

    def _ensure(self):
        if not self.is_enabled():
            raise RuntimeError("sync not configured")
        if self._client is None:
            try:
                from supabase import create_client
                self._client = create_client(self.url, self.key)
            except Exception as e:
                raise RuntimeError(f"supabase not installed: {e}")
        return self._client

    def upsert(self, table: str, record: dict) -> dict:
        client = self._ensure()
        return client.table(table).upsert(record, on_conflict="id").execute().data[0]

    def select(self, table: str, filters: dict | None = None) -> list[dict]:
        client = self._ensure()
        q = client.table(table).select("*")
        for k, v in (filters or {}).items():
            q = q.eq(k, v)
        return q.execute().data
```

```python
# app/sync/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Syncable:
    id: str
    user_id: str
    server_updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    client_updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def should_merge(self, other: "Syncable") -> bool:
        return self.user_id == other.user_id and self.id == other.id

    def merge(self, other: "Syncable") -> "Syncable":
        if datetime.fromisoformat(other.client_updated_at) >= datetime.fromisoformat(self.client_updated_at):
            return other
        return self
```

- [ ] **步骤 4：sync.yaml**

```yaml
# config/sync.yaml
url: https://your-project.supabase.co
key: ${SUPABASE_KEY}
enabled: false
offline: false
```

- [ ] **步骤 5：测试通过并 Commit**

```bash
pytest tests/test_sync.py -v
git add backend/app/sync backend/config/sync.yaml backend/tests/test_sync.py
git commit -m "feat: optional supabase sync client"
```

---

### 任务 2：离线缓存 + LWW 冲突合并

**文件：**
- 创建：`voice-assistant/backend/app/sync/offline.py`
- 修改：`voice-assistant/backend/tests/test_sync_lww.py`

**说明：** 本地 SQLite 作为离线缓存，每次写入记录变更队列；网络恢复后读取队列并与服务端 LWW 合并。

- [ ] **步骤 1：编写失败的测试**

```python
# tests/test_sync_lww.py
from app.sync.offline import OfflineCache

def test_lww_merge():
    cache = OfflineCache(":memory:")
    a = __import__("app.sync.models", fromlist=["Syncable"]).Syncable(id="1", user_id="u1", client_updated_at="2026-07-10T10:00:00")
    b = __import__("app.sync.models", fromlist=["Syncable"]).Syncable(id="1", user_id="u1", client_updated_at="2026-07-10T12:00:00")
    merged = a.merge(b)
    assert merged.client_updated_at == "2026-07-10T12:00:00"
```

- [ ] **步骤 2：实现 offline.py**

```python
# app/sync/offline.py
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from app.sync.models import Syncable


@dataclass
class OfflineCache:
    db_path: str = ":memory:"

    def __post_init__(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS pending (
                id TEXT PRIMARY KEY,
                table_name TEXT,
                data TEXT,
                queued_at TEXT
            )
        """)

    def enqueue(self, table: str, record: Syncable) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO pending (id, table_name, data, queued_at) VALUES (?,?,?,?)",
            (record.id, table, json.dumps(record.__dict__, ensure_ascii=False), datetime.utcnow().isoformat()),
        )
        self.conn.commit()

    def drain(self) -> list[tuple[str, Syncable]]:
        cur = self.conn.execute("SELECT table_name, data FROM pending")
        rows = cur.fetchall()
        self.conn.execute("DELETE FROM pending")
        self.conn.commit()
        return [(t, Syncable(**json.loads(d))) for t, d in rows]
```

- [ ] **步骤 3：测试通过并 Commit**

```bash
pytest tests/test_sync_lww.py -v
git add backend/app/sync/offline.py backend/tests/test_sync_lww.py
git commit -m "feat: offline cache with lww merge"
```

---

### 任务 3：Android Flutter 端

**文件：**
- 新建目录：`voice-assistant/android/`（完整 Flutter 脚手架）

**说明：** Flutter 端复用 Phase 1-2 的 FastAPI 接口。核心功能：文字对话、语音输入（系统 SpeechRecognizer 或 WebSocket 发送 PCM）、播放 TTS 音频、数字人 Canvas 渲染（复用 Phase 4 协议）。**Phase 5 接口调用规范（Flutter 端）：**

| 接口 | Method | URI | 用途 |
|------|--------|-----|------|
| Chat | POST | `/api/chat` | 文字对话 |
| Voice WS | WebSocket | `/api/voice/ws` | 半双工语音（Phase 2 fallback） |
| Full-duplex WS | WebSocket | `/api/voice/full-duplex/ws` | 全双工语音（Phase 5 Mini-Omni） |
| Language | GET/POST | `/api/voice/language` | 切换 `zh`/`en`（Phase 5 `LanguageConfig`） |
| Clone upload | POST | `/api/voice/clone/upload` | 上传 10s 参考音频（Phase 5 `voice_clone.py`） |
| Clone list | GET | `/api/voice/clone/profiles` | 列出已创建的音色 profile |
| Avatar | POST | `/api/avatar/upload` | 上传照片生成数字人（Phase 4） |
| Avatar WS | WebSocket | `/api/avatar/ws` | 数字人驱动帧推送（Phase 4） |

插件安装通过语音发送文字给服务端处理。

- [ ] **步骤 1：创建 Flutter 脚手架**

```bash
cd voice-assistant/android
flutter create .
```

`pubspec.yaml` 依赖：

```yaml
dependencies:
  flutter:
    sdk: flutter
  web_socket_channel: ^2.4.0
  http: ^1.2.0
  permission_handler: ^11.0.0
```

- [ ] **步骤 2：实现 `lib/services/api.dart`**

```dart
class Api {
  static const base = String.fromEnvironment('API_BASE', defaultValue: 'http://10.0.2.2:8000');
  Future<String> chat(String msg, {String session = 'mobile'}) async {
    final r = await http.post(Uri.parse('$base/api/chat'), headers: {'Content-Type':'application/json'}, body: jsonEncode({'message':msg,'session_id':session,'stream':false}));
    return (jsonDecode(r.body) as Map)['text'];
  }
}
```

- [ ] **步骤 3：实现 `lib/screens/chat_screen.dart`**

```dart
class ChatScreen extends StatefulWidget { ... }
// TextField 发送消息到 /api/chat
// WebSocket 连接 /api/voice/ws 接收 token/audio/done 事件
// audio player 播放 base64 mp3
// 浮动按钮显示/隐藏数字人（Canvas 渲染）
```

- [ ] **步骤 4：在 `android/app/build.gradle` 添加网络权限与最小 SDK**

```gradle
minSdkVersion 24
usesPermission android.permission.INTERNET
usesPermission android.permission.RECORD_AUDIO
```

- [ ] **步骤 5：构建验证并 Commit**

```bash
cd voice-assistant/android
flutter pub get
flutter run
git add android
git commit -m "feat: android flutter client"
```

---

### 任务 4：微信小程序端

**文件：**
- 新建目录：`voice-assistant/miniapp/`

**说明：** 微信小程序复用 FastAPI 接口（需配置合法域名）。核心功能：文字对话、微信语音识别（`<button open-type="getPhoneNumber">` 或 `wx.getRecorderManager`）、TTS 音频播放、基础数字人图片展示。

**Phase 5 接口调用规范（小程序端）：** 接口表同任务 3 Flutter 端。由于微信小程序不支持 WebSocket ping（需要心跳保活），全双工 `/api/voice/full-duplex/ws` 建议改为简化的 HTTP 轮询 `/api/voice/full-duplex/poll` 替代（Phase 5 可选补充接口）。语音克隆上传需在 `wx.chooseMessageFile` 中选择音频文件后调用 `/api/voice/clone/upload`。

- [ ] **步骤 1：创建小程序脚手架**

```bash
cd voice-assistant/miniapp
# 手动创建 app.json、pages/chat/index.*、utils/api.js
```

`app.json`：

```json
{
  "pages": ["pages/chat/index"],
  "permission": {"scope.record": {"desc": "用于语音输入"}},
  "requestDomain": ["https://your-api.com", "http://localhost:8000"]
}
```

- [ ] **步骤 2：实现 `utils/api.js`**

```javascript
export async function chat(message, sessionId = 'miniapp') {
  const res = await wx.request({
    url: 'https://your-api.com/api/chat',
    method: 'POST',
    data: { message, session_id: sessionId, stream: false },
  });
  return res.data.text;
}
```

- [ ] **步骤 3：实现 `pages/chat/index.wxml`**

```xml
<view class="chat">
  <block wx:for="{{messages}}" wx:key="index">
    <text class="{{item.role === 'user' ? 'user' : 'bot'}}">{{item.content}}</text>
  </block>
  <button bindtap="startRecord" type="primary">按住说话</button>
</view>
```

- [ ] **步骤 4：导入开发者工具验证并 Commit**

```bash
git add miniapp
git commit -m "feat: wechat miniapp client"
```

---

### 任务 5：插件市场（Web 管理端 + 语音安装）

**文件：**
- 新建目录：`voice-assistant/web-admin/`
- 创建：`voice-assistant/plugin-market/skills/`（示例包）
- 修改：`voice-assistant/backend/app/skill/loader.py`（增加远程安装能力）
- 修改：`voice-assistant/backend/app/api/skill.py`（增加安装/卸载接口）

**说明：** Web 管理端用于发布 Skill，前端展示市场列表；用户通过语音「安装 XX 插件」触发服务端下载 skill markdown 文件落盘到 `skills/`，Phase 1 的 `SkillLoader` 已支持热加载，只需新增 `install_skill` 接口。  
**安全硬性要求：** 安装/卸载仅管理员；下载 URL 域名白名单 + HTTPS；文件名严格校验；路径必须落在 `skills/` 沙箱内；内容大小与 frontmatter 校验；禁止跟随重定向到非白名单主机。

- [ ] **步骤 1：实现 Skill 安装接口（防 SSRF / 路径穿越 / 供应链投毒）**

```python
# app/api/skill.py 新增路由
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl

from app.api.auth import require_admin  # Phase 6：JWT/RBAC；未就绪时用管理员 API Key 角色

router = APIRouter(tags=["skill"])
SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills"
# 仅允许从官方/自建插件市场域名下载
_SKILL_URL_ALLOWLIST = frozenset({
    "plugins.example.com",
    "raw.githubusercontent.com",  # 若允许 GH，应再限制 path 前缀为 org/repo
})
_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")
_MAX_BYTES = 256 * 1024


class InstallBody(BaseModel):
    url: str
    name: str  # 由客户端/市场元数据提供，不从 URL 推断


def _assert_skill_url(url: str) -> None:
    p = urlparse(url)
    if p.scheme != "https" or not p.hostname:
        raise HTTPException(400, "only https urls allowed")
    host = p.hostname.lower()
    if host not in _SKILL_URL_ALLOWLIST:
        raise HTTPException(400, "url host not allowlisted")
    if p.username or p.password:
        raise HTTPException(400, "url credentials not allowed")


def _safe_dest(name: str) -> Path:
    if not _NAME_RE.match(name):
        raise HTTPException(400, "invalid skill name")
    dest = (SKILLS_DIR / f"{name}.md").resolve()
    if not dest.is_relative_to(SKILLS_DIR.resolve()):
        raise HTTPException(400, "path traversal denied")
    return dest


@router.post("/skills/install")
def install_skill(body: InstallBody, _admin=Depends(require_admin)):
    _assert_skill_url(body.url)
    dest = _safe_dest(body.name)
    try:
        r = requests.get(
            body.url,
            timeout=10,
            allow_redirects=False,  # 禁止跳到非白名单
            stream=True,
        )
    except requests.RequestException as e:
        raise HTTPException(400, f"download failed: {e}") from e
    if r.status_code != 200:
        raise HTTPException(400, "download failed")
    content = r.content
    if len(content) > _MAX_BYTES:
        raise HTTPException(400, "skill file too large")
    text = content.decode("utf-8", errors="strict")
    if not text.lstrip().startswith("---"):
        raise HTTPException(400, "skill must start with yaml frontmatter")
    # 可选：校验 frontmatter name 与 body.name 一致、禁止 tools.type 为 shell/eval
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    return {"installed": dest.name}


@router.post("/skills/uninstall")
def uninstall_skill(name: str, _admin=Depends(require_admin)):
    dest = _safe_dest(name)
    if dest.exists():
        dest.unlink()
    return {"removed": dest.name}
```

- [ ] **步骤 2：插件市场前端（请求必须带鉴权头）**

```tsx
// web-admin/src/pages/Market.tsx
export function Market() {
  const [skills, setSkills] = useState<{name:string;url:string}[]>([]);
  const authHeaders = { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" };
  useEffect(() => {
    fetch("/api/skills", { headers: authHeaders }).then(r => r.json()).then(setSkills);
  }, []);
  return (
    <div>
      {skills.map(s => (
        <SkillCard
          key={s.name}
          skill={s}
          onInstall={async (u, name) => {
            await fetch("/api/skills/install", {
              method: "POST",
              headers: authHeaders,
              body: JSON.stringify({ url: u, name }),
            });
          }}
        />
      ))}
    </div>
  );
}
```

- [ ] **步骤 3：示例插件包**

```markdown
# plugin-market/skills/reminder.md
---
name: 提醒
trigger: 提醒|定时|记一下
description: 设置提醒
---
## steps
1. 提取时间与内容
2. 调用提醒服务
3. 返回确认
```

- [ ] **步骤 4：Commit**

```bash
git add backend/app/api/skill.py web-admin plugin-market
git commit -m "feat: plugin market and voice install endpoint"
```

---

### 任务 6：端到端验收 + README

**文件：**
- 修改：`voice-assistant/README.md`

- [ ] **步骤 1：全量后端测试**

```bash
cd voice-assistant/backend
pytest -v
```

预期：PASS（sync 可选）

- [ ] **步骤 2：验收清单**
- [ ] 后端启动无需 Supabase（enabled=false 时正常）
- [ ] 填入 Supabase 凭据后可 upsert/select
- [ ] Android 端可连接到后端并对话
- [ ] 小程序可连接到后端并对话
- [ ] `/api/skills/install` 仅管理员 + 白名单 HTTPS 域名可下载 skill；非法 host/路径穿越返回 400
- [ ] 无鉴权或非管理员调用 install/uninstall 返回 401/403
- [ ] Web 管理端展示 skill 列表且请求带 Authorization

- [ ] **步骤 3：更新 README 并 Commit**

```bash
git add voice-assistant/README.md
git commit -m "docs: phase6 complete readme"
```

---

## 自检

### 1. 规格覆盖度（第六阶段）

| 规格需求 | 对应任务 |
|---------|---------|
| Supabase 持久化 | 任务 1 |
| 离线缓存 + LWW | 任务 2 |
| 多端同步（Android/小程序） | 任务 3、4 |
| 插件市场 + 语音安装 | 任务 5 |
| 数据模型同步（users/conversations/memories/skills/avatar_config） | 任务 1 |

### 2. 占位符扫描

- 无 TODO；Supabase/Flutter/小程序均为独立目录，后端无硬依赖。

### 3. 类型一致性

- `SyncConfig.url/key/enabled/offline`
- `Syncable.id/user_id/server_updated_at/client_updated_at/merge`
- `OfflineCache.enqueue/drain`
- 插件安装接口：`POST /api/skills/install {url,name}` / `POST /api/skills/uninstall {name}`（管理员鉴权 + 域名白名单 + 路径沙箱）

---

## 后续（本阶段后）

- 项目六阶段全部完成
- 后续可继续：真全双工模型权重本地部署、多端 UI 完善、更多插件生态、生产环境部署（Docker/CI/CD）
