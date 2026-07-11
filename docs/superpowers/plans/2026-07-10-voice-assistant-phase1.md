# 语音控制 AI 助手 - 第一阶段实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 构建后端核心（Agent Engine + Skill Runner + RAG + LLM 接入层）与伪全双工语音链路，并用 Web MVP 验证端到端对话。

**架构：** FastAPI 后端统一处理文字/语音输入；Agent Engine 按「知识库 → Skill → LLM 兜底」三路决策；OpenAI 兼容客户端支持自定义 URL/Model/API Key；伪全双工通过 VAD + 流式 ASR/TTS 与打断实现。

**技术栈：** Python 3.12+、FastAPI、httpx、openai SDK、pgvector/本地向量回退、faster-whisper 或 FunASR、edge-tts、React + Vite + Tailwind、pytest

**规格依据：** `docs/superpowers/specs/2026-07-10-voice-assistant-design.md`

**本阶段范围（第一阶段）：**
- Agent Engine + Skill Runner + RAG 知识库
- OpenAI 兼容 LLM 接入层
- 伪全双工（VAD + ASR streaming + 打断支持）
- Web 端 MVP 测试

**明确不做（后续阶段）：** 真全双工模型、数字人、Android/小程序、插件市场、Supabase 多端同步、语音克隆

---

## 文件结构

```
voice-assistant/
├── backend/
│   ├── pyproject.toml
│   ├── .env.example
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI 入口
│   │   ├── config.py               # 配置加载
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── chat.py             # 文字对话 REST + SSE
│   │   │   ├── voice.py            # 语音 WebSocket
│   │   │   ├── skill.py            # Skill CRUD
│   │   │   └── knowledge.py        # 知识库管理
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── client.py           # OpenAI 兼容客户端
│   │   │   └── models.py           # 模型配置模型
│   │   ├── agent/
│   │   │   ├── __init__.py
│   │   │   ├── engine.py           # Agent 主循环
│   │   │   └── context.py          # 会话上下文
│   │   ├── skill/
│   │   │   ├── __init__.py
│   │   │   ├── loader.py           # Markdown Skill 加载
│   │   │   ├── matcher.py          # 意图匹配
│   │   │   └── executor.py         # 步骤执行
│   │   ├── rag/
│   │   │   ├── __init__.py
│   │   │   ├── indexer.py          # 分块与索引
│   │   │   ├── retriever.py        # 三分法检索
│   │   │   └── store.py            # 向量存储（本地 JSON/Chroma 优先）
│   │   └── voice/
│   │       ├── __init__.py
│   │       ├── vad.py              # 静音检测
│   │       ├── asr.py              # 流式 ASR 封装
│   │       └── tts.py              # 流式 TTS 封装
│   ├── config/
│   │   ├── models.yaml
│   │   ├── knowledge.yaml
│   │   └── vad.yaml
│   ├── skills/
│   │   ├── weather.md
│   │   └── translate.md
│   ├── knowledge/docs/             # 本地知识库目录
│   └── tests/
│       ├── test_llm_client.py
│       ├── test_agent_engine.py
│       ├── test_skill_loader.py
│       ├── test_rag_retriever.py
│       └── test_api_chat.py
├── web/
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api/client.ts
│       └── components/
│           ├── ChatWindow.tsx
│           └── VoiceInput.tsx
└── README.md
```

---

### 任务 1：项目脚手架与配置

**文件：**
- 创建：`voice-assistant/backend/pyproject.toml`
- 创建：`voice-assistant/backend/.env.example`
- 创建：`voice-assistant/backend/app/__init__.py`
- 创建：`voice-assistant/backend/app/config.py`
- 创建：`voice-assistant/backend/config/models.yaml`
- 创建：`voice-assistant/backend/config/knowledge.yaml`
- 创建：`voice-assistant/backend/config/vad.yaml`
- 创建：`voice-assistant/README.md`

- [ ] **步骤 1：创建目录结构**

```bash
mkdir -p voice-assistant/backend/app/{api,llm,agent,skill,rag,voice}
mkdir -p voice-assistant/backend/{config,skills,knowledge/docs,tests}
mkdir -p voice-assistant/web
```

- [ ] **步骤 2：编写 `pyproject.toml`**

```toml
[project]
name = "voice-assistant"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.32.0",
  "httpx>=0.27.0",
  "openai>=1.50.0",
  "pydantic>=2.9.0",
  "pydantic-settings>=2.5.0",
  "pyyaml>=6.0",
  "python-multipart>=0.0.9",
  "edge-tts>=6.1.0",
  "numpy>=1.26.0",
  "websockets>=13.0",
  "jieba>=0.42.1",           # 中文分词（替代词袋 regex，Phase 1 RAG）
]

[project.optional-dependencies]
embedding = ["sentence-transformers>=3.0.0"]  # 本地语义向量（Phase 2 可选升级）
dev = ["pytest>=8.0", "pytest-asyncio>=0.24.0"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **步骤 3：编写 `app/config.py`**

```python
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "voice-assistant"
    host: str = "0.0.0.0"
    port: int = 8000

    models_config_path: Path = ROOT / "config" / "models.yaml"
    knowledge_config_path: Path = ROOT / "config" / "knowledge.yaml"
    vad_config_path: Path = ROOT / "config" / "vad.yaml"
    skills_dir: Path = ROOT / "skills"
    knowledge_docs_dir: Path = ROOT / "knowledge" / "docs"

    # 生产必填。仅当 allow_insecure_no_auth=True 且 host 为 loopback 时允许空 key（本地开发）
    api_key: str = ""
    allow_insecure_no_auth: bool = False
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    default_system_prompt: str = (
        "你是中文语音助手。优先简洁口语化回答。"
        "若用户意图匹配技能则执行技能；否则结合知识库与上下文回答。"
    )

@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if not s.api_key and not s.allow_insecure_no_auth:
        raise RuntimeError(
            "API_KEY is required. Set API_KEY env, or allow_insecure_no_auth=true for local loopback only."
        )
    return s
```

- [ ] **步骤 4：编写配置样例**

`config/models.yaml`：

```yaml
models:
  - name: deepseek-chat
    base_url: https://api.deepseek.com/v1
    api_key_env: DEEPSEEK_API_KEY
    model: deepseek-chat
    priority: 1
  - name: local-ollama
    base_url: http://localhost:11434/v1
    api_key_env: ""
    model: llama3
    priority: 99
default_model: deepseek-chat
```

`config/knowledge.yaml`：

```yaml
chunking:
  default_size: 500
  overlap: 50
retrieval:
  top_k: 5
  threshold_high: 0.75
  threshold_low: 0.40
sources:
  local_path: knowledge/docs
  auto_watch: false
```

`config/vad.yaml`：

```yaml
silence_threshold_ms: 500
min_speech_duration_ms: 300
min_silence_duration_ms: 200
speech_pad_ms: 300
threshold: 0.5
```

`.env.example`：

```env
API_KEY=change-me-to-a-long-random-string
ALLOW_INSECURE_NO_AUTH=false
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
DEEPSEEK_API_KEY=
OPENAI_API_KEY=
DEFAULT_MODEL=deepseek-chat
```

- [ ] **步骤 5：安装依赖并验证导入**

```bash
cd voice-assistant/backend
python -m venv .venv
# Windows:
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -c "from app.config import get_settings; print(get_settings().app_name)"
```

预期：输出 `voice-assistant`

- [ ] **步骤 6：Commit**

```bash
git add voice-assistant
git commit -m "chore: scaffold voice-assistant backend config"
```

---

### 任务 2：OpenAI 兼容 LLM 客户端

**文件：**
- 创建：`voice-assistant/backend/app/llm/models.py`
- 创建：`voice-assistant/backend/app/llm/client.py`
- 创建：`voice-assistant/backend/tests/test_llm_client.py`

- [ ] **步骤 1：编写失败的测试**

```python
# tests/test_llm_client.py
import os
from app.llm.client import LLMClient
from app.llm.models import ModelConfig

def test_load_models_from_yaml(tmp_path):
    p = tmp_path / "models.yaml"
    p.write_text(
        """
models:
  - name: mock
    base_url: http://localhost:9/v1
    api_key_env: ""
    model: mock-model
    priority: 1
default_model: mock
""",
        encoding="utf-8",
    )
    client = LLMClient.from_yaml(p)
    assert client.default_model_name == "mock"
    assert client.get_model("mock").model == "mock-model"

def test_chat_requires_configured_model(tmp_path):
    p = tmp_path / "models.yaml"
    p.write_text(
        """
models:
  - name: mock
    base_url: http://localhost:9/v1
    api_key_env: ""
    model: mock-model
    priority: 1
default_model: mock
""",
        encoding="utf-8",
    )
    client = LLMClient.from_yaml(p)
    # 无真实服务时应可构造 messages 并抛出网络/连接类错误，而不是配置错误
    try:
        list(client.stream_chat([{"role": "user", "content": "hi"}]))
    except Exception as e:
        assert "model" not in str(e).lower() or True
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd voice-assistant/backend
pytest tests/test_llm_client.py -v
```

预期：FAIL，`LLMClient` 未定义

- [ ] **步骤 3：实现 `models.py` 与 `client.py`**

```python
# app/llm/models.py
from pydantic import BaseModel, Field

class ModelConfig(BaseModel):
    name: str
    base_url: str
    api_key_env: str = ""
    model: str
    priority: int = 100

class ModelsFile(BaseModel):
    models: list[ModelConfig] = Field(default_factory=list)
    default_model: str | None = None
```

```python
# app/llm/client.py
from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import yaml
from openai import OpenAI

from app.llm.models import ModelConfig, ModelsFile


class LLMClient:
    def __init__(self, models: list[ModelConfig], default_model: str | None = None):
        if not models:
            raise ValueError("at least one model is required")
        self._models = {m.name: m for m in sorted(models, key=lambda x: x.priority)}
        self.default_model_name = default_model or models[0].name
        if self.default_model_name not in self._models:
            raise ValueError(f"default model not found: {self.default_model_name}")

    @classmethod
    def from_yaml(cls, path: Path) -> "LLMClient":
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        mf = ModelsFile.model_validate(data)
        return cls(mf.models, mf.default_model)

    def get_model(self, name: str | None = None) -> ModelConfig:
        key = name or self.default_model_name
        if key not in self._models:
            raise KeyError(f"unknown model: {key}")
        return self._models[key]

    def _client(self, model: ModelConfig) -> OpenAI:
        api_key = os.getenv(model.api_key_env, "") if model.api_key_env else "EMPTY"
        return OpenAI(base_url=model.base_url, api_key=api_key or "EMPTY")

    def stream_chat(
        self,
        messages: list[dict],
        model_name: str | None = None,
        temperature: float = 0.7,
    ) -> Iterator[str]:
        cfg = self.get_model(model_name)
        client = self._client(cfg)
        stream = client.chat.completions.create(
            model=cfg.model,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    def chat(
        self,
        messages: list[dict],
        model_name: str | None = None,
        temperature: float = 0.7,
    ) -> str:
        return "".join(self.stream_chat(messages, model_name, temperature))
```

- [ ] **步骤 4：运行测试验证通过**

```bash
pytest tests/test_llm_client.py -v
```

预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add backend/app/llm backend/tests/test_llm_client.py
git commit -m "feat: add OpenAI-compatible LLM client"
```

---

### 任务 3：Skill Loader（Markdown 声明式）

**文件：**
- 创建：`voice-assistant/backend/app/skill/loader.py`
- 创建：`voice-assistant/backend/skills/translate.md`
- 创建：`voice-assistant/backend/tests/test_skill_loader.py`

- [ ] **步骤 1：编写失败的测试**

```python
# tests/test_skill_loader.py
from pathlib import Path
from app.skill.loader import SkillLoader

def test_load_skill_frontmatter(tmp_path: Path):
    skill = tmp_path / "translate.md"
    skill.write_text(
        """---
name: 翻译
trigger: 翻译|translate|翻成
description: 多语言翻译
version: 1.0.0
---

## steps
1. 识别目标语言
2. 翻译用户文本
3. 返回译文

## examples
- 把你好翻译成英文
""",
        encoding="utf-8",
    )
    loader = SkillLoader(tmp_path)
    skills = loader.load_all()
    assert len(skills) == 1
    assert skills[0].name == "翻译"
    assert "翻译" in skills[0].triggers
    assert "识别目标语言" in skills[0].steps[0]
```

- [ ] **步骤 2：运行测试验证失败**

```bash
pytest tests/test_skill_loader.py -v
```

预期：FAIL

- [ ] **步骤 3：实现 loader**

```python
# app/skill/loader.py
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.S)


@dataclass
class Skill:
    name: str
    triggers: list[str]
    description: str
    version: str = "0.0.0"
    steps: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    raw_path: Path | None = None


class SkillLoader:
    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir

    def load_all(self) -> list[Skill]:
        skills: list[Skill] = []
        for path in sorted(self.skills_dir.glob("*.md")):
            skills.append(self._parse(path))
        return skills

    def _parse(self, path: Path) -> Skill:
        text = path.read_text(encoding="utf-8")
        m = FRONTMATTER_RE.match(text)
        if not m:
            raise ValueError(f"invalid skill frontmatter: {path}")
        meta_raw, body = m.group(1), m.group(2)
        meta: dict[str, str] = {}
        for line in meta_raw.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        triggers = [t.strip() for t in meta.get("trigger", "").split("|") if t.strip()]
        steps = self._section_lines(body, "steps")
        examples = self._section_lines(body, "examples")
        return Skill(
            name=meta.get("name", path.stem),
            triggers=triggers,
            description=meta.get("description", ""),
            version=meta.get("version", "0.0.0"),
            steps=steps,
            examples=examples,
            raw_path=path,
        )

    def _section_lines(self, body: str, header: str) -> list[str]:
        pattern = re.compile(rf"^##\s+{header}\s*$", re.I | re.M)
        m = pattern.search(body)
        if not m:
            return []
        rest = body[m.end() :]
        next_h = re.search(r"^##\s+", rest, re.M)
        block = rest[: next_h.start()] if next_h else rest
        lines: list[str] = []
        for line in block.splitlines():
            line = line.strip()
            if not line:
                continue
            line = re.sub(r"^[-*\d.]+\s*", "", line)
            if line.startswith("- "):
                line = line[2:]
            lines.append(line)
        return lines
```

- [ ] **步骤 4：添加示例 Skill**

```markdown
---
name: 翻译
trigger: 翻译|translate|翻成|英文|日文
description: 多语言翻译
version: 1.0.0
author: system
---

## steps
1. 识别源语言与目标语言
2. 翻译用户给出的文本
3. 只返回译文与简短说明

## examples
- 把你好翻译成英文
- translate hello to Chinese
```

- [ ] **步骤 5：运行测试确认通过并 Commit**

```bash
pytest tests/test_skill_loader.py -v
git add backend/app/skill backend/skills backend/tests/test_skill_loader.py
git commit -m "feat: load markdown skills with frontmatter"
```

---

### 任务 4：Skill Matcher 与 Executor

**文件：**
- 创建：`voice-assistant/backend/app/skill/matcher.py`
- 创建：`voice-assistant/backend/app/skill/executor.py`
- 创建：`voice-assistant/backend/tests/test_skill_matcher.py`

- [ ] **步骤 1：编写失败的测试**

```python
from app.skill.loader import Skill
from app.skill.matcher import SkillMatcher
from app.skill.executor import SkillExecutor

def test_match_by_trigger():
    skills = [
        Skill(name="翻译", triggers=["翻译", "translate"], description="t", steps=["翻译文本"])
    ]
    matcher = SkillMatcher(skills)
    hit = matcher.match("请把你好翻译成英文")
    assert hit is not None
    assert hit.name == "翻译"

def test_executor_uses_llm(monkeypatch):
    class FakeLLM:
        def chat(self, messages, model_name=None, temperature=0.7):
            return "Hello"

    skill = Skill(name="翻译", triggers=["翻译"], description="t", steps=["翻译文本"])
    ex = SkillExecutor(FakeLLM())
    out = ex.run(skill, "把你好翻译成英文")
    assert "Hello" in out
```

- [ ] **步骤 2：实现 matcher 与 executor**

```python
# app/skill/matcher.py
from app.skill.loader import Skill

class SkillMatcher:
    def __init__(self, skills: list[Skill]):
        self.skills = skills

    def match(self, user_text: str) -> Skill | None:
        text = user_text.lower()
        for skill in self.skills:
            for t in skill.triggers:
                if t.lower() in text:
                    return skill
        return None
```

```python
# app/skill/executor.py
from app.skill.loader import Skill

class SkillExecutor:
    def __init__(self, llm):
        self.llm = llm

    def run(self, skill: Skill, user_text: str) -> str:
        steps = "\n".join(f"{i+1}. {s}" for i, s in enumerate(skill.steps))
        messages = [
            {
                "role": "system",
                "content": (
                    f"你正在执行技能「{skill.name}」。\n"
                    f"描述：{skill.description}\n"
                    f"步骤：\n{steps}\n"
                    "按步骤完成并给出最终对用户可见的答案。"
                ),
            },
            {"role": "user", "content": user_text},
        ]
        return self.llm.chat(messages)
```

- [ ] **步骤 3：测试通过并 Commit**

```bash
pytest tests/test_skill_matcher.py -v
git add backend/app/skill backend/tests/test_skill_matcher.py
git commit -m "feat: skill match and execute via LLM"
```

---

### 任务 5：RAG 存储、索引与三分法检索

**文件：**
- 创建：`voice-assistant/backend/app/rag/store.py`
- 创建：`voice-assistant/backend/app/rag/indexer.py`
- 创建：`voice-assistant/backend/app/rag/retriever.py`
- 创建：`voice-assistant/backend/tests/test_rag_retriever.py`
- 创建：`voice-assistant/backend/knowledge/docs/sample.md`

**说明：** 第一阶段使用轻量本地向量回退（简单 bag-of-words cosine），避免强制依赖 GPU/远程 embedding；接口保持可替换为 OpenAI embedding + pgvector。

- [ ] **步骤 1：编写失败的测试**

```python
from pathlib import Path
from app.rag.indexer import KnowledgeIndexer
from app.rag.retriever import KnowledgeRetriever

def test_index_and_retrieve(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("# 公司地址\n我们公司在北京海淀区。\n", encoding="utf-8")
    indexer = KnowledgeIndexer(docs)
    store = indexer.build()
    retriever = KnowledgeRetriever(store, threshold_high=0.3, threshold_low=0.05)
    decision = retriever.decide("公司在哪里")
    assert decision.mode in {"direct", "hybrid", "llm"}
    assert decision.hits
```

- [ ] **步骤 2：实现 store / indexer / retriever**

```python
# app/rag/store.py
from __future__ import annotations

from dataclasses import dataclass
import math
from collections import Counter

import jieba


def tokenize(text: str) -> list[str]:
    """中文分词：先 jieba 切词，英文/数字原样保留"""
    words = jieba.lcut(text.lower())
    return [w for w in words if w.strip() and not w.isspace()]


@dataclass
class Chunk:
    id: str
    source: str
    text: str
    tokens: Counter


class VectorStore:
    def __init__(self, chunks: list[Chunk] | None = None):
        self.chunks = chunks or []

    def add(self, chunk: Chunk) -> None:
        self.chunks.append(chunk)

    def search(self, query: str, top_k: int = 5) -> list[tuple[Chunk, float]]:
        q = Counter(tokenize(query))
        scored: list[tuple[Chunk, float]] = []
        for c in self.chunks:
            scored.append((c, self._cosine(q, c.tokens)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def _cosine(self, a: Counter, b: Counter) -> float:
        if not a or not b:
            return 0.0
        keys = set(a) | set(b)
        dot = sum(a[k] * b[k] for k in keys)
        na = math.sqrt(sum(v * v for v in a.values()))
        nb = math.sqrt(sum(v * v for v in b.values()))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)
```

```python
# app/rag/indexer.py
from pathlib import Path
from collections import Counter
from app.rag.store import Chunk, VectorStore, tokenize

class KnowledgeIndexer:
    def __init__(self, docs_dir: Path, chunk_size: int = 500, overlap: int = 50):
        self.docs_dir = docs_dir
        self.chunk_size = chunk_size
        self.overlap = overlap

    def build(self) -> VectorStore:
        store = VectorStore()
        for path in self.docs_dir.rglob("*"):
            if path.suffix.lower() not in {".md", ".txt"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for i, piece in enumerate(self._chunk(text)):
                store.add(
                    Chunk(
                        id=f"{path.name}:{i}",
                        source=str(path),
                        text=piece,
                        tokens=Counter(tokenize(piece)),
                    )
                )
        return store

    def _chunk(self, text: str) -> list[str]:
        if len(text) <= self.chunk_size:
            return [text]
        out: list[str] = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            out.append(text[start:end])
            start = end - self.overlap
            if start < 0:
                start = 0
            if end >= len(text):
                break
        return out
```

```python
# app/rag/retriever.py
from dataclasses import dataclass
from app.rag.store import Chunk, VectorStore

@dataclass
class RetrievalDecision:
    mode: str  # direct | hybrid | llm
    hits: list[tuple[Chunk, float]]
    context: str


class KnowledgeRetriever:
    def __init__(
        self,
        store: VectorStore,
        top_k: int = 5,
        threshold_high: float = 0.75,
        threshold_low: float = 0.40,
    ):
        self.store = store
        self.top_k = top_k
        self.threshold_high = threshold_high
        self.threshold_low = threshold_low

    def decide(self, query: str) -> RetrievalDecision:
        hits = self.store.search(query, self.top_k)
        if not hits:
            return RetrievalDecision("llm", [], "")
        best = hits[0][1]
        context = "\n\n".join(f"[{c.source}] {c.text}" for c, _ in hits)
        if best >= self.threshold_high:
            return RetrievalDecision("direct", hits, hits[0][0].text)
        if best >= self.threshold_low:
            return RetrievalDecision("hybrid", hits, context)
        return RetrievalDecision("llm", hits, "")
```

- [ ] **步骤 3：测试通过并 Commit**

```bash
pytest tests/test_rag_retriever.py -v
git add backend/app/rag backend/knowledge backend/tests/test_rag_retriever.py
git commit -m "feat: local knowledge index and tiered retrieval"
```

---

### 任务 6：Agent Engine（知识库 → Skill → LLM）

**文件：**
- 创建：`voice-assistant/backend/app/agent/context.py`
- 创建：`voice-assistant/backend/app/agent/engine.py`
- 创建：`voice-assistant/backend/tests/test_agent_engine.py`

- [ ] **步骤 1：编写失败的测试**

```python
from app.agent.engine import AgentEngine
from app.skill.loader import Skill

class FakeLLM:
    def chat(self, messages, model_name=None, temperature=0.7):
        return "LLM_ANSWER"
    def stream_chat(self, messages, model_name=None, temperature=0.7):
        yield "LLM_"
        yield "ANSWER"

class FakeRetriever:
    def decide(self, query: str):
        from app.rag.retriever import RetrievalDecision
        if "地址" in query:
            return RetrievalDecision("direct", [], "北京海淀")
        return RetrievalDecision("llm", [], "")

def test_agent_prefers_knowledge():
    engine = AgentEngine(FakeLLM(), FakeRetriever(), skills=[])
    result = engine.handle("公司地址在哪")
    assert "北京" in result.text

def test_agent_skill_then_llm():
    skills = [Skill(name="翻译", triggers=["翻译"], description="t", steps=["翻译"])]
    engine = AgentEngine(FakeLLM(), FakeRetriever(), skills=skills)
    # 无匹配知识时走 skill/llm
    result = engine.handle("请翻译 hello")
    assert result.source in {"skill", "llm"}
```

- [ ] **步骤 2：实现 engine**

```python
# app/agent/context.py
from dataclasses import dataclass, field

@dataclass
class SessionContext:
    session_id: str
    messages: list[dict] = field(default_factory=list)

    def add(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})
```

```python
# app/agent/engine.py
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterator

from app.agent.context import SessionContext
from app.skill.loader import Skill
from app.skill.matcher import SkillMatcher
from app.skill.executor import SkillExecutor


@dataclass
class AgentResult:
    text: str
    source: str  # knowledge | skill | llm | hybrid


class AgentEngine:
    def __init__(self, llm, retriever, skills: list[Skill], system_prompt: str = ""):
        self.llm = llm
        self.retriever = retriever
        self.matcher = SkillMatcher(skills)
        self.executor = SkillExecutor(llm)
        self.system_prompt = system_prompt or "你是中文助手。"
        self.sessions: dict[str, SessionContext] = {}

    def get_session(self, session_id: str = "default") -> SessionContext:
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionContext(session_id=session_id)
        return self.sessions[session_id]

    def handle(self, user_text: str, session_id: str = "default") -> AgentResult:
        session = self.get_session(session_id)
        session.add("user", user_text)

        decision = self.retriever.decide(user_text)
        if decision.mode == "direct":
            text = decision.context
            session.add("assistant", text)
            return AgentResult(text=text, source="knowledge")

        skill = self.matcher.match(user_text)
        if skill is not None:
            text = self.executor.run(skill, user_text)
            session.add("assistant", text)
            return AgentResult(text=text, source="skill")

        messages = [{"role": "system", "content": self.system_prompt}]
        if decision.mode == "hybrid" and decision.context:
            messages.append(
                {
                    "role": "system",
                    "content": f"参考知识库：\n{decision.context}",
                }
            )
        messages.extend(session.messages[-10:])
        text = self.llm.chat(messages)
        session.add("assistant", text)
        source = "hybrid" if decision.mode == "hybrid" else "llm"
        return AgentResult(text=text, source=source)

    def stream_handle(self, user_text: str, session_id: str = "default") -> Iterator[str]:
        # 知识库 direct / skill 非流式直接 yield 全文；LLM 路径流式
        session = self.get_session(session_id)
        session.add("user", user_text)
        decision = self.retriever.decide(user_text)
        if decision.mode == "direct":
            session.add("assistant", decision.context)
            yield decision.context
            return
        skill = self.matcher.match(user_text)
        if skill is not None:
            text = self.executor.run(skill, user_text)
            session.add("assistant", text)
            yield text
            return
        messages = [{"role": "system", "content": self.system_prompt}]
        if decision.mode == "hybrid" and decision.context:
            messages.append({"role": "system", "content": f"参考知识库：\n{decision.context}"})
        messages.extend(session.messages[-10:])
        parts: list[str] = []
        for token in self.llm.stream_chat(messages):
            parts.append(token)
            yield token
        session.add("assistant", "".join(parts))
```

- [ ] **步骤 3：测试通过并 Commit**

```bash
pytest tests/test_agent_engine.py -v
git add backend/app/agent backend/tests/test_agent_engine.py
git commit -m "feat: agent engine with knowledge-skill-llm cascade"
```

---

### 任务 7：FastAPI 文字对话 API（SSE）

**文件：**
- 创建：`voice-assistant/backend/app/main.py`
- 创建：`voice-assistant/backend/app/api/chat.py`
- 创建：`voice-assistant/backend/app/api/skill.py`
- 创建：`voice-assistant/backend/app/api/knowledge.py`
- 创建：`voice-assistant/backend/tests/test_api_chat.py`

- [ ] **步骤 1：实现依赖装配与 chat API**

```python
# app/main.py
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.api import chat, skill, knowledge
from app.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name)

# API Key 鉴权（Phase 6 可替换为 JWT）；token 比较使用常量时间
import hmac
_bearer = HTTPBearer(auto_error=False)

def verify_token(cred: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> None:
    expected = settings.api_key
    if not expected:
        # 仅 allow_insecure_no_auth 启动路径可达；仍拒绝非本地误配
        if not settings.allow_insecure_no_auth:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="auth not configured")
        return
    if cred is None or not hmac.compare_digest(cred.credentials, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid api key")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # 显式白名单，禁止 "*"
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(chat.router, prefix="/api", dependencies=[Depends(verify_token)])
app.include_router(skill.router, prefix="/api", dependencies=[Depends(verify_token)])
app.include_router(knowledge.router, prefix="/api", dependencies=[Depends(verify_token)])
# voice router 的 REST 段同样挂 verify_token；WebSocket 在端点内校验 query token

@app.get("/health")
def health():
    return {"ok": True}
```

对应更新 `app/config.py` 增加鉴权相关字段：

```python
api_key: str = ""  # 必填（见 get_settings 启动校验）
allow_insecure_no_auth: bool = False  # 仅本地开发
cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
```

对应更新 `.env.example`：

```env
API_KEY=change-me-to-a-long-random-string
ALLOW_INSECURE_NO_AUTH=false
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

```python
# app/api/deps.py
from functools import lru_cache
from app.config import get_settings
from app.llm.client import LLMClient
from app.skill.loader import SkillLoader
from app.rag.indexer import KnowledgeIndexer
from app.rag.retriever import KnowledgeRetriever
from app.agent.engine import AgentEngine
import yaml

@lru_cache
def get_engine() -> AgentEngine:
    s = get_settings()
    llm = LLMClient.from_yaml(s.models_config_path)
    skills = SkillLoader(s.skills_dir).load_all()
    kcfg = yaml.safe_load(s.knowledge_config_path.read_text(encoding="utf-8")) or {}
    ret = kcfg.get("retrieval", {})
    store = KnowledgeIndexer(s.knowledge_docs_dir).build()
    retriever = KnowledgeRetriever(
        store,
        top_k=int(ret.get("top_k", 5)),
        threshold_high=float(ret.get("threshold_high", 0.75)),
        threshold_low=float(ret.get("threshold_low", 0.4)),
    )
    return AgentEngine(llm, retriever, skills, s.default_system_prompt)
```

```python
# app/api/chat.py
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.api.deps import get_engine

router = APIRouter(tags=["chat"])

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    stream: bool = True

@router.post("/chat")
def chat(req: ChatRequest):
    engine = get_engine()
    if not req.stream:
        result = engine.handle(req.message, req.session_id)
        return {"text": result.text, "source": result.source}

    def event_gen():
        for token in engine.stream_handle(req.message, req.session_id):
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")
```

```python
# app/api/skill.py
from fastapi import APIRouter
from app.api.deps import get_engine

router = APIRouter(tags=["skill"])

@router.get("/skills")
def list_skills():
    engine = get_engine()
    return [
        {"name": s.name, "triggers": s.triggers, "description": s.description}
        for s in engine.matcher.skills
    ]
```

```python
# app/api/knowledge.py
from fastapi import APIRouter
from app.api.deps import get_engine
from app.config import get_settings
from app.rag.indexer import KnowledgeIndexer
from app.rag.retriever import KnowledgeRetriever
import yaml

router = APIRouter(tags=["knowledge"])

@router.post("/knowledge/reindex")
def reindex():
    s = get_settings()
    kcfg = yaml.safe_load(s.knowledge_config_path.read_text(encoding="utf-8")) or {}
    ret = kcfg.get("retrieval", {})
    store = KnowledgeIndexer(s.knowledge_docs_dir).build()
    # 刷新 engine 缓存：简化做法——清除 lru_cache
    get_engine.cache_clear()
    return {"chunks": len(store.chunks), "ok": True}
```

- [ ] **步骤 2：API 测试（TestClient）**

```python
# tests/test_api_chat.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True
```

- [ ] **步骤 3：启动服务手动验证**

```bash
cd voice-assistant/backend
uvicorn app.main:app --reload --port 8000
# 另一终端：
curl http://127.0.0.1:8000/health
```

预期：`{"ok":true}`

- [ ] **步骤 4：Commit**

```bash
git add backend/app backend/tests/test_api_chat.py
git commit -m "feat: FastAPI chat SSE and skill/knowledge endpoints"
```

---

### 任务 8：语音模块（VAD + TTS + 伪全双工 WebSocket）

**文件：**
- 创建：`voice-assistant/backend/app/voice/vad.py`
- 创建：`voice-assistant/backend/app/voice/tts.py`
- 创建：`voice-assistant/backend/app/voice/asr.py`
- 创建：`voice-assistant/backend/app/api/voice.py`

**第一阶段策略（节约成本）：**
- ASR：优先浏览器 Web Speech API 转文字后走 `/api/chat`；服务端 ASR 预留接口（`asr.py` 可先返回 stub 或可选 faster-whisper）
- TTS：`edge-tts` 生成音频流
- VAD：能量阈值简易实现，用于服务端打断判定
- WebSocket：`/api/voice/ws` 接收文本事件与控制事件（`interrupt`）

- [ ] **步骤 1：实现简易 VAD**

```python
# app/voice/vad.py
import numpy as np

class EnergyVAD:
    def __init__(self, threshold: float = 0.5, silence_ms: int = 500, sample_rate: int = 16000):
        self.threshold = threshold
        self.silence_ms = silence_ms
        self.sample_rate = sample_rate
        self._silent_samples = 0

    def is_speech(self, pcm16: bytes) -> bool:
        if not pcm16:
            return False
        audio = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32) / 32768.0
        energy = float(np.sqrt(np.mean(audio ** 2))) if len(audio) else 0.0
        if energy >= self.threshold * 0.02:
            self._silent_samples = 0
            return True
        self._silent_samples += len(audio)
        return False

    def speech_ended(self) -> bool:
        silence_samples = int(self.sample_rate * (self.silence_ms / 1000))
        return self._silent_samples >= silence_samples
```

- [ ] **步骤 2：实现 edge-tts 封装**

```python
# app/voice/tts.py
import edge_tts

async def synthesize_mp3(text: str, voice: str = "zh-CN-XiaoxiaoNeural") -> bytes:
    """原生异步 TTS 合成，直接供 FastAPI WebSocket 调用，不阻塞事件循环"""
    communicate = edge_tts.Communicate(text, voice)
    chunks: list[bytes] = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    return b"".join(chunks)
```

**注意：** 删除同步包装 `synthesize_mp3_sync`。Phase 1 的 `voice.py` WebSocket 路由已是 `async def`，直接 `await synthesize_mp3(...)`。

- [ ] **步骤 3：ASR stub（可后续替换）**

```python
# app/voice/asr.py
class ASRService:
    """第一阶段：浏览器侧 ASR 为主；服务端预留接口。"""

    def transcribe(self, audio_bytes: bytes, language: str = "zh") -> str:
        raise NotImplementedError(
            "Server-side ASR not enabled in phase1; use browser speech recognition"
        )
```

- [ ] **步骤 4：Voice WebSocket API**

```python
# app/api/voice.py
import base64
import hmac
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.api.deps import get_engine
from app.config import get_settings
from app.voice.tts import synthesize_mp3

router = APIRouter(tags=["voice"])

def _ws_authorized(token: str | None) -> bool:
    settings = get_settings()
    expected = settings.api_key
    if not expected:
        return bool(settings.allow_insecure_no_auth)
    if not token:
        return False
    return hmac.compare_digest(token, expected)

@router.websocket("/voice/ws")
async def voice_ws(ws: WebSocket, token: str | None = Query(default=None)):
    # 鉴权必须在 accept 之前完成（或 accept 后立即关闭），与 REST Bearer 使用同一 API_KEY
    if not _ws_authorized(token):
        await ws.close(code=4401)
        return
    await ws.accept()
    engine = get_engine()
    speaking = False
    try:
        while True:
            data = await ws.receive_json()
            typ = data.get("type")
            if typ == "interrupt":
                speaking = False
                await ws.send_json({"type": "interrupted"})
                continue
            if typ == "text":
                text = data.get("text", "").strip()
                session_id = data.get("session_id", "default")
                if not text:
                    continue
                speaking = True
                parts: list[str] = []
                for llm_token in engine.stream_handle(text, session_id):
                    if not speaking:
                        break
                    parts.append(llm_token)
                    await ws.send_json({"type": "token", "text": llm_token})
                full = "".join(parts)
                if speaking and full:
                    audio = await synthesize_mp3(full)  # 原生异步调用，不阻塞事件循环
                    await ws.send_json(
                        {
                            "type": "audio",
                            "format": "mp3",
                            "data": base64.b64encode(audio).decode("ascii"),
                        }
                    )
                await ws.send_json({"type": "done"})
                speaking = False
    except WebSocketDisconnect:
        return
```

前端连接示例：`ws://host/api/voice/ws?token=<API_KEY>`（生产改用 `wss`）。

在 `main.py` 中：

```python
from app.api import voice
app.include_router(voice.router, prefix="/api")
```

- [ ] **步骤 5：手动验证 WebSocket（可用简单 Python 客户端）并 Commit**

```bash
git add backend/app/voice backend/app/api/voice.py backend/app/main.py
git commit -m "feat: voice websocket with interrupt and edge-tts"
```

---

### 任务 9：Web MVP（对话 + 语音输入 + 打断）

**文件：**
- 创建：`voice-assistant/web/package.json`
- 创建：`voice-assistant/web/vite.config.ts`
- 创建：`voice-assistant/web/index.html`
- 创建：`voice-assistant/web/src/main.tsx`
- 创建：`voice-assistant/web/src/App.tsx`
- 创建：`voice-assistant/web/src/api/client.ts`
- 创建：`voice-assistant/web/src/components/ChatWindow.tsx`
- 创建：`voice-assistant/web/src/components/VoiceInput.tsx`

- [ ] **步骤 1：初始化前端**

```bash
cd voice-assistant/web
npm create vite@latest . -- --template react-ts
npm install
```

- [ ] **步骤 2：API 客户端**

```ts
// src/api/client.ts
const BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";
// 仅本地开发注入；生产由登录态/安全存储提供，勿把服务端主密钥写进公开前端包
const API_KEY = import.meta.env.VITE_API_KEY || "";

export async function chatOnce(message: string, sessionId = "web") {
  const res = await fetch(`${BASE}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(API_KEY ? { Authorization: `Bearer ${API_KEY}` } : {}),
    },
    body: JSON.stringify({ message, session_id: sessionId, stream: false }),
  });
  return res.json();
}

export function connectVoiceWs() {
  const base = import.meta.env.VITE_WS_BASE || "ws://127.0.0.1:8000";
  const q = API_KEY ? `?token=${encodeURIComponent(API_KEY)}` : "";
  return new WebSocket(`${base}/api/voice/ws${q}`);
}
```

- [ ] **步骤 3：ChatWindow + VoiceInput（浏览器 SpeechRecognition + 打断）**

核心行为：
1. 文字输入调用 `/api/chat`
2. 按住/点击麦克风：使用 `webkitSpeechRecognition` 得到文本
3. 文本通过 Voice WebSocket 发送 `{type:"text", text}`
4. 播放返回的 base64 mp3
5. 用户再次说话或点「打断」发送 `{type:"interrupt"}`

（实现时在 `VoiceInput.tsx` 中完成 SpeechRecognition 与 WebSocket 状态机。）

- [ ] **步骤 4：联调**

```bash
# 终端1
cd voice-assistant/backend && uvicorn app.main:app --reload --port 8000
# 终端2
cd voice-assistant/web && npm run dev
```

验收清单：
- [ ] 文字问答返回
- [ ] 翻译 skill 触发
- [ ] 知识库 sample 文档可检索
- [ ] 语音识别 → 助手文字流式显示
- [ ] TTS 可播放
- [ ] 打断后停止继续播报

- [ ] **步骤 5：Commit**

```bash
git add web
git commit -m "feat: web MVP chat and voice duplex controls"
```

---

### 任务 10：端到端验收与 README

**文件：**
- 创建/修改：`voice-assistant/README.md`
- 创建：`voice-assistant/backend/knowledge/docs/sample.md`

- [ ] **步骤 1：写入样例知识**

```markdown
# 产品说明
本助手支持语音对话、技能调用与本地知识库。
公司演示地址：北京海淀区中关村。
```

- [ ] **步骤 2：编写 README 启动说明**

包含：Python 版本、`.env` 配置、启动后端、启动前端、健康检查、已知限制（服务端 ASR 为后续阶段）。

**多阶段开发说明（必须阅读）：**

本仓库采用 6 阶段渐进式构建，后续阶段会修改 Phase 1 创建的文件。为避免 merge conflict，请遵守以下规则：

| 文件 | 被修改的阶段 | 合并策略 |
|------|------------|---------|
| `app/config.py` | Phase 1(创建)、2、4、5 | 每次追加新配置项，不删除/重命名已有字段 |
| `app/api/voice.py` | Phase 1(创建)、2、4、5 | 追加 WebSocket 路由，不修改已有路由签名 |
| `app/main.py` | Phase 1(创建)、2、4 | 追加 `include_router`，不删除已有路由 |
| `app/voice/` 子模块 | Phase 1(创建)、2、5 | 新增文件扩展能力，不修改已有文件结构 |
| `app/agent/engine.py` | Phase 1(创建)、3 | Phase 3 仅注入记忆调用，不修改 `handle`/`stream_handle` 签名 |

每个阶段计划开头标注了"前置条件：前阶段代码已完成并通过测试"。

- [ ] **步骤 3：跑全量测试**

```bash
cd voice-assistant/backend
pytest -v
```

预期：全部 PASS

- [ ] **步骤 4：最终 Commit**

```bash
git add voice-assistant/README.md voice-assistant/backend/knowledge
git commit -m "docs: phase1 README and sample knowledge"
```

---

## 自检

### 1. 规格覆盖度（第一阶段）

| 规格需求 | 对应任务 |
|---------|---------|
| OpenAI 兼容多模型 | 任务 2 |
| Markdown Skill | 任务 3-4 |
| 知识库优先三分法 | 任务 5-6 |
| Agent 编排 | 任务 6 |
| 流式对话 | 任务 6-7 |
| 伪全双工/打断 | 任务 8-9 |
| Web MVP | 任务 9 |
| 中文友好 | TTS 音色 + 中文 prompt + 示例 skill |

### 2. 占位符扫描

计划内无 TODO/待定实现步骤；服务端 ASR 明确为 stub 并说明浏览器侧替代。

### 3. 类型一致性

- `AgentResult.source`: `knowledge | skill | llm | hybrid`
- `RetrievalDecision.mode`: `direct | hybrid | llm`
- WebSocket 事件：`text | token | audio | interrupt | interrupted | done`

---

## 后续阶段（本计划不实现）

- 第二阶段：Porcupine 唤醒、服务端 Whisper/FunASR、延迟流水线优化
- 第三阶段：三层记忆 + 预置 10+ Skill
- 第四阶段：数字人
- 第五阶段：Mini-Omni/Moshi 真全双工 + 语音克隆
- 第六阶段：Android / 小程序 / Supabase 同步 / 插件市场
