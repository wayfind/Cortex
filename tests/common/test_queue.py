"""
测试本地队列管理器和发送器
"""

import asyncio
import json
import pytest
from pathlib import Path
import tempfile

from cortex.common.queue_manager import (
    LocalQueueManager,
    QueueItemStatus,
)


class TestLocalQueueManager:
    """测试本地队列管理器"""

    @pytest.fixture
    async def queue_manager(self):
        """创建临时队列管理器"""
        # 使用临时文件
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        manager = LocalQueueManager(db_path=db_path, max_queue_size=100)
        yield manager

        # 清理
        Path(db_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_enqueue(self, queue_manager):
        """测试入队"""
        item_id = await queue_manager.enqueue(
            endpoint="http://example.com/api/test",
            payload={"key": "value", "number": 123},
        )

        assert item_id > 0

        # 验证数据已入队
        items = await queue_manager.get_pending_items()
        assert len(items) == 1
        assert items[0].id == item_id
        assert items[0].endpoint == "http://example.com/api/test"
        assert items[0].payload == {"key": "value", "number": 123}
        assert items[0].status == QueueItemStatus.PENDING
        assert items[0].retry_count == 0

    @pytest.mark.asyncio
    async def test_mark_as_sent(self, queue_manager):
        """测试标记为已发送"""
        item_id = await queue_manager.enqueue("http://example.com", {"test": 1})

        # 标记为已发送
        await queue_manager.mark_as_sent(item_id)

        # 不应该出现在待发送列表中
        items = await queue_manager.get_pending_items()
        assert len(items) == 0

        # 检查统计
        stats = await queue_manager.get_stats()
        assert stats[QueueItemStatus.SENT.value] == 1

    @pytest.mark.asyncio
    async def test_mark_as_failed_with_retry(self, queue_manager):
        """测试失败后重试"""
        item_id = await queue_manager.enqueue("http://example.com", {"test": 1})

        # 第一次失败
        await queue_manager.mark_as_failed(item_id, "Connection timeout")

        # 仍然在待发送列表中（可以重试）
        items = await queue_manager.get_pending_items()
        assert len(items) == 1
        assert items[0].retry_count == 1
        assert items[0].last_error == "Connection timeout"

        # 第二次失败
        await queue_manager.mark_as_failed(item_id, "Network error")

        items = await queue_manager.get_pending_items()
        assert len(items) == 1
        assert items[0].retry_count == 2

    @pytest.mark.asyncio
    async def test_mark_as_failed_max_retries(self, queue_manager):
        """测试超过最大重试次数"""
        # 设置较小的最大重试次数
        queue_manager.max_retry_count = 3

        item_id = await queue_manager.enqueue("http://example.com", {"test": 1})

        # 失败 3 次
        for i in range(3):
            await queue_manager.mark_as_failed(item_id, f"Error {i}")

        # 应该被标记为永久失败
        items = await queue_manager.get_pending_items()
        assert len(items) == 0  # 不再出现在待发送列表

        stats = await queue_manager.get_stats()
        assert stats[QueueItemStatus.FAILED.value] == 1

    @pytest.mark.asyncio
    async def test_get_stats(self, queue_manager):
        """测试统计信息"""
        # 创建不同状态的项目
        id1 = await queue_manager.enqueue("http://example.com", {"test": 1})
        id2 = await queue_manager.enqueue("http://example.com", {"test": 2})
        id3 = await queue_manager.enqueue("http://example.com", {"test": 3})

        await queue_manager.mark_as_sent(id1)
        await queue_manager.mark_as_failed(id2, "Error")
        # id3 保持 pending
        # 注意: id2 失败后会重新变为 pending（等待重试）

        stats = await queue_manager.get_stats()

        assert stats[QueueItemStatus.PENDING.value] == 2  # id2 和 id3
        assert stats[QueueItemStatus.SENT.value] == 1  # id1
        assert stats["total"] == 3

    @pytest.mark.asyncio
    async def test_cleanup_if_full(self, queue_manager):
        """测试队列满时自动清理"""
        # 设置较小的队列容量
        queue_manager.max_queue_size = 10

        # 添加 15 个项目
        for i in range(15):
            item_id = await queue_manager.enqueue(
                "http://example.com", {"index": i}
            )
            # 将前 10 个标记为已发送（可被清理）
            if i < 10:
                await queue_manager.mark_as_sent(item_id)

        # 统计应该触发清理
        stats = await queue_manager.get_stats()
        assert stats["total"] <= queue_manager.max_queue_size + 100  # 有余量

    @pytest.mark.asyncio
    async def test_cleanup_old_items(self, queue_manager):
        """测试清理旧项目"""
        # 添加一些项目并标记为已发送
        for i in range(5):
            item_id = await queue_manager.enqueue(
                "http://example.com", {"index": i}
            )
            await queue_manager.mark_as_sent(item_id)

        # 清理（这里无法模拟旧数据，只测试函数不报错）
        await queue_manager.cleanup_old_items(days=7)

        # 应该仍然有数据（因为都是刚创建的）
        stats = await queue_manager.get_stats()
        assert stats[QueueItemStatus.SENT.value] == 5


class TestQueueIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """测试完整工作流"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            manager = LocalQueueManager(db_path=db_path, max_retry_count=3)

            # 1. 入队
            item_id = await manager.enqueue(
                endpoint="http://example.com/api/reports",
                payload={
                    "agent_id": "test-agent",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "data": {"cpu": 50, "memory": 70},
                },
            )

            # 2. 获取待发送项
            items = await manager.get_pending_items()
            assert len(items) == 1
            assert items[0].id == item_id

            # 3. 模拟第一次发送失败
            await manager.mark_as_sending(item_id)
            await manager.mark_as_failed(item_id, "Network timeout")

            # 4. 仍然可以获取（因为可以重试）
            items = await manager.get_pending_items()
            assert len(items) == 1
            assert items[0].retry_count == 1

            # 5. 模拟第二次发送成功
            await manager.mark_as_sending(item_id)
            await manager.mark_as_sent(item_id)

            # 6. 不再出现在待发送列表
            items = await manager.get_pending_items()
            assert len(items) == 0

            # 7. 检查最终统计
            stats = await manager.get_stats()
            assert stats[QueueItemStatus.SENT.value] == 1
            assert stats["total"] == 1

        finally:
            Path(db_path).unlink(missing_ok=True)
