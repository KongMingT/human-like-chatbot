# Spec: 拟人化聊天机器人（Human-like Chatbot）

## Objective

构建一个部署在即时通讯平台上的拟人化聊天机器人，其行为高度接近真人，人格可定制，
并能通过个人数据训练和对话经验逐步演化性格。

### 目标用户
- 个人用户，用于娱乐/角色扮演场景
- 需要一个「数字分身」在 QQ 等平台与人自然交流

### 成功标准
- ✅ 机器人对话响应自然度评分 > 7/10（人工盲测）
- ✅ 人格特征在对话中可被第三方明确感知
- ✅ 个人数据导入后，机器人语言风格向数据源趋近
- ✅ 跨平台支持 ≥ 2 个平台（QQ + Discord）
- ✅ 机器人能记住跨会话的长期信息

## Tech Stack

| 层级 | 技术选型 | 版本 |
|------|---------|------|
| 主语言 | Python | ≥3.11 |
| QQ 接入 | NapCat + NoneBot2 | latest |
| LLM API | DeepSeek API（初期） | latest |
| 本地模型 | Qwen2.5（后期量化部署） | 4bit |
| 向量数据库 | ChromaDB | latest |
| 结构化存储 | SQLite（aiosqlite） | 内置 |
| 微调框架 | Unsloth + LoRA | latest |
| 依赖管理 | pip + venv | — |
| 异步框架 | asyncio | 标准库 |

## Commands

```bash
# 环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 运行
python -m src.main                    # 启动机器人
python -m src.main --config custom.toml  # 指定配置

# 数据工具
python -m tools.import_chat --file export.json   # 导入聊天数据
python -m tools.analyze_profile --file data.json # 分析性格特征

# 测试
pytest tests/ -v                       # 运行全部测试
pytest tests/ -v -k "memory"           # 运行特定模块测试
pytest tests/ --cov=src/ --cov-report=term  # 带覆盖率

# 代码质量
ruff check src/ tests/                 # 静态检查
ruff format src/ tests/                # 自动格式化
mypy src/                              # 类型检查
```

## Project Structure

```
weichat-AI/
├── docs/                       # 文档
│   └── ideas/                  # 方案构思
│       └── human-like-chatbot.md
├── src/
│   ├── __init__.py
│   ├── main.py                 # 入口：启动/配置加载
│   ├── config.py               # 全局配置（TOML/YAML）
│   │
│   ├── platform/               # 平台适配层
│   │   ├── __init__.py
│   │   ├── base.py             # 抽象基类：Message, Event, Bot
│   │   ├── qq.py               # QQ 实现（NoneBot2 + NapCat）
│   │   └── discord.py          # Discord 实现（后续）
│   │
│   ├── middleware/             # 拟人化中间件
│   │   ├── __init__.py
│   │   ├── personality.py     # 人格引擎：性格维度、情绪模型
│   │   ├── scheduler.py       # 行为调度器：延迟、作息、节奏
│   │   ├── memory.py          # 记忆系统：短期+长期
│   │   └── evolution.py       # 演化引擎：时间/事件驱动的性格渐变
│   │
│   ├── llm/                   # 大模型接口
│   │   ├── __init__.py
│   │   ├── base.py            # LLM 抽象接口
│   │   ├── deepseek.py        # DeepSeek API 实现
│   │   └── local.py           # 本地模型实现（后期）
│   │
│   ├── knowledge/             # 知识库 & RAG
│   │   ├── __init__.py
│   │   ├── vector_store.py    # ChromaDB 封装
│   │   └── retriever.py       # 检索增强生成
│   │
│   ├── data/                  # 数据处理
│   │   ├── __init__.py
│   │   ├── importer.py        # 聊天记录导入器
│   │   └── profiler.py        # 性格特征提取器
│   │
│   └── models/                # 数据模型（Pydantic）
│       ├── __init__.py
│       ├── message.py         # 消息模型
│       ├── personality.py     # 人格配置模型
│       └── memory.py          # 记忆数据模型
│
├── tests/                     # 测试
│   ├── conftest.py
│   ├── test_personality.py
│   ├── test_scheduler.py
│   ├── test_memory.py
│   └── test_evolution.py
│
├── data/                      # 本地数据（不提交到 Git）
│   ├── chat_exports/          # 导入的聊天记录
│   ├── profiles/              # 生成的性格特征
│   └── chroma_db/             # ChromaDB 持久化目录
│
├── configs/                   # 配置文件
│   └── default.toml           # 默认配置
│
├── tools/                     # 辅助工具
│   ├── import_chat.py         # 聊天数据导入CLI
│   └── analyze_profile.py     # 性格分析CLI
│
├── scripts/                   # 脚本
│   └── setup.sh               # 环境初始化
│
├── SPEC.md                    # 本文件
├── requirements.txt           # 生产依赖
├── requirements-dev.txt       # 开发依赖
├── pyproject.toml             # 项目元数据
└── README.md                  # 项目说明
```

## Code Style

### 命名约定
- **模块/包**：全小写，下划线分隔（`personality.py`, `vector_store.py`）
- **类**：PascalCase（`PersonalityEngine`, `MemorySystem`）
- **函数/方法**：snake_case（`process_message()`, `get_typing_delay()`）
- **常量**：UPPER_SNAKE_CASE（`DEFAULT_TYPING_DELAY`）
- **私有**：前导下划线（`_calculate_mood()`）

### 异步优先
所有 I/O 操作用 `async/await`，必要时用 `asyncio.run()`。

```python
# 好风格示例
class PersonalityEngine:
    """人格引擎：管理性格特征配置和情绪状态。"""

    def __init__(self, config: PersonalityConfig):
        self._config = config
        self._mood: MoodState = MoodState.neutral

    async def apply_personality(
        self,
        prompt: str,
        context: ConversationContext,
    ) -> str:
        """将人格特征注入到 LLM prompt 中。"""
        traits = self._build_trait_prompt()
        mood_desc = self._describe_current_mood()
        return f"{traits}\n{mood_desc}\n\n用户说: {prompt}"
```

### 类型注解
所有函数签名必须含类型注解，使用 `|` 而非 `Optional`。

### 错误处理
- 自定义异常继承自 `ChatbotError`
- 外部 API 调用含重试和优雅降级
- 不吞异常，不 `except: pass`

## Testing Strategy

| 层级 | 框架 | 位置 | 覆盖目标 |
|------|------|------|---------|
| 单元测试 | pytest | `tests/` | 人格引擎、调度器、记忆系统等核心逻辑 |
| 集成测试 | pytest + httpx | `tests/` | LLM API 交互、数据库存取 |
| E2E 测试 | 手动 + 脚本 | 单独文档 | 实际 QQ 对话验证 |

### 要求
- 核心逻辑测试覆盖率 ≥ 80%
- 每个模块至少有一个正向测试和一个边界测试
- LLM API 调用用 `pytest-httpx` mock 掉，不依赖真实网络
- 测试数据用 `tests/fixtures/` 中的静态文件

## Boundaries

### Always ✅
- 运行测试后再提交代码
- 所有函数的 public 签名写类型注解
- 异步函数用 `async/await` 而非 `asyncio.get_event_loop()`
- 写 docstring（至少单行）
- 新模块添加对应的测试文件
- 配置文件和环境变量分离（.env 文件）
- 数据文件（聊天记录、数据库）加入 `.gitignore`

### Ask First 🤔
- 新增外部依赖（pip install 任何新包）
- 数据库 schema 变更
- 引入新的 LLM 模型（增加 provider）
- 修改项目结构（移动目录、创建新顶层目录）
- 接入新平台（微信、Telegram 等）
- 任何涉及用户数据出本机的操作

### Never 🚫
- 提交 API Key / Token / 密钥到 Git
- 将用户聊天记录提交到 Git
- 使用 `except: pass` 静默吞异常
- 在未 mock 的情况下运行依赖外部 API 的测试
- 修改 `__pycache__`、`.venv` 等生成目录中的内容
- 移除失败的测试而不修复或标记

## Success Criteria

- [ ] **MVP 可运行**：启动后 QQ 机器人正常接收和回复消息
- [ ] **拟人行为可感知**：回复有打字延迟、作息规律、语气自然
- [ ] **人格可配置**：修改配置文件后，机器人语言风格有明显变化
- [ ] **长期记忆**：跨会话记住用户提到的重要信息
- [ ] **数据导入**：聊天记录导入后，可分析出性格特征
- [ ] **性格演化**：运行多日后，性格参数出现可测量的渐变
- [ ] **跨平台**：同一人格配置可在 ≥2 个平台上运行

## Open Questions

| 问题 | 状态 |
|------|------|
| NapCat + NoneBot2 的当前兼容性如何？ | 🔄 待调研 |
| DeepSeek API 的并发限制和成本？ | 🔄 待验证 |
| 性格演化的幅度控制——渐变曲线用线性还是 sigmoid？ | 🔄 实现时决定 |
| 是否需要支持多用户/多角色？ | 🔄 MVP 先支持单角色 |
| 聊天记录导入支持哪些格式？（JSON/CSV/HTML） | 🔄 先支持通用 JSON |
