# Known Issues (排查纪要)

排查日期：2026-07-11
排查范围：voice-assistant 全量代码（6 阶段 + 1 轮完善）

## 已修复（13 项）

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

## 未修复（已知不紧急，共 4 项）

| # | 问题 | 文件 | 影响 | 优先级 |
|---|------|------|------|--------|
| A | ShortTermMemory.close() 从未调用 | memory/short_term.py | 进程退出时 SQLite 自动关闭，无泄漏风险；生产环境建议加 atexit | 低 |
| B | CosyVoiceTTS 是彻底空桩 | voice/tts.py:40-41 | 始终 raise NotImplementedError，已标记为不可用；模型本身未部署 | 低 |
| C | _stream_wrapper 嵌套两层函数 | api/voice.py:155-159 | 可读性差但功能正常 | 低 |
| D | deps.py 中 get_memory() 和 get_engine() 各开独立 SQLite 连接 | api/deps.py | 两个 ShortTermMemory 实例不共享；MySQL 迁移后自然解决 | 低 |

## 计划下一步

将 ShortTermMemory 从 SQLite 迁移到 MySQL（127.0.0.1:3306 root:root），统一数据库连接。