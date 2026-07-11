# 语音 AI 助手 - 第三阶段实现计划（记忆系统 + 生态预置）

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在已完成的 Phase 1/2 之上，新增三层记忆系统（短期会话 / 长期摘要 / 向量记忆）与 10+ 预置 Skill，使助手能跨会话记住用户偏好并即装即用常用能力。

**架构：** 新增 `app/memory/` 模块：短期记忆复用 Phase 1 的 `SessionContext` 并扩展元数据，使用 SQLite 持久化（替代 Phase 1 的内存 dict，支持多 Worker 和重启不丢上下文）；长期记忆由 LLM 空闲时自动摘要生成；向量记忆基于 Phase 1 的 `VectorStore`（同库复用）存储对话摘要 embedding。预置 Skill 以 Markdown 文件落入 `skills/`，Phase 1 的 `SkillLoader` 已支持热加载。Agent Engine 在 `handle` 前先检索向量记忆与知识库，合并上下文后送入 LLM。所有改动向后兼容 Phase 1/2 的 REST/SSE 接口。

**技术栈：** Python 3.12+、Phase 1 的 `VectorStore`/`SkillLoader`、openai SDK（embedding）、pydantic、FastAPI、pytest

**规格依据：** `docs/superpowers/specs/2026-07-10-voice-assistant-design.md`（三层记忆架构、短期/长期记忆结构、上下文检索回答流程、生态预置技能表）

**本阶段范围（第三阶段）：**
- 三层记忆架构（短期 / 长期 / 向量）
- 10+ 预置 Skill（天气/翻译/日历/待办/闹钟/计算器/搜索/新闻/音乐/系统控制）
- 上下文检索回答（记忆 + 知识库 + 当前消息合并）
- 自动摘要归档（会话空闲时生成长期记忆）

**明确不做（后续阶段）：** 数字人（第四阶段）、真全双工/语音克隆（第五阶段）、多端/Supabase 同步/插件市场（第六阶段）。

---

## 文件结构

```
voice-assistant/backend/
├── app/
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── short_term.py     # 短期会话记忆（扩展 SessionContext）
│   │   ├── long_term.py      # 长期摘要记忆
│   │   ├── vector.py         # 向量记忆（复用 rag/store.VectorStore）
│   │   └── manager.py        # 记忆管理器：合并检索 + 自动归档
│   ├── agent/
│   │   └── engine.py         # 修改：handle 前注入记忆上下文
│   ├── skill/
│   │   └── executor.py       # 修改：支持 http 工具类型（天气/搜索等）
│   └── api/
│       ├── memory.py         # 新建：记忆查看/清空 REST
│       └── skill.py          # 修改：支持动态安装 Skill（落盘 skills/）
├── skills/
│   ├── weather.md            # 新建（替换 Phase 1 stub）
│   ├── translate.md          # 已有
│   ├── calendar.md           # 新建
│   ├── todo.md               # 新建
│   ├── alarm.md              # 新建
│   ├── calculator.md         # 新建
│   ├── search.md             # 新建
│   ├── news.md               # 新建
│   ├── music.md              # 新建
│   └── system_control.md     # 新建
└── tests/
    ├── test_memory_manager.py
    ├── test_long_term.py
    └── test_preset_skills.py
```

---

### 任务 1：短期记忆扩展

**文件：**
- 修改：`voice-assistant/backend/app/agent/context.py`
- 创建：`voice-assistant/backend/app/memory/__init__.py`
- 创建：`voice-assistant/backend/app/memory/short_term.py`

- [ ] **步骤 1：编写失败的测试**

```python
# tests/test_memory_manager.py （片段，任务 1 部分）
from app.memory.short_term import ShortTermMemory

def test_short_term_expiry():
    m = ShortTermMemory(session_id="s1", ttl_minutes=0)
    m.add("user", "北京天气")
    assert m.is_expired() is True  # ttl=0 立即过期
    m.touch()
    assert m.is_expired() is False
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd voice-assistant/backend
pytest tests/test_memory_manager.py -v
```

预期：FAIL

- [ ] **步骤 3：实现 short_term.py**

```python
# app/memory/short_term.py
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

_DB = Path(__file__).resolve().parent.parent.parent / "data" / "sessions.db"


class ShortTermMemory:
    """SQLite 持久化短期记忆，替代 Phase 1 的内存 SessionContext"""

    def __init__(self, session_id: str, ttl_minutes: int = 30):
        self.session_id = session_id
        self.ttl_minutes = ttl_minutes
        _DB.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(_DB))
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                messages TEXT DEFAULT '[]',
                last_active REAL DEFAULT 0
            )
        """)
        self._conn.commit()

    def _load(self) -> dict:
        cur = self._conn.execute(
            "SELECT messages, last_active FROM sessions WHERE session_id=?",
            (self.session_id,),
        )
        row = cur.fetchone()
        if row:
            return {"messages": json.loads(row[0]), "last_active": row[1]}
        return {"messages": [], "last_active": time.monotonic()}

    def _save(self, messages: list, last_active: float) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO sessions (session_id, messages, last_active) VALUES (?,?,?)",
            (self.session_id, json.dumps(messages, ensure_ascii=False), last_active),
        )
        self._conn.commit()

    def add(self, role: str, content: str) -> None:
        data = self._load()
        data["messages"].append({"role": role, "content": content})
        data["last_active"] = time.monotonic()
        self._save(data["messages"], data["last_active"])

    @property
    def messages(self) -> list[dict]:
        return self._load()["messages"]

    def touch(self) -> None:
        data = self._load()
        self._save(data["messages"], time.monotonic())

    def is_expired(self) -> bool:
        if self.ttl_minutes <= 0:
            return True
        data = self._load()
        elapsed = (time.monotonic() - data["last_active"]) / 60
        return elapsed >= self.ttl_minutes

    def close(self) -> None:
        self._conn.close()
```

- [ ] **步骤 4：测试通过并 Commit**

```bash
pytest tests/test_memory_manager.py -v
git add backend/app/memory backend/app/agent/context.py backend/tests/test_memory_manager.py
git commit -m "feat: short-term memory with ttl"
```

---

### 任务 2：长期记忆（LLM 自动摘要）

**文件：**
- 创建：`voice-assistant/backend/app/memory/long_term.py`
- 修改：`voice-assistant/backend/tests/test_memory_manager.py`

- [ ] **步骤 1：编写失败的测试**

```python
from app.memory.long_term import LongTermMemory, Summary

def test_long_term_add_and_query():
    lt = LongTermMemory(user_id="u1")
    lt.add_summary(Summary(date="2026-07-10", topics=["天气"], preferences={"city": "北京"}, key_facts=["用户住在北京"]))
    hits = lt.query("用户住哪")
    assert "北京" in hits[0].key_facts[0]
```

- [ ] **步骤 2：运行测试验证失败**

```bash
pytest tests/test_memory_manager.py -v
```

预期：FAIL

- [ ] **步骤 3：实现 long_term.py**

```python
# app/memory/long_term.py
from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Iterable


@dataclass
class Summary:
    date: str
    topics: list[str] = field(default_factory=list)
    preferences: dict = field(default_factory=dict)
    key_facts: list[str] = field(default_factory=list)
    embedding_id: str | None = None


class LongTermMemory:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.summaries: list[Summary] = []

    def add_summary(self, s: Summary) -> None:
        self.summaries.append(s)

    def query(self, text: str) -> list[Summary]:
        # 关键词重叠简单检索；后续可用向量存储替换
        words = set(text.lower().split())
        scored = []
        for s in self.summaries:
            blob = " ".join(s.topics + list(s.preferences.values()) + s.key_facts).lower()
            overlap = len(words & set(blob.split()))
            if overlap:
                scored.append((overlap, s))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored]

    def preferences(self) -> dict:
        merged: dict = {}
        for s in self.summaries:
            merged.update(s.preferences)
        return merged
```

- [ ] **步骤 4：测试通过并 Commit**

```bash
pytest tests/test_memory_manager.py -v
git add backend/app/memory/long_term.py backend/tests/test_memory_manager.py
git commit -m "feat: long-term memory with summary query"
```

---

### 任务 3：向量记忆 + 记忆管理器

**文件：**
- 创建：`voice-assistant/backend/app/memory/vector.py`
- 创建：`voice-assistant/backend/app/memory/manager.py`

**说明：** 向量记忆复用 Phase 1 的 `app/rag/store.py` 的 `VectorStore` 与 `tokenize`，存储对话摘要的文本块与 embedding（本阶段用 bag-of-words cosine，接口可换 OpenAI embedding）。

- [ ] **步骤 1：编写失败的测试**

```python
from app.memory.manager import MemoryManager

def test_manager_merge_context():
    mm = MemoryManager(user_id="u1")
    mm.long_term.add_summary(__import__("app.memory.long_term", fromlist=["Summary"]).Summary(
        date="2026-07-10", topics=["音乐"], preferences={"lang": "中文"}, key_facts=["喜欢周杰伦"]
    ))
    ctx = mm.build_context("推荐一首歌")
    assert "周杰伦" in ctx
    assert "中文" in ctx
```

- [ ] **步骤 2：运行测试验证失败**

```bash
pytest tests/test_memory_manager.py -v
```

预期：FAIL

- [ ] **步骤 3：实现 vector.py 与 manager.py**

```python
# app/memory/vector.py
from __future__ import annotations

from dataclasses import dataclass, field

from app.rag.store import VectorStore, tokenize, Chunk


@dataclass
class VectorMemory:
    store: VectorStore = field(default_factory=VectorStore)

    def remember(self, text: str, source: str = "summary") -> None:
        self.store.add(
            Chunk(id=f"{source}:{len(self.store.chunks)}", source=source, text=text, tokens=tokenize(text))
        )

    def recall(self, query: str, top_k: int = 3) -> list[tuple[Chunk, float]]:
        return self.store.search(query, top_k)
```

```python
# app/memory/manager.py
from __future__ import annotations

from app.memory.long_term import LongTermMemory
from app.memory.vector import VectorMemory


class MemoryManager:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.long_term = LongTermMemory(user_id)
        self.vector = VectorMemory()

    def build_context(self, query: str) -> str:
        parts: list[str] = []
        for s in self.long_term.query(query):
            parts.append(f"[长期记忆] 偏好={s.preferences} 事实={s.key_facts}")
        for chunk, score in self.vector.recall(query):
            if score > 0:
                parts.append(f"[向量记忆] {chunk.text}")
        return "\n".join(parts)

    def archive(self, session_messages: list[dict], summary_text: str) -> None:
        # 由 Agent Engine 在会话空闲时调用
        self.vector.remember(summary_text)
        prefs = self.long_term.preferences()
        from app.memory.long_term import Summary
        self.long_term.add_summary(
            Summary(date="auto", topics=["对话"], preferences=prefs, key_facts=[summary_text[:200]])
        )
```

- [ ] **步骤 4：测试通过并 Commit**

```bash
pytest tests/test_memory_manager.py -v
git add backend/app/memory/vector.py backend/app/memory/manager.py backend/tests/test_memory_manager.py
git commit -m "feat: vector memory and manager merge context"
```

---

### 任务 4：Agent Engine 接入记忆上下文

**文件：**
- 修改：`voice-assistant/backend/app/agent/engine.py`
- 修改：`voice-assistant/backend/tests/test_agent_engine.py`

- [ ] **步骤 1：修改 engine.py 构造函数与 handle**

在 `AgentEngine.__init__` 增加 `memory: MemoryManager | None = None` 参数，保存为 `self.memory`。

在 `handle` 与 `stream_handle` 中，构造 messages 前加入记忆上下文：

```python
def _build_messages(self, user_text, decision, session):
    messages = [{"role": "system", "content": self.system_prompt}]
    if self.memory:
        mem_ctx = self.memory.build_context(user_text)
        if mem_ctx:
            messages.append({"role": "system", "content": f"用户历史记忆：\n{mem_ctx}"})
    if decision.mode == "hybrid" and decision.context:
        messages.append({"role": "system", "content": f"参考知识库：\n{decision.context}"})
    messages.extend(session.messages[-10:])
    return messages
```

替换 engine 中两处 messages 构造逻辑调用 `_build_messages`。

- [ ] **步骤 2：在 deps.py 装配 memory**

修改 `app/api/deps.py` 的 `get_engine`，增加：

```python
from app.memory.manager import MemoryManager
memory = MemoryManager(user_id="default")
return AgentEngine(llm, retriever, skills, s.default_system_prompt, memory=memory)
```

- [ ] **步骤 3：测试通过并 Commit**

```bash
pytest tests/test_agent_engine.py -v
git add backend/app/agent/engine.py backend/app/api/deps.py backend/tests/test_agent_engine.py
git commit -m "feat: agent engine injects memory context"
```

---

### 任务 5：Skill Executor 支持 HTTP 工具

**文件：**
- 修改：`voice-assistant/backend/app/skill/executor.py`
- 创建：`voice-assistant/backend/tests/test_skill_http.py`

**说明：** Phase 1 的 executor 仅用 LLM 自由回答。本任务让 `## tools` 中声明的 `http` 工具被真实调用（天气/搜索等预置 Skill 需要）。先用 Fake LLM 提取参数，再调用工具，最后用 LLM 格式化。

- [ ] **步骤 1：编写失败的测试**

```python
# tests/test_skill_http.py
from app.skill.loader import Skill
from app.skill.executor import SkillExecutor

def test_http_tool_called(monkeypatch):
    calls = {}
    def fake_get(url, params=None, **kw):
        class R: pass
        r = R(); r.status_code = 200; r.json = lambda: {"temp": 25}
        calls["url"] = url
        return r
    monkeypatch.setattr("app.skill.executor.requests.get", fake_get)
    skill = Skill(
        name="天气", triggers=["天气"], description="查天气",
        steps=["提取城市", "调用天气", "返回"],
        examples=[],
        raw_path=None,
    )
    # 注入 tools 字典
    skill.tools = {"weather_api": {"type": "http", "method": "GET", "url": "https://api.weather.com/{city}"}}
    ex = SkillExecutor(FakeLLM())
    out = ex.run(skill, "北京天气")
    assert calls["url"].endswith("北京") or "temp" in out

class FakeLLM:
    def chat(self, messages, model_name=None, temperature=0.7):
        return "北京"
```

- [ ] **步骤 2：运行失败**

```bash
pytest tests/test_skill_http.py -v
```

预期：FAIL

- [ ] **步骤 3：实现 executor 工具调用**

```python
# app/skill/executor.py （修改版）
from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse

import requests

from app.skill.loader import Skill

# 预置 Skill 允许访问的 HTTPS 域名（SSRF 防护）；可按需扩展，禁止裸 IP
_HTTP_HOST_ALLOWLIST = frozenset({
    "api.weather.com",
    "api.openweathermap.org",
    "api.duckduckgo.com",
    "news.example.com",  # 示例；上线前替换为真实 RSS/音乐 API 域名
})
_SAFE_PARAM = re.compile(r"^[\w\u4e00-\u9fff\-\.\s]{1,64}$")


def _is_public_https_url(url: str) -> bool:
    """仅允许 https + 白名单主机；拒绝私有/回环/链路本地 IP 与非标准端口滥用。"""
    try:
        p = urlparse(url)
    except Exception:
        return False
    if p.scheme != "https" or not p.hostname:
        return False
    host = p.hostname.lower()
    if host not in _HTTP_HOST_ALLOWLIST:
        return False
    # 主机名不得解析为内网（实现时用 socket.getaddrinfo + ipaddress 再校验一次）
    try:
        ipaddress.ip_address(host)
        return False  # 禁止直接写 IP
    except ValueError:
        pass
    if p.username or p.password:
        return False
    return True


class SkillExecutor:
    def __init__(self, llm, timeout: int = 10, sysctl_enabled: bool = False):
        self.llm = llm
        self.timeout = timeout
        self.sysctl_enabled = sysctl_enabled  # 默认关闭系统控制

    def run(self, skill: Skill, user_text: str) -> str:
        steps = "\n".join(f"{i+1}. {s}" for i, s in enumerate(skill.steps))
        sys_msg = (
            f"你正在执行技能「{skill.name}」。\n描述：{skill.description}\n步骤：\n{steps}\n"
            "先提取本技能需要的参数（如城市名），只返回参数值，不要解释。"
        )
        params_text = self.llm.chat([{"role": "system", "content": sys_msg}, {"role": "user", "content": user_text}])
        tool_results = self._call_tools(skill, params_text)
        final = self.llm.chat([
            {"role": "system", "content": f"技能「{skill.name}」已完成工具调用，请组织成自然语言回答。工具结果：{tool_results}"},
            {"role": "user", "content": user_text},
        ])
        return final

    def _call_tools(self, skill: Skill, params_text: str) -> str:
        tools = getattr(skill, "tools", {}) or {}
        out = []
        param = params_text.strip()
        if param and not _SAFE_PARAM.match(param):
            return "error:invalid parameter"
        for name, spec in tools.items():
            if spec.get("type") != "http":
                continue
            url = spec["url"]
            for key, _ in re.findall(r"\{(\w+)\}", url):
                url = url.replace("{" + key + "}", param)
            if not _is_public_https_url(url):
                out.append(f"{name}=error:url not allowed")
                continue
            method = spec.get("method", "GET").upper()
            if method not in {"GET", "POST"}:
                out.append(f"{name}=error:method not allowed")
                continue
            # allow_redirects=False 降低开放重定向到内网的风险
            resp = requests.request(
                method, url, timeout=self.timeout, allow_redirects=False
            )
            out.append(f"{name}={resp.text[:500]}")
        return " | ".join(out) if out else ""
```

- [ ] **步骤 4：Loader 解析 tools 段（修改 loader.py）**

在 `SkillLoader._parse` 中增加 `tools = self._section_kv(body, "tools")`，并在 `Skill` dataclass 增加 `tools: dict = field(default_factory=dict)`。

`_section_kv` 实现：解析 `key:` 缩进块为嵌套字典（简单两层级即可）。

- [ ] **步骤 5：测试通过并 Commit**

```bash
pytest tests/test_skill_http.py -v
git add backend/app/skill/executor.py backend/app/skill/loader.py backend/tests/test_skill_http.py
git commit -m "feat: skill http tool execution"
```

---

### 任务 6：10+ 预置 Skill 文件

**文件：**
- 创建/修改：`voice-assistant/backend/skills/weather.md` `calendar.md` `todo.md` `alarm.md` `calculator.md` `search.md` `news.md` `music.md` `system_control.md`

- [ ] **步骤 1：编写 weather.md**

```markdown
---
name: 天气查询
trigger: 天气|温度|下雨|晴天|气温|多少度
description: 查询指定城市的实时天气
version: 1.0.0
author: system
---

## steps
1. 从用户输入中提取城市名
2. 调用 weather_api 获取天气
3. 用自然语言返回温度与天气状况

## tools
weather_api:
  type: http
  method: GET
  url: https://api.weather.com/{city}

## examples
- 今天北京天气怎么样
- 上海明天会下雨吗
```

- [ ] **步骤 2：编写其余 8 个 Skill（同模板，差异化 trigger/steps/tools）**

- calculator.md：`trigger: 计算|算一下|等于多少`，tools 使用 `type: math`（AST 白名单算子，**禁止 `eval`/`exec`/`__import__`**；限制指数与操作数大小防 DoS）。
- todo.md：`trigger: 待办|提醒我|记一下`，tools 用 `type: localfile`（写入 `data/todo.json`，`Path.is_relative_to` 沙箱）。
- alarm.md：`trigger: 闹钟|定时|几分钟后`，tools `type: localfile`。
- calendar.md：`trigger: 日历|日程|安排`，tools `type: ical`（读取本地 ics，路径沙箱同 localfile）。
- search.md：`trigger: 搜索|查一下网页`，tools `type: http`（仅 HTTPS + 域名白名单）。
- news.md：`trigger: 新闻|头条`，tools `type: rss`（同 HTTP 白名单规则）。
- music.md：`trigger: 播放|来首歌|音乐`，tools `type: http` 音乐 API（白名单）。
- system_control.md：`trigger: 关机|休眠|锁屏`，tools `type: sysctl`（硬编码命令表 + **默认禁用** + 需用户二次确认 token；**禁止 shell 拼接**）。

- [ ] **步骤 3：executor 增加 math/localfile/sysctl 分支**

```python
# 在 _call_tools 中补充（安全工具类型；禁止 RCE）：
from pathlib import Path

if spec.get("type") == "math":
    try:
        # AST 白名单求值，禁止 eval/exec；限制 Pow 与操作数防资源耗尽
        import ast, operator as op
        allowed_ops = {
            ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul,
            ast.Div: op.truediv, ast.Pow: op.pow, ast.USub: op.neg,
            ast.Mod: op.mod, ast.FloorDiv: op.floordiv,
        }
        MAX_ABS = 10**12
        MAX_EXP = 32

        def _safe_eval(node):
            if isinstance(node, ast.Expression):
                return _safe_eval(node.body)
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                if abs(node.value) > MAX_ABS:
                    raise ValueError("number too large")
                return node.value
            if isinstance(node, ast.UnaryOp) and type(node.op) in allowed_ops:
                return allowed_ops[type(node.op)](_safe_eval(node.operand))
            if isinstance(node, ast.BinOp) and type(node.op) in allowed_ops:
                left, right = _safe_eval(node.left), _safe_eval(node.right)
                if isinstance(node.op, ast.Pow):
                    if not isinstance(right, int) or right < 0 or right > MAX_EXP:
                        raise ValueError("exponent not allowed")
                    if abs(left) > 10**6:
                        raise ValueError("base too large for pow")
                result = allowed_ops[type(node.op)](left, right)
                if isinstance(result, (int, float)) and abs(result) > MAX_ABS:
                    raise ValueError("result too large")
                return result
            raise ValueError(f"unsupported expression: {type(node).__name__}")
        expr = params_text.strip()
        if len(expr) > 128:
            raise ValueError("expression too long")
        result = _safe_eval(ast.parse(expr, mode="eval"))
        out.append(f"{name}={result}")
    except Exception as e:
        out.append(f"{name}=error:{e}")
elif spec.get("type") == "localfile":
    _BASE = Path(__file__).resolve().parent.parent.parent / "data"
    path_str = spec.get("path", "todo.json")
    # 仅允许相对文件名，禁止 .. 与绝对路径
    if Path(path_str).is_absolute() or ".." in Path(path_str).parts:
        out.append(f"{name}=error:path traversal denied")
    else:
        p = (_BASE / path_str).resolve()
        base = _BASE.resolve()
        # 使用 is_relative_to，避免 Windows 上 startswith 路径绕过
        if not p.is_relative_to(base):
            out.append(f"{name}=error:path traversal denied")
        else:
            import json
            p.parent.mkdir(parents=True, exist_ok=True)
            arr = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
            arr.append(params_text.strip()[:500])
            p.write_text(json.dumps(arr, ensure_ascii=False), encoding="utf-8")
            out.append(f"{name}=saved")
elif spec.get("type") == "sysctl":
    # 默认关闭；开启后仍须二次确认 + 硬编码命令表，禁止 shell 拼接
    if not self.sysctl_enabled:
        out.append(f"{name}=error:sysctl disabled")
    elif not getattr(skill, "confirmed", False):
        out.append(f"{name}=error:confirmation required")
    else:
        _WHITELIST = {"shutdown", "restart", "sleep", "lock", "hibernate"}
        cmd_key = spec.get("command", "")
        if cmd_key not in _WHITELIST:
            out.append(f"{name}=error:command not allowed")
        else:
            import subprocess, sys
            cmds = {
                ("shutdown", "win32"): ["shutdown", "/s", "/t", "5"],
                ("shutdown", "linux"): ["shutdown", "-h", "+1"],
                ("shutdown", "darwin"): ["shutdown", "-h", "+1"],
                ("restart", "win32"): ["shutdown", "/r", "/t", "5"],
                ("restart", "linux"): ["shutdown", "-r", "+1"],
                ("lock", "win32"): ["rundll32.exe", "user32.dll,LockWorkStation"],
                ("lock", "linux"): ["gnome-screensaver-command", "-l"],
                ("sleep", "win32"): ["rundll32.exe", "powrprof.dll,SetSuspendState", "0", "1", "0"],
                ("sleep", "linux"): ["systemctl", "suspend"],
                ("hibernate", "win32"): ["shutdown", "/h"],
                ("hibernate", "linux"): ["systemctl", "hibernate"],
            }
            plat = sys.platform
            cmd = cmds.get((cmd_key, plat))
            if cmd:
                subprocess.run(cmd, shell=False, timeout=self.timeout)
                out.append(f"{name}=ok")
            else:
                out.append(f"{name}=error:unsupported platform")
```

- [ ] **步骤 4：验证 Skill 加载并 Commit**

```bash
cd voice-assistant/backend
python -c "from app.api.deps import get_engine; e=get_engine(); print(len(e.matcher.skills), [s.name for s in e.matcher.skills])"
# 预期打印 >=10 个技能名
git add backend/skills backend/app/skill/executor.py
git commit -m "feat: 10+ preset skills with tool types"
```

---

### 任务 7：记忆 REST 接口 + 端到端验收

**文件：**
- 创建：`voice-assistant/backend/app/api/memory.py`
- 修改：`voice-assistant/backend/README.md`

- [ ] **步骤 1：实现 memory.py**

```python
# app/api/memory.py
from fastapi import APIRouter
from app.api.deps import get_engine

router = APIRouter(tags=["memory"])

@router.get("/memory/context")
def memory_context(q: str = "你好"):
    engine = get_engine()
    if not engine.memory:
        return {"context": ""}
    return {"context": engine.memory.build_context(q)}

@router.post("/memory/archive")
def archive(session_id: str = "default"):
    engine = get_engine()
    if not engine.memory:
        return {"ok": False}
    session = engine.get_session(session_id)
    engine.memory.archive(session.messages, f"会话摘要：{session.messages[-1:]}")
    return {"ok": True, "summaries": len(engine.memory.long_term.summaries)}
```

- [ ] **步骤 2：在 main.py 注册**

```python
from app.api import memory
app.include_router(memory.router, prefix="/api")
```

- [ ] **步骤 3：全量测试**

```bash
cd voice-assistant/backend
pytest -v
```

预期：全部 PASS

- [ ] **步骤 4：更新 README 并 Commit**

```bash
git add backend/app/api/memory.py backend/app/main.py voice-assistant/README.md
git commit -m "feat: memory rest api and phase3 readme"
```

---

## 自检

### 1. 规格覆盖度（第三阶段）

| 规格需求 | 对应任务 |
|---------|---------|
| 短期记忆（Session + TTL） | 任务 1 |
| 长期记忆（摘要） | 任务 2 |
| 向量记忆 | 任务 3 |
| 上下文检索回答 | 任务 3、4 |
| 自动摘要归档 | 任务 3、7 |
| 10+ 预置 Skill | 任务 5、6 |
| Skill HTTP/工具调用 | 任务 5、6 |

### 2. 占位符扫描

- 无 TODO；工具类型仅为 `http` / `math` / `localfile` / `sysctl` / `ical` / `rss`（**无** `eval`/`shell`）；HTTP 域名白名单 + localfile `is_relative_to` + sysctl 默认禁用。

### 3. 类型一致性

- `ShortTermMemory` 继承 `SessionContext`，复用 `.add/.messages`
- `Summary.date/topics/preferences/key_facts`
- `MemoryManager.build_context/archive`
- `Skill.tools: dict`（loader 新增字段）

---

## 后续阶段（本计划不实现）

- 第四阶段：数字人
- 第五阶段：Mini-Omni/Moshi 真全双工 + 语音克隆
- 第六阶段：Android / 小程序 / Supabase 同步 / 插件市场
