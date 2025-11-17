"""
队列发送器

定期从本地队列中取出数据并发送到目标服务器
"""

import asyncio
from typing import Callable, Awaitable, Optional
import httpx

from loguru import logger

from cortex.common.queue_manager import LocalQueueManager, QueueItem
from cortex.common.retry import retry_async, FAST_RETRY_CONFIG


class QueueSender:
    """
    队列发送器

    定期检查本地队列，并尝试发送待处理的数据
    """

    def __init__(
        self,
        queue_manager: LocalQueueManager,
        send_interval: int = 60,  # 发送间隔（秒）
        batch_size: int = 10,  # 每批发送数量
        timeout: int = 30,  # HTTP 超时时间
    ):
        """
        初始化队列发送器

        Args:
            queue_manager: 队列管理器
            send_interval: 发送检查间隔（秒）
            batch_size: 每批发送的最大数量
            timeout: HTTP 请求超时时间（秒）
        """
        self.queue_manager = queue_manager
        self.send_interval = send_interval
        self.batch_size = batch_size
        self.timeout = timeout
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def _send_one_item(self, item: QueueItem) -> bool:
        """
        发送单个队列项

        Args:
            item: 队列项

        Returns:
            True 如果发送成功
        """
        logger.info(f"Sending queue item {item.id} to {item.endpoint}")

        await self.queue_manager.mark_as_sending(item.id)

        # 定义发送函数（用于重试）
        async def _make_request():
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(item.endpoint, json=item.payload)
                response.raise_for_status()
                return response.json()

        try:
            # 使用快速重试配置
            result = await retry_async(_make_request, config=FAST_RETRY_CONFIG)

            # 标记为已发送
            await self.queue_manager.mark_as_sent(item.id)
            logger.success(f"Successfully sent queue item {item.id}")
            return True

        except Exception as e:
            # 标记为失败（会增加重试计数）
            await self.queue_manager.mark_as_failed(item.id, str(e))
            logger.error(f"Failed to send queue item {item.id}: {e}")
            return False

    async def _process_batch(self):
        """处理一批队列数据"""
        # 获取待发送的项目
        items = await self.queue_manager.get_pending_items(limit=self.batch_size)

        if not items:
            return

        logger.info(f"Processing {len(items)} queue items")

        # 并发发送（限制并发数）
        tasks = [self._send_one_item(item) for item in items]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        success_count = sum(1 for r in results if r is True)
        logger.info(
            f"Batch complete: {success_count}/{len(items)} sent successfully"
        )

    async def _sender_loop(self):
        """发送循环"""
        logger.info(f"Queue sender started (interval: {self.send_interval}s)")

        while self._running:
            try:
                await self._process_batch()
            except Exception as e:
                logger.error(f"Error in sender loop: {e}", exc_info=True)

            # 等待下一次发送
            await asyncio.sleep(self.send_interval)

        logger.info("Queue sender stopped")

    def start(self):
        """启动发送器"""
        if self._running:
            logger.warning("Queue sender already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._sender_loop())
        logger.info("Queue sender task created")

    async def stop(self):
        """停止发送器"""
        if not self._running:
            return

        self._running = False

        if self._task:
            # 等待任务完成
            await self._task
            self._task = None

        logger.info("Queue sender stopped")

    async def flush(self):
        """立即处理所有待发送的数据（阻塞直到完成）"""
        logger.info("Flushing queue...")

        processed = 0
        while True:
            items = await self.queue_manager.get_pending_items(
                limit=self.batch_size
            )
            if not items:
                break

            tasks = [self._send_one_item(item) for item in items]
            await asyncio.gather(*tasks, return_exceptions=True)
            processed += len(items)

        logger.info(f"Flushed {processed} items from queue")
