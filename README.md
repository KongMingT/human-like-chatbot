# Human-like Chatbot — 拟人化聊天机器人

一个部署在即时通讯平台上的拟人化聊天机器人，行为高度接近真人，人格可定制，
并能通过数据训练和个人对话经验逐步演化性格。

## 特性

- 🎭 **人格引擎** — 可配置的性格维度、情绪模型，让机器人拥有独特个性
- ⏱ **行为调度器** — 打字延迟、发送节奏、作息规律，模拟真人交互
- 🧠 **记忆系统** — 短期对话记忆 + 长期事实记忆，跨会话持续积累
- 🔄 **演化引擎** — 性格随时间和事件渐进演化，不再是静态AI
- 📊 **数据训练** — 导入聊天记录分析性格特征，注入个人风格
- 🔌 **跨平台** — QQ 优先，架构预留 Discord/微信扩展

## 快速开始

### 前置条件

- Python ≥ 3.11
- [NapCat](https://github.com/NapNeko/NapCatQQ) QQ 协议实现
- DeepSeek API Key（或其他兼容 API）

### 安装

```bash
# 克隆项目
git clone <repo-url>
cd weichat-AI

# 创建虚拟环境
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
# source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 配置

```bash
# 复制环境变量配置
cp .env.example .env
# 编辑 .env，填入你的 API Key
```

编辑 `configs/default.toml` 配置人格和行为参数。

### 运行

```bash
当前本地运行在虚拟环境：.\.venv\Scripts\Activate.ps1

python -m src.main

仅启动 Web 界面（不启动机器人）
.venv\Scripts\python.exe -m src.main --web-only

同时启动机器人和 Web 界面
.venv\Scripts\python.exe -m src.main --web

指定端口
.venv\Scripts\python.exe -m src.main --web --web-port 9090
```

## 项目结构

```
src/
├── main.py           # 主入口
├── config.py         # 配置加载
├── platform/         # 平台适配层（QQ/Discord）
├── middleware/       # 拟人中间件（人格/调度/记忆/演化）
├── llm/             # 大模型接口（DeepSeek/本地）
├── knowledge/       # 知识库 & RAG
├── data/            # 数据处理
└── models/          # 数据模型
```

## 数据工具

```bash
# 导入聊天记录
python -m tools.import_chat --file data/chat_exports/export.json

# 分析性格特征
python -m tools.analyze_profile --file data/chat_exports/export.json
```

## 许可

MIT
