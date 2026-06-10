# Implementation Plan: 拟人化聊天机器人

## Overview

构建一个部署在 QQ（后续扩展至 Discord/微信）上的拟人化聊天机器人核心系统。
项目采用拟人中间件架构，在 LLM API 外层封装人格引擎、行为调度器、记忆系统和演化引擎。

## Architecture Decisions

| 决策 | 选择 | 理由 |
|------|------|------|
| QQ 接入方案 | NoneBot2 + NapCat | 社区最活跃，异步原生，插件生态好 |
| LLM 调用方式 | 流式（streaming） | 支持逐字输出模拟打字效果 |
| 人格注入方式 | System Prompt + Few-shot | MVP 阶段最快，后续可升级为 LoRA 微调 |
| 记忆持久化 | ChromaDB + SQLite | Chroma 存语义向量，SQLite 存结构化事实 |
| 配置格式 | TOML | 比 JSON 可读性好，比 YAML 更简单 |
| 异步运行时 | asyncio + nonebot 事件循环 | NoneBot2 原生异步，无需额外框架 |

## Dependency Graph

```
Task 1 (项目骨架)
   │
   ├── Task 2 (数据模型 + 配置系统)
   │       │
   │       ├── Task 3 (LLM 接口) ──┐
   │       │                       │
   │       ├── Task 4 (平台抽象)    ├── Task 6 (人格引擎)
   │       │       │               │
   │       │       └── Task 5 (QQ) │
   │       │                       │
   │       ├── Task 7 (行为调度器) ──┘
   │       │
   │       ├── Task 8 (记忆系统) ──→ Task 9 (演化引擎)
   │       │
   │       └── Task 10 (知识库 RAG)
   │
   ├── Task 11 (数据处理工具)
   │
   └── Task 12 (主入口集成) ←── 所有上游
```

## Task List

---

### Phase 1: 骨架搭建 — Foundation

#### Task 1: 项目初始化与环境配置

**Description:** 创建完整的项目目录结构、Python 虚拟环境、依赖管理文件和 Git 配置。
这是所有后续开发的基础。

**Acceptance criteria:**
- [ ] 项目目录结构与 SPEC.md 一致
- [ ] `pyproject.toml`、`requirements.txt` 配置正确
- [ ] `.gitignore` 排除 `data/`、`.venv/`、`__pycache__`、`.env`
- [ ] `python -m venv .venv` 后 `pip install -r requirements.txt` 成功

**Verification:**
- [ ] `python --version` ≥ 3.11
- [ ] `pip install -r requirements.txt` 无报错
- [ ] `git status` 显示已忽略正确文件

**Dependencies:** None

**Files likely touched:**
- `pyproject.toml`
- `requirements.txt`
- `requirements-dev.txt`
- `.gitignore`
- `README.md`
- `.env.example`
- `src/__init__.py`

**Estimated scope:** Small (1-2 files → 实际多个但都是配置)

---

#### Task 2: 配置系统与数据模型

**Description:** 实现全局配置加载（TOML + 环境变量覆盖）和所有 Pydantic 数据模型。
数据模型包括：消息模型、人格配置模型、记忆数据模型、情绪状态模型。

**Acceptance criteria:**
- [ ] `src/config.py` 能加载 `configs/default.toml`，支持环境变量覆盖
- [ ] 所有 Pydantic 模型定义在 `src/models/` 下
- [ ] `PersonalityConfig` 包含性格维度、知识偏好、情绪参数
- [ ] `Message` 模型支持平台无关的抽象消息结构
- [ ] `MemoryItem` 模型支持向量化存储

**Verification:**
- [ ] `python -c "from src.config import load_config; cfg = load_config(); print(cfg)"` 正常
- [ ] `python -c "from src.models.personality import PersonalityConfig; print(PersonalityConfig())"` 正常
- [ ] `pytest tests/ -v -k "model"` 通过

**Dependencies:** Task 1

**Files likely touched:**
- `src/config.py`
- `src/models/__init__.py`
- `src/models/message.py`
- `src/models/personality.py`
- `src/models/memory.py`
- `configs/default.toml`
- `tests/test_models.py`

**Estimated scope:** Medium (3-5 files)

---

#### Task 3: LLM 接口抽象层 + DeepSeek 实现

**Description:** 定义 `BaseLLM` 抽象接口（支持同步/流式两种调用模式），
实现 DeepSeek API 适配器。支持 streaming 输出、重试机制、Token 用量统计。

**Acceptance criteria:**
- [ ] `BaseLLM` 定义 `async chat()` 和 `async chat_stream()` 接口
- [ ] `DeepSeekLLM` 实现支持配置 model/temperature/max_tokens
- [ ] streaming 模式下支持逐块 yield
- [ ] 自动重试（指数退避，最多 3 次）
- [ ] API key 从环境变量读取，不硬编码

**Verification:**
- [ ] `pytest tests/ -v -k "llm"` 通过（mock 网络请求）
- [ ] 手动 mock 测试确认重试逻辑生效

**Dependencies:** Task 2

**Files likely touched:**
- `src/llm/__init__.py`
- `src/llm/base.py`
- `src/llm/deepseek.py`
- `tests/test_llm.py`

**Estimated scope:** Medium (3-4 files)

---

### ✅ Checkpoint 1: 骨架搭建完成

- [ ] `pip install -r requirements.txt` 无报错
- [ ] `pytest tests/` 核心测试通过
- [ ] 配置系统可正常运行
- [ ] LLM 接口 mock 测试通过
- [ ] **Review with human ✅**

---

### Phase 2: 平台接入 — Platform Integration

#### Task 4: 平台抽象层

**Description:** 定义平台无关的抽象基类，包括 `BaseBot`、`BaseMessage`、`BaseEvent`。
所有平台适配器继承自这些基类，确保核心逻辑与平台解耦。

**Acceptance criteria:**
- [ ] `BaseBot` 定义 `send_message()`、`on_message()`、`start()`、`stop()`
- [ ] `BaseMessage` 包含 sender、content、timestamp、message_type
- [ ] 平台事件模型通用化（私聊/群聊/系统事件）

**Verification:**
- [ ] `python -c "from src.platform.base import BaseBot; print(BaseBot.__abstractmethods__)"` 显示抽象方法列表
- [ ] 单元测试验证接口契约

**Dependencies:** Task 2

**Files likely touched:**
- `src/platform/__init__.py`
- `src/platform/base.py`
- `tests/test_platform_base.py`

**Estimated scope:** Small (2-3 files)

---

#### Task 5: QQ 平台接入（NoneBot2 + NapCat）

**Description:** 基于 NoneBot2 框架实现 QQ 平台适配器，通过 NapCat 连接 QQ。
实现消息收发、事件处理、错误重连、心跳保活。

**Acceptance criteria:**
- [ ] QQ 适配器继承 `BaseBot` 实现所有抽象方法
- [ ] 能连接 NapCat WebSocket 并接收消息
- [ ] 支持私聊和群聊消息收发
- [ ] 断线自动重连（指数退避）
- [ ] 所有 QQ 特有事件正确映射到通用事件模型

**Verification:**
- [ ] 启动后 NoneBot2 日志显示已连接 NapCat
- [ ] 手动 QQ 发消息，机器人能收到并回复
- [ ] `pytest tests/ -v -k "qq"` 通过

**Dependencies:** Task 4

**Files likely touched:**
- `src/platform/qq.py`
- `tests/test_platform_qq.py`

**Estimated scope:** Medium (2-3 files)

---

### ✅ Checkpoint 2: 平台接入完成

- [ ] QQ 机器人能正常收发消息
- [ ] 断线重连机制验证
- [ ] 平台抽象层接口稳定
- [ ] **Review with human ✅**

---

### Phase 3: 拟人中间件核心 — Core Middleware

#### Task 6: 人格引擎（Personality Engine）

**Description:** 核心模块——将性格配置转化为 LLM 可理解的 prompt 注入。
管理性格维度（开放度、幽默感、直率程度、话题偏好等）、情绪状态（情绪模型）。
支持从配置文件加载人格、实时查询当前人格状态。

**Acceptance criteria:**
- [ ] `PersonalityEngine` 接收 `PersonalityConfig` 配置
- [ ] `build_system_prompt()` 将性格维度转化为自然语言描述
- [ ] 情绪模型：对话情感分析 → 情绪状态更新 → 表达方式调整
- [ ] `apply_to_prompt(context)` 返回注入人格后的完整 prompt
- [ ] 提供人物设定的预设模板（可自定义）

**Verification:**
- [ ] `pytest tests/ -v -k "personality"` 通过
- [ ] 相同输入 + 不同人格配置 → 输出风格有明显差异
- [ ] 情绪状态随对话上下文变化

**Dependencies:** Task 2, Task 3

**Files likely touched:**
- `src/middleware/personality.py`
- `tests/test_personality.py`

**Estimated scope:** Medium (2-3 files)

---

#### Task 7: 行为调度器（Behavior Scheduler）

**Description:** 控制机器人的「人类行为特征」——打字延迟、发送节奏、作息规律、错别字模拟。
这是拟人化最直观可感知的模块。

**Acceptance criteria:**
- [ ] **打字延迟**：根据回复长度动态计算延迟（150ms-3s），用 streaming 模拟逐字输出
- [ ] **发送节奏**：长回复分段发送（每段间隔 0.5-2s）
- [ ] **作息规律**：配置活跃时段，非活跃时段延迟回复/告知在忙
- [ ] 支持随机扰动，避免模式化

**Verification:**
- [ ] `pytest tests/ -v -k "scheduler"` 通过
- [ ] 手动观察 QQ 机器人回复有自然延迟和分段效果
- [ ] 午夜测试：非活跃时段行为正确触发

**Dependencies:** Task 2, Task 3

**Files likely touched:**
- `src/middleware/scheduler.py`
- `tests/test_scheduler.py`

**Estimated scope:** Medium (2-3 files)

---

#### Task 8: 记忆系统（Memory System）

**Description:** 实现短期记忆（对话窗口上下文）和长期记忆（持久化重要信息）。
长期记忆使用 ChromaDB 存储语义向量 + SQLite 存储结构化事实。
支持记忆的写入、检索、总结和遗忘。

**Acceptance criteria:**
- [ ] **短期记忆**：维护对话窗口（默认 20 轮），自动截断老消息
- [ ] **长期记忆**：提取关键信息（偏好、事实、关系）存入 ChromaDB
- [ ] **记忆检索**：根据当前对话语义，检索相关历史记忆注入 prompt
- [ ] **记忆管理**：自动摘要旧记忆、按重要性分级
- [ ] **遗忘机制**：不活跃记忆逐渐衰减权重

**Verification:**
- [ ] `pytest tests/ -v -k "memory"` 通过
- [ ] 多轮对话后询问之前提到过的事实 → 能正确回忆
- [ ] ChromaDB 数据持久化和重启加载正常

**Dependencies:** Task 2, Task 3

**Files likely touched:**
- `src/middleware/memory.py`
- `tests/test_memory.py`

**Estimated scope:** Large (5-6 files, 含 ChromaDB 封装)

---

### ✅ Checkpoint 3: 拟人中间件核心完成

- [ ] 人格引擎可配置并影响对话风格
- [ ] 行为调度器产生自然的人类交互节奏
- [ ] 记忆系统支持跨会话回忆
- [ ] 三者集成后端到端对话测试通过
- [ ] **Review with human ✅**

---

### Phase 4: 高级能力 — Advanced Features

#### Task 9: 演化引擎（Evolution Engine）

**Description:** 实现性格随时间和事件的渐进演化——这是本项目的核心差异化功能。
包括时间驱动的性格漂移和事件驱动的性格突变。

**Acceptance criteria:**
- [ ] **时间漂移**：性格参数按配置的速率随时间缓慢变化（如越来越开放）
- [ ] **事件驱动**：特定类型的事件（深度对话、冲突、用户反馈）触发性格调整
- [ ] **演化记录**：所有性格变化被记录，支持回滚到历史版本
- [ ] **演化可控**：用户可冻结性格、设定演化速率、指定期望方向
- [ ] **一致性保障**：变化是渐变（sigmoid），不会突然"人格分裂"

**Verification:**
- [ ] `pytest tests/ -v -k "evolution"` 通过
- [ ] 模拟 30 天时间线 → 性格参数出现可测量的渐变
- [ ] 模拟特定事件 → 性格参数相应调整

**Dependencies:** Task 6, Task 8

**Files likely touched:**
- `src/middleware/evolution.py`
- `tests/test_evolution.py`

**Estimated scope:** Medium (2-3 files)

---

#### Task 10: 知识库与 RAG 检索

**Description:** 构建向量知识库，支持基于角色的知识偏好注入。
使机器人在特定话题上表现出更深的知识和更强的兴趣。

**Acceptance criteria:**
- [ ] ChromaDB 封装支持文档增删改查
- [ ] 知识按主题分类，带兴趣权重
- [ ] RAG 检索：根据对话内容自动检索相关知识注入上下文
- [ ] 知识来源可以是文件、网页、用户提供

**Verification:**
- [ ] `pytest tests/ -v -k "knowledge"` 通过
- [ ] 配置某话题权重高 → 对话中该话题被主动提起

**Dependencies:** Task 2

**Files likely touched:**
- `src/knowledge/vector_store.py`
- `src/knowledge/retriever.py`
- `tests/test_knowledge.py`

**Estimated scope:** Medium (3-4 files)

---

#### Task 11: 数据处理工具

**Description:** 实现聊天数据导入和性格特征分析工具。
支持从 JSON/CSV/HTML 格式导入聊天记录，自动提取语言风格特征。

**Acceptance criteria:**
- [ ] `tools/import_chat.py` 支持导入 JSON 格式聊天记录
- [ ] 数据清洗：去重、脱敏（替换真实姓名/电话）
- [ ] `tools/analyze_profile.py` 分析语言特征：词汇偏好、句式、情感倾向、回复模式
- [ ] 分析结果可导出为人格配置（`PersonalityConfig`）

**Verification:**
- [ ] `python -m tools.import_chat --help` 显示完整 CLI 参数
- [ ] 用测试数据运行导入 + 分析管线
- [ ] 分析结果可被人格引擎加载

**Dependencies:** Task 2, Task 6 (间接)

**Files likely touched:**
- `src/data/importer.py`
- `src/data/profiler.py`
- `tools/import_chat.py`
- `tools/analyze_profile.py`
- `tests/test_data_pipeline.py`

**Estimated scope:** Large (5-6 files)

---

### ✅ Checkpoint 4: 高级能力完成

- [ ] 演化引擎在 30 天模拟中产生可感知的性格变化
- [ ] 知识库 RAG 能影响对话内容偏好
- [ ] 数据处理工具成功导入测试数据并产出分析报告
- [ ] 完整对话管线（QQ → 中间件 → LLM → 回复）端到端通过
- [ ] **Review with human ✅**

---

### Phase 5: 集成与交付 — Integration & Polish

#### Task 12: 主入口与模块集成

**Description:** 实现 `src/main.py` 主入口，将所有模块组装成完整的运行系统。
包括启动流程、模块初始化顺序、优雅关闭、日志系统。

**Acceptance criteria:**
- [ ] 启动流程：加载配置 → 初始化 LLM → 初始化中间件 → 连接平台
- [ ] 消息处理管线完整：接收 → 调度器 → 人格引擎 → 记忆检索 → LLM → 记忆写入 → 调度器发送
- [ ] 优雅关闭：保存记忆 → 关闭连接 → 释放资源
- [ ] 结构化日志（logging + 重要事件记录）
- [ ] 错误隔离：单个模块崩溃不影响整个系统

**Verification:**
- [ ] `python -m src.main --dry-run` 输出初始化流程但不连接平台
- [ ] 完整启动后 QQ 消息端到端处理
- [ ] `Ctrl+C` 优雅关闭无报错

**Dependencies:** Task 5, Task 6, Task 7, Task 8, Task 9, Task 10

**Files likely touched:**
- `src/main.py`
- `src/config.py`（可能微调）

**Estimated scope:** Small (1-2 files)

---

#### Task 13: 全模块测试覆盖与文档完善

**Description:** 补全测试覆盖，完善 README 和配置文档。
确保核心模块覆盖率 ≥ 80%。

**Acceptance criteria:**
- [ ] 核心模块（人格引擎、调度器、记忆系统、演化引擎）覆盖率 ≥ 80%
- [ ] README.md 包含安装、配置、运行指南
- [ ] `configs/default.toml` 有完整注释
- [ ] `tests/` 下每个模块有正向和边界测试

**Verification:**
- [ ] `pytest tests/ --cov=src/ --cov-report=term` 覆盖率达标
- [ ] 按 README 步骤可独立完成环境搭建和运行

**Dependencies:** All previous tasks

**Files likely touched:**
- `README.md`
- `tests/` 下各测试文件
- `configs/default.toml`（注释补充）

**Estimated scope:** Medium (3-5 files)

---

### ✅ Checkpoint 5: 最终验证

- [ ] 所有 13 个任务完成
- [ ] `pytest tests/ --cov=src/ --cov-report=term` 覆盖率 ≥ 80%
- [ ] QQ 机器人端到端对话 20 轮无异常
- [ ] 导入测试数据后性格分析工具可产出有效结果
- [ ] 演化引擎在模拟中产生可测量变化
- [ ] 跨平台抽象层接口完备，可接入第二个平台
- [ ] **🎉 Final review with human**

---

## 执行顺序建议

```
并行起点:
  Task 1 ──→ Task 2 ──→ Task 3 ──┐
                                  │
                        Task 4 ──┤
                            │    ├──→ Task 6 ──→ Task 9
                            │    │
                            │    ├──→ Task 7
                            │    │
                            │    ├──→ Task 8
                            │    │
                     Task 5 ──┘    Task 10
                                   Task 11
                                      │
                                   Task 12 ──→ Task 13
```

建议按顺序依次执行，因为每个任务都依赖于前面的成果。

## Risks and Mitigations

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| NapCat 方案被封或不可用 | 高 | 预研多方案（LLOneBot 作为备选） |
| DeepSeek API 延迟不稳定 | 中 | 缓存常见回复，本地模型作为 fallback |
| ChromaDB 长期运行后膨胀 | 中 | 定期归档和压缩策略 |
| 性格演化失控（人格不一致） | 低 | 演化边界限制 + 用户可冻结/回滚 |
| 个人数据隐私泄露 | 高 | 所有数据本地处理，严格不上传 |

## Open Questions

| 问题 | 决策时机 |
|------|---------|
| NapCat 还是 LLOneBot？ | Task 5 开始时决定（取决于当前兼容性） |
| DeepSeek 具体模型版本（deepseek-chat vs deepseek-reasoner） | Task 3 实现时 |
| 演化曲线的具体数学形式（线性/sigmoid/分段） | Task 9 实现时 |
| 聊天记录导入首选格式 | Task 11 实现时 |
