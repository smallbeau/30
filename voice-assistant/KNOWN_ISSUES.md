# Known Issues (排查纪要)

排查日期：2026-07-11
排查范围：voice-assistant 全量代码（6 阶段 + 1 轮完善）

## 已修复（17 项）

| # | 问题 | 文件 | 修复方式 | 提交 |
|---|------|------|----------|------|
| 1 | intent 结果被丢弃 | agent/engine.py | 问候/告别/帮助走快速回复 | 38c9c1a |
| 2 | 同步 ASR 阻塞事件循环 | voice/full_duplex/gateway.py | run_in_executor | 38c9c1a |
| 3 | VAD 配置硬编码 | voice/pipeline.py, api/voice.py | 加载 vad.yaml | 38c9c1a |
| 4 | 冗余 import | api/knowledge.py | 移除重复行 | 38c9c1a |
| 5 | requirements.txt 脏数据 | requirements.txt | 改干净列表 | 38c9c1a |
| 6 | 空目录无说明 | avatar/, sync/ | 加占位文档 | 38c9c1a |
| 7 | WS 无 PCM 限制异常处理 | api/voice.py | 补 PCMBufferLimitError | 待提交 |
| 8 | WS JSON 解析失败无提示 | api/voice.py | 补 ValueError 处理 | 待提交 |
| 9 | WS 冗余 import | api/voice.py | 移至顶部 | 待提交 |
| 10 | ShortTermMemory/SQLite 统一到 MySQL | 全量 | MySQL 连接池 + 三表 | 595eeca |
| 11 | _stream_wrapper 嵌套两层函数 | api/voice.py | 移除工厂函数，直接内联 async gen | 待提交 |
| 12 | SessionStore.close() 为 no-op | database/session_store.py, database/mysql.py | 改调 close_pool()，加 atexit 注册 | 待提交 |
| 13 | get_memory() 与 get_engine() 各开独立连接 | api/deps.py | MySQL 迁移后两者共享同一连接池 | 595eeca |

## 未修复（已知不紧急，共 1 项）

| # | 问题 | 文件 | 影响 | 优先级 |
|---|------|------|------|--------|
| B | CosyVoiceTTS 是彻底空桩 | voice/tts.py:40-41 | 始终 raise NotImplementedError，已标记为不可用；模型本身未部署，属设计决策 | 低 |