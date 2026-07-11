# Handoff: 语音 AI 助手全阶段计划

**日期**: 2026-07-10
**会话**: 设计评审 + 第一阶段计划已完成，需继续撰写第二～六阶段计划

## 已完成

- **设计文档**: `docs/superpowers/specs/2026-07-10-voice-assistant-design.md`（800行，含竞品分析、架构、优化路线图）
- **第一阶段计划**: `docs/superpowers/plans/2026-07-10-voice-assistant-phase1.md`（10任务，1446行）
  - 范围：Agent Engine + Skill Runner + RAG + LLM 接入 + 伪全双工 + Web MVP
  - 使用 `writing-plans` 技能撰写，含完整代码、测试、commit 步骤
- **用户决定**: 先写齐六个阶段计划再开始实现

## 当前状态

- 项目根目录 `E:\Project\30\` 下尚无代码（`voice-assistant/` 目录未创建）
- 第一阶段计划已可通过 subagent-driven-development 或 inline 执行
- 第二～六阶段计划尚未撰写

## 待完成

| 阶段 | 内容 | 状态 |
|------|------|------|
| 二 | 语音增强：Porcupine 唤醒 + 服务端 ASR + CosyVoice TTS + 延迟优化 | ❌ 未写 |
| 三 | 三层记忆系统 + 10+ 预置 Skill | ❌ 未写 |
| 四 | 虚拟数字人（LivePortrait/SadTalker + 口型同步） | ❌ 未写 |
| 五 | 真全双工（Mini-Omni/Moshi）+ 语音克隆 | ❌ 未写 |
| 六 | 多端（Android/小程序）+ Supabase 同步 + 插件市场 | ❌ 未写 |

## 设计依据

所有阶段的规格依据同一份设计文档：`docs/superpowers/specs/2026-07-10-voice-assistant-design.md`

关键架构决策已在设计文档中锁定：
- Edge+Cloud 混合架构
- Markdown 声明式 Skill
- OpenAI 兼容 LLM 接入
- 六阶段渐进式路线图（先半双工 MVP → 再真全双工）

## 建议技能

- `writing-plans` — 撰写每个阶段的实现计划
- `subagent-driven-development` — 之后执行计划时推荐使用
- `brainstorming` — 如果某个阶段需求需要细化，先头脑风暴团队通信

## 架构复用

每个阶段的计划应复用 Phase 1 的文件结构和命名约定：
- 计划保存到 `docs/superpowers/plans/YYYY-MM-DD-voice-assistant-phase{N}.md`
- 每个计划的 Tasks 遵循 writing-plans 技能的小步骤模式
- 使用 TDD（先测试、后实现）
- 本阶段不做的不在计划中实现（明确边界）