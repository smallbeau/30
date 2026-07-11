# 语音控制 AI 助手

中文语音 AI 助手，支持语音对话、技能调用、知识库优先回答。

## 快速启动

### 后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
cp .env.example .env
# 编辑 .env 填入 DEEPSEEK_API_KEY
uvicorn app.main:app --reload --port 8000
```

验证: `curl http://127.0.0.1:8000/health` → `{"ok":true}`

### 前端

```bash
cd web
npm install
npm run dev
```

打开 http://localhost:5173

## 已知限制

- Phase 1 服务端 ASR 未启用（使用浏览器语音识别）
- 仅支持 DeepSeek/OpenAI 兼容模型
- 需要 API Key 才能调用 LLM

## 多阶段开发说明

本仓库采用 6 阶段渐进式构建，后续阶段会修改此阶段创建的文件:

| 文件 | 被修改的阶段 | 合并策略 |
|------|------------|---------|
| `app/config.py` | Phase 1(创建)、2、4、5 | 每次追加新配置项，不删除/重命名已有字段 |
| `app/api/voice.py` | Phase 1(创建)、2、4、5 | 追加 WebSocket 路由，不修改已有路由签名 |
| `app/main.py` | Phase 1(创建)、2、4 | 追加 include_router，不删除已有路由 |
| `app/voice/` 子模块 | Phase 1(创建)、2、5 | 新增文件扩展能力，不修改已有文件结构 |
| `app/agent/engine.py` | Phase 1(创建)、3 | Phase 3 仅注入记忆调用，不修改 handle/stream_handle 签名 |

每个阶段计划开头标注了"前置条件：前阶段代码已完成并通过测试"。