"""平台抽象层 — 定义平台无关的 Bot 接口。

所有平台适配器（QQ、Discord、微信等）需继承 BaseBot 并实现其抽象方法。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Callable

from src.models.message import Message, PlatformEvent


class BaseBot(ABC):
    """平台 Bot 抽象基类。

    定义所有平台适配器必须实现的接口。
    """

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self._handlers: dict[str, list[Callable]] = {}

    @abstractmethod
    async def start(self) -> None:
        """启动机器人，连接平台。"""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """停止机器人，断开连接。"""
        ...

    @abstractmethod
    async def send_message(
        self,
        message: Message,
    ) -> bool:
        """发送消息。

        Args:
            message: 要发送的消息对象

        Returns:
            是否发送成功
        """
        ...

    @abstractmethod
    async def listen(self) -> AsyncGenerator[Message, None]:
        """监听消息事件，持续生成消息。

        Yields:
            收到的消息对象
        """
        ...
        yield  # pragma: no cover

    def on_message(self, handler: Callable) -> Callable:
        """注册消息处理函数（装饰器模式）。

        Args:
            handler: 接收 Message 参数的异步函数

        Returns:
            原 handler（保持装饰器语义）
        """
        self._handlers.setdefault("message", []).append(handler)
        return handler

    def on_event(self, event_type: str) -> Callable:
        """注册事件处理函数（装饰器模式）。

        Args:
            event_type: 事件类型

        Returns:
            装饰器
        """
        def decorator(handler: Callable) -> Callable:
            self._handlers.setdefault(f"event:{event_type}", []).append(handler)
            return handler
        return decorator

    async def dispatch_message(self, message: Message) -> None:
        """分发消息给所有注册的处理器。

        Args:
            message: 收到的消息
        """
        for handler in self._handlers.get("message", []):
            await handler(message)

    async def dispatch_event(self, event: PlatformEvent) -> None:
        """分发事件给所有注册的事件处理器。

        Args:
            event: 事件对象
        """
        for handler in self._handlers.get(f"event:{event.type}", []):
            await handler(event)

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """返回平台名称 (qq / discord / wechat)。"""
        ...

    @property
    def is_connected(self) -> bool:
        """是否已连接。"""
        return False
