# 语音控制 AI 助手系统设计

## 概述

一个类似豆包的全能型语音 AI 助手，支持语音控制、自动调用技能、多端同步、知识库优先回答。

## 核心需求

- 实时语音输入（Whisper Streaming）
- 语音回复（TTS 自动播放）
- 流式对话（边生成边说）
- 多模型接入（DeepSeek、Qwen、Llama3、Gemini 等 OpenAI 兼容格式）
- 插件/Skill 系统（Markdown 声明式）
- 知识库优先回答（RAG + 本地文件 + 网页抓取）
- 多端支持（Web、Android、微信小程序）
- 数据同步（Supabase，后期可迁移自建）
- 本地部署（隐私安全）
- 中文友好
- **唤醒词唤醒**（Porcupine，本地运行）
- **语音自动安装 Skill/插件**（语音 → ASR → LLM 理解 → 下载安装）
- **虚拟数字人**（照片生成，对话默认开启，可隐藏）
- **三层记忆系统**（短期/长期/向量，上下文检索回答）
- **全双工对话**（边听边说，支持打断）

## 架构方案

### 整体架构

```
┌────────────────────────────────────────────────────────────���─┐
│                        客户端层                                │
│  ┌──────────┐  ┌──────────┐  ┌────────────┐  ┌──────────┐   │
│  │ Web端     │  │ Android  │  │ 微信小程序  │  │ API 调用 │   │
│  └─────┬────┘  └─────┬────┘  └──────┬─────┘  └────┬─────┘   │
└────────┼──────────────┼──────────────┼──────────────┼─────────┘
         │              │              │              │
         └──────────────┼──────────────┼──────────────┘
                        │   API Gateway (REST + WebSocket)
┌───────────────────────┼──────────────────────────────────────┐
│                后端服务层 (Python/FastAPI)                     │
│                                                              │
│  ┌────────���────┐  ┌──────────────┐  ┌───────────────────┐   │
│  │ 语音网关     │  │ Agent Engine  │  │ Skill Runner      │   │
│  │ (Porcupine   │  │ (LLM 编排)    │  │ (Markdown 技能)   │   │
│  │  + FunASR   │  │              │  │                   │   │
│  │  + CosyVoice)│  │              │  │                   │   │
│  └─────────────┘  └──────┬───────┘  └───────────────────┘   │
│                          │                                     │
│  ┌───────────────────────┼────────────────────────────────┐   │
│  │                   RAG 知识库引擎                        │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐   │   │
│  │  │ 本地文件索引  │  │ 网页抓取器    │  │ 向量检索     │   │   │
│  │  │(MD/PDF/TXT) │  │(URL 爬取)    │  │(Embeddings)  │   │   │
│  │  ���─────────────┘  └──────────────┘  └──────────────┘   │   │
│  └────────────────────────────────────────────────────────┘   │
│                          │                                     │
│  ┌───────────────────────┼────────────────────────────────┐   │
│  │            OpenAI 兼容 LLM 接入层                      │   │
│  │    (自定义 URL / Model / API Key / System Prompt)      │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  数据层: Supabase (PostgreSQL + Realtime + Storage)     │   │
│  │  (开源，后期可迁移到自建)                                 │   │
│  └────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### 技术选型

| 模块 | 选型 | 说明 |
|------|------|------|
| 后端框架 | Python FastAPI | 异步、高性能、WebSocket 原生支持 |
| 语音唤醒 | Porcupine (Picovoice) | 本地运行，中文唤醒词支持 |
| 语音识别 | faster-whisper / FunASR | 中文 ASR 流式识别（Phase 2 启用） |
| 语音合成 | CosyVoice / Edge TTS | 中文自然，支持流式 TTS |
| LLM 接入 | OpenAI 兼容接口 | 自定义 URL/Model/API Key |
| 向量库 | 本地 `VectorStore` → pgvector(Phase 6) | Phase 1 用 jieba 分词 + TF-IDF；Phase 2 可选升级 sentence-transformers |
| 中文分词 | jieba | 替代 bag-of-words regex，Phase 1 即启用 |
| Embedding | sentence-transformers(可选) / OpenAI Embedding | 本地 CPU 可跑 paraphrase-multilingual-MiniLM-L12-v2 |
| 记忆持久化 | SQLite（Phase 3）→ Supabase(Phase 6) | 支持多 Worker，重启不丢上下文 |
| 安全鉴权 | API Key Bearer Token（Phase 1）→ JWT(Phase 6) | 所有 `/api` 路由强制校验 |
| 工具执行 | 白名单枚举 + ast.literal_eval | 禁止 eval/shell，防 RCE |
| 数据同步 | Supabase Realtime | 开源可迁移 |
| 前端 Web | React + Tailwind | 轻量、生态丰富 |
| 移动端 | Flutter | 跨平台，可复用逻辑 |
| 小程序 | 微信原生 | 平台要求 |

## 开源全双工模型集成

### Mini-Omni（gpt-omni/mini-omni）

Mini-Omni 是一个开源端到端全双工语音模型，可直接替代 Phase 5 的自建全双工实现，大幅减少代码量。

**能力：**
- 实时语音输入 → 流式音频输出（原生全双工）
- 自带 VAD + Whisper 编码 + SNAC 解码 + CosyVoice 合成
- 提供 Flask `/chat` HTTP 接口（仅 63 行 `server.py`）
- 可直接作为子模块或子进程嵌入本项目

**集成方式（推荐）：子进程模式**

```
我们的 FastAPI
    │
    ├── 中文对话 → Phase 2 ASR + LLM + TTS 链路
    │
    └── 全双工模式 → 启动 Mini-Omni server.py 子进程
         │
         ├── POST /chat {audio: base64 wav}
         │   → 返回 streaming audio/wav
         │
         └── 我们负责：
             - 接收客户端 PCM 流
             - 转 WAV 格式调用 Mini-Omni
             - 流式转发音频帧回客户端
             - 打断事件转发
```

**子模块集成：**

```bash
git submodule add https://github.com/gpt-omni/mini-omni.git third_party/mini-omni
```

**接口契约：**

Mini-Omni 默认 `server.py` 返回纯二进制音频流。为使全双工对话可被记忆系统记录（Phase 3 依赖文本），需修改 `MiniOmniClient` 的流式响应格式为 JSON 分块，每块包含 text + audio：

```python
# app/voice/mini_omni.py
import base64, json, os, shutil, subprocess, time
from pathlib import Path
from typing import Iterator
import requests

class MiniOmniClient:
    def __init__(self, url="http://localhost:60808"):
        self.url = url
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
        raise TimeoutError("Mini-Omni server did not start within 30s")

    def stream_chat(
        self, wav_bytes: bytes, stream_stride=4, max_tokens=2048
    ) -> Iterator[dict]:
        """每次 yield {"text": str, "audio": bytes | None}"""
        resp = requests.post(
            f"{self.url}/chat",
            json={
                "audio": base64.b64encode(wav_bytes).decode(),
                "stream_stride": stream_stride,
                "max_tokens": max_tokens,
            },
            stream=True,
        )
        # 解析 JSON Lines 格式：{"text":"...","audio":"base64..."}
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            data = json.loads(line)
            audio = base64.b64decode(data["audio"]) if data.get("audio") else None
            yield {"text": data.get("text", ""), "audio": audio}
```

对应地，Mini-Omni 的 `server.py` 需要做两处改动：
1. 在 stream 循环中将 yield 从纯 `audio_chunk` 改为 `json.dumps({"text": text_chunk, "audio": base64.b64encode(audio_chunk).decode()}) + "\n"`
2. 增加 `GET /health` 路由返回 200

这些改动作为对 `third_party/mini-omni/server.py` 的 patch 文件维护。

**限制与应对：**

| 限制 | 说明 | 应对方案 |
|------|------|---------|
| 仅输出英文 | FAQ 明确说明 | 英文模式直接使用；中文模式回退到 Phase 2 链路 |
| 需要 GPU | 模型 ~2B 参数 | 可选依赖，未配置时自动回退 |
| 仅支持英语语音 | CosyVoice 中文 voice 未开放 | Phase 2 中文 TTS 作为回退 |

**决策建议：**
- Phase 5 以 Mini-Omni 为主，省去自建全双工模型代码
- 保留 Phase 2 的中文 ASR+TTS 链路作为中文模式回退
- 通过 `config/full_duplex.yaml` 的 `mode: mini-omni | fallback` 切换

## Agent Engine 流程

```
用户输入（语音/文字）
       │
       ▼
┌─────────────���────┐
│  意图识别层       │
│  ┌────────────┐   │
│  │ 知识库优先  │──┼──→ 有匹配 → 直接返回知识库答案
│  │ (RAG检索)  │   │
│  └────────────┘   │
│       │ 无匹配     │
│       ▼           │
│  ┌────────────┐   │
│  │ Skill 匹配  │──┼──→ 有匹配 → 执行 Skill → 返回结果
│  │ (语义匹配)  │   │
│  └────────────┘   │
│       │ 无匹配     │
│       ▼           │
│  ┌────────────┐   │
│  │ LLM 自由回答 │──┼──→ 自定义提示词 + LLM 生成
│  │ (兜底)      │   │
│  └────────────┘   │
└──────────────────┘
       │
       ▼
┌──────────────────┐
│  流式输出层        │
│  ┌────────────┐   │
│  │ 文字流式输出 │──┼──→ WebSocket 推送到客户端
│  └────────────┘   │
│  ┌────────────┐   │
│  │ TTS 语音合成 │──┼──→ 音频���推送到客户端
│  │ (CosyVoice) │   │
│  └────────────┘   │
└──────────────────┘
```

### 流式对话流程

```
用户语音 → Whisper Streaming（实时转文字）
              │
              ▼
Agent Engine 开始处理 → 同时返回两种流：
              │
    ┌─────────┴─────────┐
    ▼                   ▼
文字流（SSE）         音频流（WebSocket）
    │                   │
    ▼                   ▼
Web 端实时显示文字     Android 端实时播放语音
    │                   │
    └─────────┬─────────┘
              ▼
      两端同步完成
```

## 多模型接入

```yaml
models:
  - name: deepseek-chat
    provider: openai-compatible
    base_url: https://api.deepseek.com/v1
    api_key: ${DEEPSEEK_KEY}
    model: deepseek-chat
    priority: 1

  - name: qwen-max
    provider: openai-compatible
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    api_key: ${QWEN_KEY}
    model: qwen-max
    priority: 2

  - name: local-llama
    provider: openai-compatible
    base_url: http://localhost:11434/v1
    api_key: ""
    model: llama3
    priority: 3
```

## Skill Runner 详细设计

### 架构

```
┌──────────────────────────────────────────┐
│              Skill Runner                 │
│                                           │
│  ┌──────────────┐  ┌──────────────┐      │
│  │ Skill 加载器   │  │ Skill 匹配器  │      │
│  │              │  │              │      │
│  │ 扫描 skills/  │  │ LLM 语义匹配  │      │
│  │ 热加载/热重载  │  │ 用户意图 →   │      │
│  │ 校验语法      │  │ 最佳 Skill   │      │
│  └──────┬───────┘  └──────┬───────┘      │
│         │                 │              │
│         └──────┬──────────┘              │
│                ▼                         │
│  ┌───────────────────────────────┐       │
│  │      Skill 执行器              │       │
│  │                               │       │
│  │ 解析 steps → 调用 tool →      │       │
│  │ 返回结果 → 格式化输出          │       │
│  └───────────────────────────────┘       │
│                                           │
│  ┌───────────────────────────────┐       │
│  │      语音安装 Skill            │       │
│  │                               │       │
│  │  "安装天气插件" → 语音识别 →   │       │
│  │  搜索插件市场 → 下载 → 加载    │       │
│  └───────────────────────────────┘       │
└──────────────────────────────────────────┘
```

### Skill Markdown 格式规范

```markdown
---
name: 天气查询
trigger: 天气|温度|下雨|晴天|气温
description: 查询指定城市的实时天气
version: 1.0.0
author: system
---

## steps
1. 从用户输入中提取城市名
2. 调用 `weather_api` 获取城市天气
3. 格式化结果返回

## tools
weather_api:
  type: http
  method: GET
  url: https://api.weather.com/{city}
  response: json

## examples
- "今天北京天气怎么样"
- "上海明天会下雨吗"
```

### Skill 匹配逻辑

```
用户输入 → LLM 语义匹配
              │
    ┌─────────┴─────────┐
    ▼                   ▼
  匹配成功            无匹配
    │                   │
    ▼                   ▼
执行 Skill        返回 Agent Engine
返回结果            走 LLM 兜底
```

### 插件类型

- **Skill 插件**: Markdown 声明式，定义触发条件和执行步骤
- **工具插件**: Python 代码，提供具体功能实现
- **数据源插件**: API 连接器，接入外部数据

## 知识库引擎

### 数据源

- **本地文件**: Markdown / PDF / TXT，自动索引
- **网页抓取**: URL 爬取，定时更新

### 检索流程

```
用户问题 → 向量检索 Top-5
       │
       ▼
┌──────────────────────┐
│ 相似度 ≥ 0.75        │───→ 直接返回知识库答案（高置信度）
└──────────────────────┘
       │ < 0.75
       ▼
┌──────────────────────┐
│ 相似度 0.4 ~ 0.75    │───→ 知识库结果 + LLM 总结（混合回答）
└──────────────────────┘
       │ < 0.4
       ▼
┌──────────────────────┐
│ LLM 自由回答          │───→ 使用自定义提示词兜底
└──────────────────────┘
```

## 项目结构

```
E:\Project\30\voice-assistant/
├── backend/
│   ├── app/
│   │   ├── api/              # API 路由
│   │   │   ├── chat.py       # 对话接口
│   │   │   ├── voice.py      # 语音接口
│   │   │   ├── skill.py      # Skill CRUD
│   │   │   ├── memory.py     # 记忆接口
│   │   │   ├── avatar.py     # 数字人接口
│   │   │   └── knowledge.py  # 知识库接口
│   │   ├── agent/            # Agent Engine
│   │   │   ├── engine.py     # 主循环
│   │   │   ├── intent.py     # 意图识别
│   │   │   └── context.py    # 上下文管理
│   │   ├── skill/            # Skill Runner
│   │   │   ├── loader.py     # 加载器
│   │   │   ├── matcher.py    # 匹配器
│   │   │   └── executor.py   # 执行器
│   │   ├── rag/              # RAG 知识库
│   │   │   ├── indexer.py    # 索引
│   │   │   ├── retriever.py  # 检索
│   │   │   └── crawler.py    # 网页抓取
│   │   ├── memory/           # 记忆系统
│   │   │   ├── short_term.py # 短期记忆
│   │   │   ├── long_term.py  # 长期记忆
│   │   │   └── vector.py     # 向量记忆
│   │   ├── voice/            # 语音模块
│   │   │   ├── wake.py       # 唤醒词
│   │   │   ├── asr.py        # 语音识别
│   │   │   └── tts.py        # 语音合成
│   │   ├── avatar/           # 数字人
│   │   │   ├── generator.py  # 生成
│   │   │   └── renderer.py   # 渲染
│   │   ├── llm/              # LLM 接入层
│   │   │   ├── client.py     # OpenAI 客户端
│   │   │   └── models.yaml   # 模型配置
│   │   └── sync/             # 同步层
│   │       └── supabase.py   # Supabase 客户端
│   ├── config/               # 配置文件
│   │   ├── models.yaml       # 多模型配置
│   │   └── knowledge.yaml    # 知识库配置
│   └── skills/               # 技能文件目录
│       ├── weather.md        # 天气查询
│       └── translate.md      # 翻译
├── web/                      # React 前端
│   ├── src/
│   │   ├── components/
│   │   │   ├── VoiceInput/   # 语音输入
│   │   │   ├── ChatWindow/   # 对话窗口
│   │   │   ├── Avatar/       # 数字人
│   │   │   └── SkillManager/ # 技能管理
│   │   └── hooks/
│   └── package.json
├── android/                  # Flutter 移动端
├── miniapp/                  # 微信小程序
└── docs/                     # 文档

## 竞品分析

### 行业标杆对比（2026年7月）

| 维度 | 本设计 | 豆包 (Seeduplex) | GPT-Live | Gemini Live |
|------|--------|-----------------|----------|-------------|
| **核心架构** | ASR+LLM+TTS 级联（混合） | 端到端统一模型 | 端到端全双工 | 端到端全双工 |
| **全双工** | ❌ 半双工（回合制） | ✅ 原生全双工 | ✅ 原生全双工 | ✅ 原生全双工 |
| **语音模型** | 开源组件拼装 | 自研 Seeduplex | 自研 GPT-5.5 | Gemini 3.1 Flash Live |
| **中文优化** | ✅ 深度优化 | ✅ 深度优化（最强） | ❌ 一般 | ❌ 一般 |
| **技能系统** | ✅ Markdown 声明式 | ✅ 封闭生态 | ✅ GPTs/Function Calling | ✅ Google Extension |
| **知识库 RAG** | ✅ 本地+网页双源 | ✅ 企业知识库 | ✅ 联网搜索 | ✅ Google 搜索 |
| **数字人** | ✅ LivePortrait | ✅ 自研 | ❌ 无 | ❌ 无 |
| **多端同步** | ✅ Supabase | ✅ 字节云 | ✅ OpenAI Cloud | ✅ Google Cloud |
| **开源** | ✅ 完全开源 | ❌ 闭源 | ❌ 闭源 | ❌ 闭源 |
| **本地部署** | ✅ 完全支持 | ❌ 不支持 | ❌ 不支持 | ❌ 不支持 |
| **多模型切换** | ✅ 任意 OpenAI 兼容 | ❌ 仅豆包模型 | ❌ 仅 OpenAI 模型 | ❌ 仅 Gemini 模型 |

### 核心差距分析

#### 1. 全双工架构差距 ❌
- **竞品现状**：豆包 Seeduplex、GPT-Live、Gemini Live 均已实现原生全双工（边听边说、可打断）
- **本设计现状**：半双工（ASR→LLM→TTS 串行，需等待完整语音输入）
- **影响**：对话自然度差距明显，用户会感觉到"对讲机效应"

#### 2. 端到端语音模型差距 ❌
- **竞品现状**：自研端到端语音大模型（Seeduplex / GPT-5.5），延迟约 700ms~1s
- **本设计现状**：开源组件拼装（Porcupine + FunASR + CosyVoice），级联延迟约 2~3s
- **影响**：响应速度慢 2~3 倍，体验差距明显

#### 3. 生态整合差距 ❌
- **竞品现状**：深度绑定自有生态（字节飞书/抖音、Google Workspace、OpenAI 生态）
- **本设计现状**：无自有生态，靠技能系统和 API 对接
- **影响**：开箱即用的能力较弱

#### 4. 情感表达能力差距 ❌
- **竞品现状**：支持丰富的情感表达、语气切换、情绪感知
- **本设计现状**：CosyVoice 基础情感支持
- **影响**：语音交互缺乏"人情味"

### 本设计的优势 ✅

#### 1. 完全开源 + 本地部署
- 所有竞品均为闭源云服务
- 本设计可完全本地运行，数据不出门

#### 2. 多模型自由切换
- 豆包只能用豆包模型，GPT-Live 只能用 OpenAI
- 本设计支持任意 OpenAI 兼容模型

#### 3. Markdown Skill 生态
- 竞品技能系统是封闭的（GPTs/Extension）
- 本设计的 Skill 是纯文本文件，任何编辑器可创建

#### 4. 知识库自主可控
- 竞品知识库绑定各自云平台
- 本设计支持本地文件 + 任意网页

#### 5. 虚拟数字人
- GPT-Live 和 Gemini Live 均无数字人功能
- 豆包有但需接入字节生态

### 改进方案

#### 优先级 P0（必须改进）

| 问题 | 改进方案 | 复杂度 | 替代方案 |
|------|---------|--------|---------|
| 全双工对话 | 阶段1（伪全双工）：流式 VAD + ASR 流式输出 + LLM streaming 并行处理，支持用户打断。阶段2（真全双工）：接入开源全双工模型 Mini-Omni 或 Moshi | 高 | 保持半双工，但通过极低延迟（<500ms ASR+LLM+TTS）伪造成全双工体验 |
| 响应延迟 | ASR 流式输出 + LLM 流式推理 + TTS 首帧快速合成，流水线并行 | 中 | 纯云端方案（延迟更低但依赖网络） |

#### 优先级 P1（应该改进）

| 问题 | 改进方案 | 复杂度 | 替代方案 |
|------|---------|--------|---------|
| 情感表达 | CosyVoice 情感参数调优 + 集成 GPT-SoVITS 作为可选 TTS 引擎 | 中 | 使用 Edge TTS（免费但情感有限） |
| 语音克隆 | 基于 CosyVoice 2 的零样本语音克隆，用户上传 10s 音频即可克隆自己的声音 | 中 | FunASR 声纹提取 + 简单变声 |
| 知识库更新 | 支持 Webhook 触发知识库自动重建，监控文件变更实时重索引 | 低 | 手动触发重建按钮 |

#### 优先级 P2（可以改进）

| 问题 | 改进方案 | 复杂度 | 替代方案 |
|------|---------|--------|---------|
| 端到端模型 | 跟踪 Mini-Omni / Moshi 等开源端到端语音模型，成熟后替换级联架构 | 高 | 级联架构优化到极致（1s 内完成） |
| 生态整合 | 预置 10+ 常用 Skill（天气/翻译/日历等），提供 Skill Market 网页端市场 | 低 | 用户自行安装 |
| 对话管理 | 支持对话分支、对话收藏、对话分享 | 低 | 线性对话 |
| 多语言切换 | 声控切换语言模式，ASR/LLM/TTS 自动切换 | 中 | 手动切换 |

### 具体优化路线图

#### 1. 全双工实现方案（P0）

```
目标：从对讲机模式进化到真人对话模式

阶段1（1-2周）—— 伪全双工：
+-----------------------------------------------------+
| 用户说话 -> VAD 检测到语音 -> ASR Streaming 输出文字   |
|                    |                                |
| VAD 检测到停顿（500ms）-> 当前文字送入 LLM            |
|                    |                                |
| LLM Streaming 输出 -> TTS 流式合成 -> 音频播放          |
|                    |                                |
| 用户可以随时说话 -> 音频播放暂停 -> ASR 重新开始        |
+-----------------------------------------------------+

阶段2（长期）—— 真全双工：
+-----------------------------------------------------+
| 集成 Mini-Omni 或 Moshi 开源全双工模型               |
| 单一模型同时处理：语音输入 + 语音输出                 |
| 原生支持：打断、插话、语气反馈（嗯/明白/哦）           |
| 延迟从 ~2s 降低到 ~800ms                             |
+-----------------------------------------------------+
```

**VAD 参数配置**（可调）：

```yaml
vad:
  silence_threshold_ms: 500
  min_speech_duration_ms: 300
  min_silence_duration_ms: 200
  speech_pad_ms: 300
  threshold: 0.5
```

#### 2. 响应延迟优化（P0）

```
当前流程（串行，~2-3s）：
  ASR (500ms) -> LLM (500-1000ms) -> TTS (500ms) = 约 2s

优化流程（并行流水线）：
  ASR streaming 实时输出
  LLM 在 ASR 未结束时即开始推理（基于部分结果）
  TTS 在 LLM 首 token 产出后立即开始合成

首 token 延迟预期：
  阶段1（伪全双工）：200-400ms + 200-300ms = 400-700ms
  阶段2（真全双工）：200-300ms（端到端模型）
```

#### 3. 情感 TTS 实现（P1）

```yaml
# config/tts.yaml
tts:
  primary: cosyvoice
  cosyvoice:
    model: CosyVoice-300M
    emotion: auto
    speed: 1.0

  alternative: gpt-sovits
  gpt_sovits:
    clone_audio: true
    clone_samples: "10s"

  emotion_tags:
    - "[happy]今天天气真好"
    - "[calm]让我查一下"
    - "[surprise]这是真的吗"
```

#### 4. 生态预置技能（P1）

| Skill | 功能 | 实现方式 |
|-------|------|---------|
| 天气查询 | 查实时/未来天气 | 和风天气 API |
| 翻译 | 多语言翻译 | LLM 自身能力 |
| 日历 | 查看/添加日程 | iCal 协议 |
| 待办事项 | 添加/查看待办 | 本地文件存储 |
| 闹钟/计时 | 设置提醒 | 系统通知 |
| 计算器 | 数学计算 | AST 安全求值（禁止 `eval`/`exec`） |
| 搜索 | 网页搜索 | OpenAI 兼容搜索 API（HTTPS 域名白名单） |
| 新闻 | 获取新闻摘要 | RSS 聚合（HTTPS 域名白名单） |
| 播放音乐 | 本地/在线音乐 | 对接音乐 API（HTTPS 域名白名单） |
| 系统控制 | 关机/休眠等 | 硬编码命令白名单 + 二次确认（禁止 shell 拼接） |

### 实施阶段（优化后）

#### 第一阶段：后端核心 + 基础全双工
- Agent Engine + Skill Runner + RAG 知识库
- OpenAI 兼容 LLM 接入层
- 伪全双工（VAD + ASR streaming + 打断支持）
- Web 端 MVP 测试

#### 第二阶段：语音能力增强
- Porcupine 唤醒词优化
- Whisper Streaming 实时语音
- CosyVoice TTS + 情感参数调优
- 响应延迟优化（流水线并行）

#### 第三阶段：记忆系统 + 生态预置
- 三层记忆架构
- 10+ 预置 Skill
- 上下文检索回答
- 自动摘要归档

#### 第四阶段：虚拟数字人
- 照片生成数字人
- 实时口型同步
- 显示/隐藏切换

#### 第五阶段：真全双工 + 语音克隆
- 接入 Mini-Omni / Moshi 开源全双工模型
- 语音克隆功能
- 多语言声控切换

#### 第六阶段：多端支持 + 插件生态
- Android Flutter 端
- 微信小程序
- 数据同步
- 插件市场 + 语音安装插件
## 虚拟数字人模块

### 架构

```
┌──────────────────────────────────────────────────┐
│                 数字人模块                          │
│                                                   │
│  ┌──────────────────┐  ┌───────────────────┐     │
│  │  数字人生成         │  │  数字人渲染         │     │
│  │                   │  │                   │     │
│  │  上传照片 → 检测    │  │  2D/3D 实时渲染    │     │
│  │  面部特征 → 生成    │  │  TTS + 口型同步    │     │
│  │  默认/用户自定义    │  │  显示/隐藏切换     │     │
│  └────────┬─────────┘  └────────┬──────────┘     │
│           │                     │                 │
│           └────────┬────────────┘                 │
│                    ▼                              │
│  ┌──────────────────────────────────┐            │
│  │       数字人状态管理                │            │
│  │  ┌─────────┐  ┌───────────────┐  │            │
│  │  │ 默认开启  │  │ 隐藏按钮      │  │            │
│  │  │ (对话时)  │  │ (随时可关闭)  │  │            │
│  │  └─────────┘  └───────────────┘  │            │
│  └──────────────────────────────────┘            │
└──────────────────────────────────────────────────┘
```

### 技术选型

| 功能 | 方案 | 说明 |
|------|------|------|
| 照片生成数字人 | LivePortrait / SadTalker | 上传照片 → 面部特征提取 → 生成 |
| 实时口型同步 | Wav2Lip / SadTalker | TTS 音频流 → 口型匹配 |
| 显示/隐藏 | 前端状态切换 + 全双工自动隐藏 | 对话时默认开启，可手动关闭；英文全双工(Mini-Omni)模式因无文本流口型将定格，由 `avatar.hide_on_full_duplex: true` 配置自动隐藏数字人 |
| 渲染引擎 | Canvas / WebGL | 轻量级，移动端友好 |

## 记忆系统

### 三层记忆架构

```
┌──────────────────────────────────────┐
│         三层记忆架构                    │
│                                       │
│  ┌────────────┐                      │
│  │ 短期记忆     │  当前对话上下文        │
│  │ (Session)   │  LLM 的上下文窗口     │
│  └────────────┘                      │
│       │ 自动归档                       │
│       ▼                              │
│  ┌────────────┐                      │
│  │ 长期记忆     │  历史对话摘要          │
│  │ (Summary)   │  关键信息提取          │
│  │            │  用户偏好、习惯        │
│  └────────────┘                      │
│       │ 向量化                        │
│       ▼                              │
│  ┌────────────┐                      │
│  │ 向量记忆     │  Embedding 存储      │
│  │ (Vector)   │  相似度检索           │
│  │            │  关联历史对话          │
│  └────────────┘                      │
└──────────────────────────────────────┘
```

### 短期记忆结构

```json
{
  "session_id": "xxx",
  "messages": [
    {"role": "user", "content": "今天天气怎么样"},
    {"role": "assistant", "content": "...", "tools_used": ["weather"]}
  ],
  "context": {"city": "北京", "topic": "天气"},
  "expires_at": "30分钟无活动后过期"
}
```

### 长期记忆结构

```json
{
  "user_id": "xxx",
  "summaries": [
    {
      "date": "2026-07-10",
      "topics": ["天气", "编程", "音乐"],
      "preferences": {"city": "北京", "language": "中文"},
      "key_facts": ["用户住在北京", "使用Python开发"],
      "embedding_id": "vec_xxx"
    }
  ],
  "auto_summary": "对话空闲时自动生成摘要"
}
```

### 上下文检索回答流程

```
用户新提问
    │
    ▼
┌─────────────────────────────────────┐
│ 步骤1: 检索相关历史记忆              │
│ 向量检索 → 找到相似的历史对话片段      │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 步骤2: 检索知识库                   │
│ 向量检索 → 找到相关知识条目          │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 步骤3: 合并上下文                    │
│ 当前消息 + 相关历史 + 相关知识       │
│ → 送入 LLM 生成回答                  │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 步骤4: 更新记忆                     │
│ 本次对话 → 短期记忆 → 归档长期记忆    │
└─────────────────────────────────────┘
```

## 多端数据同步设计

### 同步架构

```
┌──────────────────────────────────────────────────┐
│                  Supabase 同步层                    │
│                                                   │
│  ┌──────────────┐  ┌──────────────┐              │
│  │ Realtime      │  │ PostgreSQL   │              │
│  │ (WebSocket)   │  │ (主数据)      │              │
│  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                       │
│         ▼                 ▼                       │
│  ┌──────────────────────────────────────┐        │
│  │       同步数据模型                      │        │
│  └──────────────────────────────────────┘        │
└──────────────────────────────────────────────────┘

同步策略：
Web端 ↔ Supabase ↔ Android ↔ 小程序
任一端变更 → 实时推送到其他端
离线 → 本地缓存 → 恢复网络后自动同步
```

### 同步数据模型

| 数据表 | 同步策略 | 说明 |
|--------|---------|------|
| users | 全端同步 | 用户配置、偏好（含 `language` 偏好、`full_duplex_mode` 默认模式等 JSON config） |
| conversations | 全端同步 | 对话记录 |
| memories | 全端同步 | 长期记忆 |
| skills | 全端同步 | 已安装技能 |
| avatar_config | 全端同步 | 数字人配置 |
| voice_profiles | 全端同步（Supabase Storage） | 语音克隆参考音频文件（Phase 5），多设备共享用户自定义音色 |
| knowledge_files | 服务端同步 | 知识库文件索引 |
| language_settings | 合并到 users.config | 声控切换的语言偏好跨端同步 |
| full_duplex_config | 合并到 users.config | 全双工模式（mini-omni / fallback）跨端同步 |

### 离线缓存策略

```
客户端在线 → 实时同步 → 本地缓存更新
客户端离线 → 读写本地缓存 → 记录变更队列
客户端恢复 → 冲突检测 → 合并变更 → 推送到服务端
```

### 冲突处理

```
最后写入者获胜（LWW）：
- 每条记录带 server_updated_at 时间戳
- 冲突时以时间戳最新的版本为准
- 对话记录追加式写入（无冲突可能）
```

## 安全性设计

### API Key 管理

| 密钥 | 存储位置 | 说明 |
|------|---------|------|
| LLM API Key | 配置文件 + 环境变量 | 不硬编码在代码中 |
| Supabase Key | 环境变量 | 仅服务端使用 |
| 服务端 API Key | 环境变量 `API_KEY`（必填） | 所有 `/api` 与 WebSocket 强制 Bearer/query 校验 |
| 用户 API Key | 本地加密存储 + Supabase | 前端不可读明文 |

### 用户认证

```
- Phase 1：服务端 API Key（Bearer Token）；空 key 时拒绝启动（非 loopback 开发除外）
- Phase 6：Supabase Auth（邮箱/手机号/OAuth）+ JWT
- 多端：同一账号登录，数据自动同步
- 权限：RBAC（管理员/普通用户）；危险操作（关机、Skill 安装）仅管理员
```

### 工具与网络边界

```
- 禁止 eval / exec / shell 字符串拼接；数学用 AST 白名单算子
- HTTP/RSS 工具：仅 HTTPS + 域名白名单；禁止私有 IP / link-local / metadata
- 远程 Skill 安装：来源白名单 + 内容校验 + 路径沙箱 + 管理员鉴权
- 系统控制：硬编码命令映射 + 用户二次确认；默认关闭或需显式 enable
- CORS：显式 origin 列表，禁止 allow_origins=["*"] 搭配 credentials
- WebSocket：连接前校验 token（query 或首帧），与 REST 同一密钥体系
```

### 数据加密

```
- 传输加密：TLS 1.3
- 存储加密：Supabase 内置加密
- 敏感配置：环境变量 + .env 文件（.env 不入库）
- 本地缓存：SQLite 加密存储
- Token 比较：hmac.compare_digest，禁止明文 ==
```

## 错误处理

### LLM 调用失败

```
用户请求 → LLM 调用超时/报错
    │
    ▼
┌──────────────────────┐
│ 重试机制              │
│ 第1次失败 → 等待2秒   │
│ 第2次失败 → 等待5秒   │
│ 第3次失败 → 降级处理  │
└──────────────────────┘
    │
    ▼
┌──────────────────────┐
│ 降级策略              │
│ ① 切换到备选模型     │
│ ② 返回错误提示      │
│ ③ 记录日志 + 通知    │
└──────────────────────┘
```

### 语音识别失败

```
- 静音检测 → 提示用户说话
- 噪声过高 → 建议安静环境
- 识别率低 → 显示文字让用户确认
```

### 知识库检索失败

```
- 向量库不可用 → 跳过知识库，直接走 LLM
- Embedding 失败 → 使用 BM25 关键词检索兜底
```
