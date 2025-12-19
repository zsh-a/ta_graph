import asyncio
from typing import Any, Callable, Awaitable
from collections import defaultdict
from datetime import datetime

class EventBus:
    """
    轻量级异步事件总线，用于交易逻辑与仪表盘实时通信
    """
    def __init__(self):
        self.subscribers: dict[str, list[Callable[[Any], Awaitable[None]]]] = defaultdict(list)
        self.queue = asyncio.Queue()
        self._running = False
        self._task = None
        self.loop = None

    def subscribe(self, event_type: str, callback: Callable[[Any], Awaitable[None]]):
        """订阅事件"""
        if callback not in self.subscribers[event_type]:
            self.subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable[[Any], Awaitable[None]]):
        """取消订阅"""
        if event_type in self.subscribers:
            if callback in self.subscribers[event_type]:
                self.subscribers[event_type].remove(callback)

    async def emit(self, event_type: str, data: Any):
        """发送事件"""
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        await self.queue.put(event)

    def emit_sync(self, event_type: str, data: Any):
        """同步发送事件 (线程安全)"""
        if self.loop and self.loop.is_running():
            event = {
                "type": event_type,
                "data": data,
                "timestamp": datetime.now().isoformat()
            }
            def _put():
                # 注意：这里我们是在 loop 线程中执行的
                # 直接 put 是异步的，所以我们还是需要 create_task 或者 call_soon
                self.queue.put_nowait(event)
            self.loop.call_soon_threadsafe(_put)

    async def _process_events(self):
        """处理队列中的事件"""
        while self._running:
            try:
                event = await self.queue.get()
                event_type = event["type"]
                
                # 通知所有订阅者（例如 WebSocket 发送器）
                callbacks = set(self.subscribers.get(event_type, []))
                
                # 也通知通配符订阅者
                callbacks.update(self.subscribers.get("*", []))

                tasks = [callback(event) for callback in callbacks]
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                
                self.queue.task_done()
            except Exception as e:
                print(f"Error in EventBus: {e}")
                await asyncio.sleep(0.1)

    def start(self):
        """启动事件处理"""
        if not self._running:
            try:
                self.loop = asyncio.get_running_loop()
            except RuntimeError:
                # 不在 async 上下文中，尝试 get_event_loop
                self.loop = asyncio.get_event_loop()
            
            self._running = True
            self._task = self.loop.create_task(self._process_events())

    async def stop(self):
        """停止事件循环"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

# 全局单例
_bus = EventBus()

def get_event_bus() -> EventBus:
    return _bus
