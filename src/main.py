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
from src.config import load_config, SleepState
from src.llm.deepseek import DeepSeekLLM
from src.middleware.personality import PersonalityEngine
from src.middleware.scheduler import BehaviorScheduler
from src.middleware.memory import MemorySystem
from src.middleware.evolution import EvolutionEngine
from src.middleware.growth import GrowthEngine
from src.middleware.media_handler import MediaHandler
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

    def __init__(self, config_path: str | None = None, web_enabled: bool = False, web_port: int = 8080):
        self.config = load_config(config_path)
        self._running = False
        self._web_enabled = web_enabled
        self._web_port = web_port

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

        logger.info("初始化成长引擎...")
        self.growth = GrowthEngine(self.config.evolution)

        logger.info("初始化媒体处理器...")
        self.media = MediaHandler()

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
        # 1. 获取当前睡眠状态
        sleep_state = self.scheduler.get_sleep_state()

        # 2. 根据睡眠状态决定是否回复
        session_id = message.sender_id

        if not self.scheduler.should_respond(sleep_state):
            # 没醒 → 完全不回复
            return None

        # 3. 如果在睡眠时段刚回复过，不再重复吵醒（冷却 3 分钟）
        if sleep_state != SleepState.AWAKE and self.scheduler.was_just_woken(session_id):
            return None

        # 4. 记录对话交互（用于疲劳度计算）
        self.scheduler.record_interaction(session_id)

        # 5. 疲劳度检查：太累了就直接不回，模拟「不想聊了」
        fatigue_behavior = self.scheduler.get_fatigue_behavior(session_id)
        if fatigue_behavior["ending_chance"] > 0:
            import random as _random
            if _random.random() < fatigue_behavior["ending_chance"]:
                logger.info(f"疲劳度过高 ({self.scheduler.get_fatigue_level(session_id)})，不回复")
                return None

        # 6. 构建对话上下文
        ctx = ConversationContext(
            messages=[],
            current_message=message,
            platform=message.platform,
            session_id=session_id,
        )

        # 7. 加载短期记忆
        stm = self.memory.get_short_term(session_id)
        for msg in stm.messages:
            ctx.messages.append(Message(
                content=msg["content"],
                role=MessageRole.USER if msg["role"] == "user" else MessageRole.BOT,
            ))

        # 8. 注入当前时间到对话上下文（紧挨用户消息前，确保被看到）
        from datetime import datetime as _dt
        _now = _dt.now()
        _time_str = _now.strftime("%Y年%m月%d日 %H:%M")
        _weekday = ["一", "二", "三", "四", "五", "六", "日"][_now.weekday()]
        ctx.messages.append(Message(
            content=f"[当前时间：{_time_str}，星期{_weekday}]",
            role=MessageRole.SYSTEM,
        ))

        # 9. 添加当前消息
        ctx.messages.append(message)

        # 10. 检索长期记忆
        relevant_memories = await self.memory.get_relevant_memories(
            message.content, session_id
        )

        # 11. 构建 system prompt（人格注入 + 睡眠情境 + 语气适应 + 疲劳）
        sleep_context = self.scheduler.get_sleep_context(sleep_state)
        system_prompt = self.personality.apply_to_prompt(ctx, sleep_context=sleep_context)

        # 语气适应：注入学到的用词
        tone_prompt = self.growth.get_adapted_tone_prompt()
        if tone_prompt:
            system_prompt += f"\n\n{tone_prompt}"

        # 对话疲劳注入
        fatigue_ctx = self.scheduler.get_fatigue_context(session_id)
        if fatigue_ctx:
            system_prompt += f"\n\n{fatigue_ctx}"

        # 添加记忆上下文
        if relevant_memories:
            memory_context = "\n".join([
                f"[记忆] {m.content}" for m in relevant_memories
            ])
            system_prompt += f"\n\n你记得关于这个人的以下信息：\n{memory_context}"

        # 图片感知：如果消息包含图片，注入描述
        if message.has_media and message.images:
            img_descs = []
            for img in message.images:
                summary = img.get("summary", "[图片]")
                if summary and summary != "[图片]":
                    img_descs.append(f"[对方发了一张图片: {summary}]")
                else:
                    img_descs.append("[对方发了一张图片]")
            # 追加到当前消息内容
            message.content += " " + " ".join(img_descs)
            # 更新对话上下文中的最后一条消息
            if ctx.messages and ctx.messages[-1].role == MessageRole.USER:
                ctx.messages[-1].content = message.content

        # 12. 调用 LLM
        try:
            response = await self.llm.chat_with_context(
                ctx,
                system_prompt=system_prompt,
            )
            reply = response.content
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            # 睡眠时出错就不回复了
            if sleep_state != SleepState.AWAKE:
                return None
            return "嗯…我刚才走神了，能再说一遍吗？"

        # 13. 模拟打字延迟（受睡眠状态影响）
        await self.scheduler.typing_delay(len(reply), sleep_state)

        # 14. 应用随机口语化（睡眠时口语化频率更高）
        typo_freq = 0.15 if sleep_state != SleepState.AWAKE else None
        reply = self.personality.random_typo(reply, frequency=typo_freq)

        # 15. 后处理：截断过长的回复 + 替换不必要的叹号
        MAX_REPLY_LENGTH = 60
        if len(reply) > MAX_REPLY_LENGTH:
            # 在最后一个句子边界截断
            import re
            truncated = reply[:MAX_REPLY_LENGTH]
            last_boundary = max(
                truncated.rfind("。"), truncated.rfind("？"),
                truncated.rfind("！"), truncated.rfind("~"),
                truncated.rfind("…"),
            )
            if last_boundary > 10:
                reply = truncated[:last_boundary + 1]
            else:
                reply = truncated.rstrip(",.;，。；") + "…"

        # 16. 存储到短期记忆
        self.memory.add_to_short_term(session_id, "user", message.content)
        self.memory.add_to_short_term(session_id, "assistant", reply)

        # 17. 提取并存储重要事实
        await self.memory.extract_and_store_facts(message.content, session_id)

        # 18. 成长引擎：学习对方的用词和句式
        self.growth.learn_from_message(message.content, message.sender_id)

        # 19. 成长引擎：基于近期对话计算性格漂移
        recent_msgs = stm.messages[-20:] if len(stm.messages) >= 20 else stm.messages
        drift = self.growth.calculate_drift(
            self.personality.profile.current,
            recent_msgs,
        )
        if drift:
            self.personality.profile.current = self.personality.profile.current.apply_delta(drift)

        # 20. 演化检查（每 10 条消息检查一次）
        if len(stm.messages) > 0 and len(stm.messages) % 10 == 0:
            current_snapshot = self.personality.profile.current
            evolved = self.evolution.evolve(
                current_snapshot,
                days_passed=0.1,
                events=[{"type": "deep_conversation"}],
            )
            self.personality.profile.current = evolved

        # 21. 标记被吵醒（睡眠时段回复后进入冷却，下一条不再吵醒）
        if sleep_state != SleepState.AWAKE:
            self.scheduler.mark_woke_up(session_id)

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
            sleep_state = self.scheduler.get_sleep_state_name()
            logger.info(f"收到消息: [{msg.sender_name}] {msg.content[:50]} (状态:{sleep_state})")
            reply = await self.handle_message(msg)

            if reply:
                logger.info(f"回复: {reply[:50]}...")

                # 决定是否带表情包
                meme_path = None
                if self.media.has_memes():
                    mood_intensity = self.personality._mood.intensity
                    if self.media.should_send_meme(mood_intensity, len(reply)):
                        meme = self.media.pick_meme(
                            mood=self.personality._mood.state.value,
                            text=reply,
                        )
                        if meme:
                            meme_path = meme.path
                            logger.info(f"附带表情包: {meme.category}/{meme.id}")

                # 构建回复消息
                reply_msg = Message(
                    content=reply,
                    sender_id=msg.sender_id,
                    sender_name=self.config.bot.name,
                    role=MessageRole.BOT,
                    platform=msg.platform,
                    type=msg.type,
                    group_id=msg.group_id,
                    media_path=meme_path,
                )

                # 分段发送
                async def send(content: str):
                    reply_msg.content = content
                    await self.bot.send_message(reply_msg)

                await self.scheduler.split_and_send(reply, send)

        # 启动平台连接（后台自动重连）
        await self.bot.start()
        self._running = True

        # 启动 Web 管理界面（后台 asyncio 任务）
        if self._web_enabled:
            from web.app import start_web_async
            asyncio.create_task(start_web_async(port=self._web_port))

        logger.info(f"\n{'='*50}")
        logger.info(f"[ON] {self.config.bot.name} 已启动！")
        logger.info(f"   人格: {self.config.personality.name}")
        logger.info(f"   当前情绪: {self.personality._mood.state.value}")
        logger.info(f"   睡眠状态: {self.scheduler.get_sleep_state_name()}")
        logger.info(f"   Web 界面: http://127.0.0.1:{self._web_port}")
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

        # 保存记忆和成长数据
        self.memory.save_state()
        self.growth.save_state()
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
    parser.add_argument("--web", action="store_true",
                        help="同时启动 Web 管理界面 (http://127.0.0.1:8080)")
    parser.add_argument("--web-port", type=int, default=8080,
                        help="Web 管理界面端口 (默认 8080)")
    parser.add_argument("--web-only", action="store_true",
                        help="仅启动 Web 管理界面，不启动机器人")
    args = parser.parse_args()

    print(f"""
{'='*45}
   Human-like Chatbot
   拟人化聊天机器人 v{__version__}
{'='*45}
    """)

    # 仅启动 Web 界面
    if args.web_only:
        from web.app import start_web_async
        asyncio.run(start_web_async(port=args.web_port))
        return

    bot = ChatBot(args.config, web_enabled=args.web, web_port=args.web_port)

    if args.dry_run:
        asyncio.run(bot.run_dry())
    else:
        # web-only 模式在 main() 开头已经 return，不会走到这里
        try:
            asyncio.run(bot.start(check_connection=not args.no_check))
        except KeyboardInterrupt:
            logger.info("收到中断信号，正在退出...")


if __name__ == "__main__":
    main()
