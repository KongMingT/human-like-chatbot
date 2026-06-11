"""QQ 平台适配器 — 通过 WebSocket 直连 NapCat (OneBot v11 协议)。

不再依赖 NoneBot2 框架，直接使用 websockets 库连接 NapCat。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, AsyncGenerator

from src.models.message import Message, MessageRole, MessageType, PlatformEvent
from src.platform.base import BaseBot

logger = logging.getLogger("human-like-chatbot.qq")

try:
    import websockets
except ImportError:
    websockets = None  # type: ignore


class QQBot(BaseBot):
    """QQ 机器人适配器。

    通过原生 WebSocket 连接 NapCat 的 OneBot v11 接口。
    """

    def __init__(self, config: dict | None = None):
        config = config or {}
        super().__init__(config)
        self._running = False
        self._ws = None
        self._message_queue: asyncio.Queue[Message] = asyncio.Queue()
        self._bot_self_id: str = ""

        # 连接配置
        self.ws_host = config.get("host", os.getenv("QQ_HOST", "127.0.0.1"))
        self.ws_port = config.get("port", int(os.getenv("QQ_PORT", "6099")))
        self.access_token = config.get(
            "access_token", os.getenv("QQ_ACCESS_TOKEN", "")
        )

    @property
    def platform_name(self) -> str:
        return "qq"

    @property
    def is_connected(self) -> bool:
        return self._running and self._ws is not None

    @property
    def ws_url(self) -> str:
        return f"ws://{self.ws_host}:{self.ws_port}"

    async def start(self) -> None:
        """连接 NapCat WebSocket 并开始监听。"""
        if websockets is None:
            raise RuntimeError(
                "websockets 未安装。请执行: pip install websockets"
            )

        if self._running:
            return

        logger.info(f"正在连接 NapCat: {self.ws_url}")
        self._running = True

        # 启动 WebSocket 连接（自动重连）
        asyncio.create_task(self._connect_loop())

    async def _connect_loop(self):
        """WebSocket 连接循环（含自动重连）。"""
        retry_delay = 3
        max_retry_delay = 60

        while self._running:
            try:
                additional_headers = {}
                if self.access_token:
                    additional_headers["Authorization"] = f"Bearer {self.access_token}"

                async with websockets.connect(
                    self.ws_url,
                    additional_headers=additional_headers or None,
                    ping_interval=20,
                    ping_timeout=10,
                ) as ws:
                    self._ws = ws
                    logger.info(f"NapCat 已连接: {self.ws_url}")
                    retry_delay = 3  # 重置重试间隔

                    # 获取机器人自身信息
                    await self._get_login_info()

                    # 监听消息
                    await self._listen_loop(ws)

            except asyncio.CancelledError:
                break
            except Exception as e:
                if self._running:
                    logger.warning(
                        f"连接断开: {e}，{retry_delay}秒后重试..."
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 1.5, max_retry_delay)

        self._ws = None

    async def _get_login_info(self):
        """获取登录信息。"""
        result = await self._api_call("get_login_info")
        if result and "data" in result:
            self._bot_self_id = str(result["data"].get("user_id", ""))
            logger.info(f"机器人 QQ: {self._bot_self_id}")

    async def _listen_loop(self, ws):
        """消息监听循环。"""
        async for raw_msg in ws:
            try:
                data = json.loads(raw_msg)
                await self._handle_event(data)
            except json.JSONDecodeError:
                continue

    async def _handle_event(self, data: dict[str, Any]):
        """处理 OneBot 事件。"""
        post_type = data.get("post_type", "")

        if post_type == "message":
            message = self._parse_message(data)
            if message:
                await self._message_queue.put(message)
                await self.dispatch_message(message)

        elif post_type == "meta_event":
            pass  # 心跳等元事件忽略

        elif post_type == "notice":
            event = PlatformEvent(
                type=data.get("notice_type", ""),
                platform="qq",
                data=data,
            )
            await self.dispatch_event(event)

    def _parse_message(self, data: dict[str, Any]) -> Message | None:
        """将 OneBot 消息 JSON 解析为通用 Message。"""
        message_type = data.get("message_type", "")
        user_id = str(data.get("user_id", ""))
        group_id = str(data.get("group_id", "")) if data.get("group_id") else None

        # 提取纯文本和媒体
        raw_message = data.get("message", "")
        content = self._extract_text_from_segments(raw_message)

        # 提取图片信息
        images = []
        if isinstance(raw_message, list):
            for seg in raw_message:
                if seg.get("type") == "image":
                    img_data = seg.get("data", {})
                    images.append({
                        "url": img_data.get("url", ""),
                        "file": img_data.get("file", ""),
                        "summary": img_data.get("summary", "[图片]"),
                    })

        # 判断消息类型
        msg_type = MessageType.GROUP if message_type == "group" else MessageType.PRIVATE

        # 获取发送者信息
        sender = data.get("sender", {})
        sender_name = sender.get("card", "") or sender.get("nickname", "") or user_id

        # 判断是否 @ 了机器人
        is_mention = self._check_mention(raw_message)

        return Message(
            id=str(data.get("message_id", "")),
            platform="qq",
            type=msg_type,
            role=MessageRole.USER,
            sender_id=user_id,
            sender_name=sender_name,
            group_id=group_id,
            content=content,
            raw=data,
            is_mention=is_mention,
            has_media=len(images) > 0,
            images=images,
        )

    def _extract_text_from_segments(self, message: Any) -> str:
        """从消息段中提取纯文本。

        支持两种格式：
        1. 字符串格式: "你好"
        2. 数组格式: [{"type":"text","data":{"text":"你好"}}, ...]
        """
        if isinstance(message, str):
            return message

        if isinstance(message, list):
            texts = []
            for seg in message:
                if isinstance(seg, dict) and seg.get("type") == "text":
                    text = seg.get("data", {}).get("text", "")
                    if text:
                        texts.append(text)
            return "".join(texts)

        return str(message)

    def _check_mention(self, message: Any) -> bool:
        """检查是否 @ 了机器人。"""
        if isinstance(message, list):
            for seg in message:
                if isinstance(seg, dict) and seg.get("type") == "at":
                    target = seg.get("data", {}).get("qq", "")
                    if target == "all" or (self._bot_self_id and target == self._bot_self_id):
                        return True
        return False

    async def _api_call(self, action: str, params: dict | None = None) -> dict | None:
        """调用 OneBot API。"""
        if not self._ws:
            return None

        payload = {
            "action": action,
            "params": params or {},
        }
        try:
            await self._ws.send(json.dumps(payload))
            # 等待响应
            response = await asyncio.wait_for(self._ws.recv(), timeout=5.0)
            return json.loads(response) if isinstance(response, str) else response
        except Exception:
            return None

    async def send_message(self, message: Message) -> bool:
        """发送消息到 QQ。

        支持纯文本和图文混合消息。
        message.content 为文本内容。
        message.media_path 如有值，则作为图片一并发送。
        """
        if not self._ws:
            return False

        try:
            # 构建消息段
            segments: list[dict] = [{
                "type": "text",
                "data": {"text": message.content or ""},
            }]

            # 如果附带图片，添加图片段
            media_path = getattr(message, "media_path", None) or getattr(message, "media_url", None)
            if media_path:
                segments.append({
                    "type": "image",
                    "data": {"file": media_path},
                })

            params: dict[str, Any] = {
                "message": segments,
            }

            if message.type == MessageType.PRIVATE:
                params["user_id"] = int(message.sender_id)
                action = "send_private_msg"
            elif message.type == MessageType.GROUP and message.group_id:
                params["group_id"] = int(message.group_id)
                action = "send_group_msg"
            else:
                return False

            payload = {"action": action, "params": params}
            await self._ws.send(json.dumps(payload))
            return True

        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return False

    async def listen(self) -> AsyncGenerator[Message, None]:
        """从队列中持续获取消息。"""
        while self._running:
            try:
                message = await asyncio.wait_for(
                    self._message_queue.get(), timeout=1.0
                )
                yield message
            except asyncio.TimeoutError:
                continue

    async def stop(self) -> None:
        """停止并断开连接。"""
        self._running = False
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        logger.info("QQ 机器人已断开")
