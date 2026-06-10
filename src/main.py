"""主入口 — 组装所有模块并启动机器人。"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).parent.parent))

from src import __version__
from src.config import load_config
from src.llm.deepseek import DeepSeekLLM
from src.middleware.personality import PersonalityEngine
from src.middleware.scheduler import BehaviorScheduler
from src.middleware.memory import MemorySystem
from src.middleware.evolution import EvolutionEngine
from src.models.message import ConversationContext, Message, MessageRole


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("human-like-chatbot")


class ChatBot:
    """聊天机器人主控制器。

    组装所有模块，管理消息处理管线。
    """

    def __init__(self, config_path: str | None = None):
        self.config = load_config(config_path)
        self._running = False

        # 初始化模块
        logger.info("初始化 LLM 接口...")
        self.llm = DeepSeekLLM({
            "model": self.config.llm.model,
            "temperature": self.config.llm.temperature,
            "max_tokens": self.config.llm.max_tokens,
            "stream": self.config.llm.stream,
        })

        logger.info("初始化人格引擎...")
        self.personality = PersonalityEngine(self.config.personality)

        logger.info("初始化行为调度器...")
        self.scheduler = BehaviorScheduler(self.config.scheduler)

        logger.info("初始化记忆系统...")
        self.memory = MemorySystem(self.config.memory)

        logger.info("初始化演化引擎...")
        self.evolution = EvolutionEngine(self.config.evolution)

        # 平台相关的 bot（延迟初始化）
        self._bot = None

    @property
    def bot(self):
        """获取平台 bot（延迟加载）。"""
        if self._bot is None:
            self._init_bot()
        return self._bot

    def _init_bot(self):
        """初始化平台 bot。"""
        platform = self.config.bot.platform
        bot_config = {
            "host": self.config.qq_host,
            "port": self.config.qq_port,
            "access_token": self.config.qq_access_token,
        }

        if platform == "qq":
            from src.platform.qq import QQBot
            self._bot = QQBot(bot_config)
        else:
            raise ValueError(f"不支持的平台: {platform}")

    async def handle_message(self, message: Message) -> str | None:
        """处理单条消息，生成回复。

        消息处理管线：
        1. 行为调度器 → 检查是否应回复
        2. 人格引擎 → 注入性格特征
        3. 记忆系统 → 检索相关记忆
        4. LLM → 生成回复
        5. 记忆系统 → 存储新信息
        6. 演化引擎 → 检查事件驱动演化

        Args:
            message: 收到的用户消息

        Returns:
            生成的回复文本，或 None 如果不回复
        """
        # 1. 作息检查
        if not self.scheduler.should_respond():
            if not self.scheduler.is_active_hours():
                return self.scheduler.get_inactive_message()
            return None

        # 2. 构建对话上下文
        session_id = message.sender_id
        ctx = ConversationContext(
            messages=[],
            current_message=message,
            platform=message.platform,
            session_id=session_id,
        )

        # 3. 加载短期记忆
        stm = self.memory.get_short_term(session_id)
        for msg in stm.messages:
            ctx.messages.append(Message(
                content=msg["content"],
                role=MessageRole.USER if msg["role"] == "user" else MessageRole.BOT,
            ))

        # 4. 添加当前消息
        ctx.messages.append(message)

        # 5. 检索长期记忆
        relevant_memories = await self.memory.get_relevant_memories(
            message.content, session_id
        )

        # 6. 构建 system prompt（人格注入）
        system_prompt = self.personality.apply_to_prompt(ctx)

        # 添加记忆上下文
        if relevant_memories:
            memory_context = "\n".join([
                f"[记忆] {m.content}" for m in relevant_memories
            ])
            system_prompt += f"\n\n你记得关于这个人的以下信息：\n{memory_context}"

        # 7. 调用 LLM
        try:
            response = await self.llm.chat_with_context(
                ctx,
                system_prompt=system_prompt,
            )
            reply = response.content
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            return "嗯…我刚才走神了，能再说一遍吗？"

        # 8. 模拟打字延迟
        await self.scheduler.typing_delay(len(reply))

        # 9. 应用随机口语化
        reply = self.personality.random_typo(reply)

        # 10. 存储到短期记忆
        self.memory.add_to_short_term(session_id, "user", message.content)
        self.memory.add_to_short_term(session_id, "assistant", reply)

        # 11. 提取并存储重要事实
        await self.memory.extract_and_store_facts(message.content, session_id)

        # 12. 演化检查（每 10 条消息检查一次）
        if len(stm.messages) > 0 and len(stm.messages) % 10 == 0:
            current_snapshot = self.personality.profile.current
            evolved = self.evolution.evolve(
                current_snapshot,
                days_passed=0.1,  # 每次对话相当于 0.1 天
                events=[{"type": "deep_conversation"}],
            )
            self.personality.profile.current = evolved

        return reply

    async def start(self, check_connection: bool = True):
        """启动机器人。

        Args:
            check_connection: 是否检查平台连接可达性
        """
        logger.info(f"启动 {self.config.bot.name} v{self.config.bot.version}")
        logger.info(f"平台: {self.config.bot.platform}")
        logger.info(f"LLM: {self.config.llm.provider}/{self.config.llm.model}")

        # 加载记忆
        self.memory.load_state()

        # 检查 API Key
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        if not api_key:
            logger.warning("[!] DEEPSEEK_API_KEY 未设置！请在 .env 文件中配置")
        else:
            logger.info(f"[OK] DeepSeek API Key 已配置 ({api_key[:8]}...)")

        # 检查 NapCat 连接
        if check_connection and self.config.bot.platform == "qq":
            logger.info(f"正在检测 NapCat 连接: {self.bot.ws_url}...")
            import socket
            host = self.config.qq_host
            port = int(self.config.qq_port)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            try:
                result = sock.connect_ex((host, port))
                if result == 0:
                    logger.info(f"✓ NapCat 端口可达 ({host}:{port})")
                else:
                    logger.warning(
                        f"⚠ NapCat 未运行 ({host}:{port} 无响应)。\n"
                        f"  请确保 NapCat 已启动并配置了 WebSocket 服务。\n"
                        f"  启动后机器人将自动连接。"
                    )
                sock.close()
            except Exception:
                logger.warning(f"⚠ 无法检测 NapCat 连接状态")
            finally:
                sock.close()

        # 注册消息处理器
        @self.bot.on_message
        async def message_handler(msg: Message):
            logger.info(f"收到消息: [{msg.sender_name}] {msg.content[:50]}")
            reply = await self.handle_message(msg)

            if reply:
                logger.info(f"回复: {reply[:50]}...")

                # 构建回复消息
                reply_msg = Message(
                    content=reply,
                    sender_id=msg.sender_id,
                    sender_name=self.config.bot.name,
                    role=MessageRole.BOT,
                    platform=msg.platform,
                    type=msg.type,
                    group_id=msg.group_id,
                )

                # 分段发送
                async def send(content: str):
                    reply_msg.content = content
                    await self.bot.send_message(reply_msg)

                await self.scheduler.split_and_send(reply, send)

        # 启动平台连接（后台自动重连）
        await self.bot.start()
        self._running = True

        logger.info(f"\n{'='*50}")
        logger.info(f"[ON] {self.config.bot.name} 已启动！")
        logger.info(f"   人格: {self.config.personality.name}")
        logger.info(f"   当前情绪: {self.personality._mood.state.value}")
        logger.info(f"   等待 NapCat 连接: {self.bot.ws_url}")
        logger.info(f"   按 Ctrl+C 停止")
        logger.info(f"{'='*50}\n")

        # 保持运行
        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

    async def stop(self):
        """优雅关闭。"""
        logger.info("正在关闭...")

        if self._bot:
            await self.bot.stop()

        # 保存记忆
        self.memory.save_state()
        self._running = False
        logger.info("已关闭。再见 👋")

    async def run_dry(self):
        """干运行：检查配置和模块初始化但不连接平台。"""
        logger.info("=== 干运行模式 ===")
        logger.info(f"配置: {self.config.bot.name} / {self.config.bot.platform}")
        logger.info(f"人格: {self.config.personality.name}")
        logger.info(f"LLM: {self.config.llm.provider}/{self.config.llm.model}")
        logger.info(f"性格维度: {self.personality.profile.current.to_dict()}")
        logger.info(f"当前情绪: {self.personality._mood.state.value}")
        logger.info("干运行完成 — 配置正常，模块初始化成功。")
        return True


def main():
    """入口函数。"""
    import argparse

    parser = argparse.ArgumentParser(description="拟人化聊天机器人")
    parser.add_argument("--config", "-c", type=str, help="配置文件路径")
    parser.add_argument("--dry-run", action="store_true",
                        help="干运行模式：检查配置和模块初始化，不连接平台")
    parser.add_argument("--no-check", action="store_true",
                        help="跳过平台连接检测")
    args = parser.parse_args()

    print(f"""
{'='*45}
   Human-like Chatbot
   拟人化聊天机器人 v{__version__}
{'='*45}
    """)

    bot = ChatBot(args.config)

    if args.dry_run:
        asyncio.run(bot.run_dry())
    else:
        try:
            asyncio.run(bot.start(check_connection=not args.no_check))
        except KeyboardInterrupt:
            logger.info("收到中断信号，正在退出...")


if __name__ == "__main__":
    main()
