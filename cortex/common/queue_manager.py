"""
上报数据本地队列管理器

在网络不可用时，将上报数据缓存到本地队列；
网络恢复后自动重新发送。
"""

import asyncio
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from enum import Enum

from loguru import logger


class QueueItemStatus(str, Enum):
    """队列项状态"""

    PENDING = "pending"  # 待发送
    SENDING = "sending"  # 发送中
    SENT = "sent"  # 已发送
    FAILED = "failed"  # 发送失败（超过最大重试次数）


class QueueItem:
    """队列项"""

    def __init__(
        self,
        id: int,
        endpoint: str,
        payload: Dict[str, Any],
        status: QueueItemStatus,
        retry_count: int,
        created_at: datetime,
        updated_at: datetime,
        last_error: Optional[str] = None,
    ):
        self.id = id
        self.endpoint = endpoint
        self.payload = payload
        self.status = QueueItemStatus(status)
        self.retry_count = retry_count
        self.created_at = created_at
        self.updated_at = updated_at
        self.last_error = last_error


class LocalQueueManager:
    """
    本地队列管理器

    使用 SQLite 存储待发送的数据，支持离线缓存和自动重试
    """

    def __init__(
        self,
        db_path: str = "cortex_queue.db",
        max_retry_count: int = 5,
        max_queue_size: int = 1000,
    ):
        """
        初始化队列管理器

        Args:
            db_path: SQLite 数据库文件路径
            max_retry_count: 单个项目最大重试次数
            max_queue_size: 队列最大容量（超过则丢弃最旧的项目）
        """
        self.db_path = Path(db_path)
        self.max_retry_count = max_retry_count
        self.max_queue_size = max_queue_size
        self._init_database()

    def _init_database(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS queue_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    endpoint TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_error TEXT
                )
                """
            )

            # 创建索引
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_status_created
                ON queue_items(status, created_at)
                """
            )

            conn.commit()

    async def enqueue(self, endpoint: str, payload: Dict[str, Any]) -> int:
        """
        将数据加入队列

        Args:
            endpoint: 目标 API 端点
            payload: 要发送的数据

        Returns:
            队列项 ID
        """
        # 检查队列大小，必要时清理
        await self._cleanup_if_full()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO queue_items (endpoint, payload, status)
                VALUES (?, ?, ?)
                """,
                (endpoint, json.dumps(payload), QueueItemStatus.PENDING.value),
            )
            item_id = cursor.lastrowid
            conn.commit()

        logger.info(f"Enqueued item {item_id} for {endpoint}")
        return item_id

    async def get_pending_items(self, limit: int = 100) -> List[QueueItem]:
        """
        获取待发送的队列项

        Args:
            limit: 最多获取数量

        Returns:
            待发送的队列项列表
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM queue_items
                WHERE status = ?
                AND retry_count < ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (QueueItemStatus.PENDING.value, self.max_retry_count, limit),
            )

            items = []
            for row in cursor:
                items.append(
                    QueueItem(
                        id=row["id"],
                        endpoint=row["endpoint"],
                        payload=json.loads(row["payload"]),
                        status=row["status"],
                        retry_count=row["retry_count"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                        updated_at=datetime.fromisoformat(row["updated_at"]),
                        last_error=row["last_error"],
                    )
                )

            return items

    async def mark_as_sending(self, item_id: int):
        """标记项目为发送中"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE queue_items
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (QueueItemStatus.SENDING.value, item_id),
            )
            conn.commit()

    async def mark_as_sent(self, item_id: int):
        """标记项目为已发送"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE queue_items
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (QueueItemStatus.SENT.value, item_id),
            )
            conn.commit()

        logger.success(f"Item {item_id} marked as sent")

    async def mark_as_failed(self, item_id: int, error: str):
        """
        标记项目发送失败（增加重试计数）

        Args:
            item_id: 队列项 ID
            error: 错误信息
        """
        with sqlite3.connect(self.db_path) as conn:
            # 增加重试计数
            conn.execute(
                """
                UPDATE queue_items
                SET
                    retry_count = retry_count + 1,
                    last_error = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (error, item_id),
            )

            # 检查是否超过最大重试次数
            cursor = conn.execute(
                """
                SELECT retry_count FROM queue_items WHERE id = ?
                """,
                (item_id,),
            )
            row = cursor.fetchone()
            if row and row[0] >= self.max_retry_count:
                # 标记为永久失败
                conn.execute(
                    """
                    UPDATE queue_items
                    SET status = ?
                    WHERE id = ?
                    """,
                    (QueueItemStatus.FAILED.value, item_id),
                )
                logger.error(
                    f"Item {item_id} marked as FAILED after {self.max_retry_count} retries"
                )
            else:
                # 重新标记为 pending，等待下次重试
                conn.execute(
                    """
                    UPDATE queue_items
                    SET status = ?
                    WHERE id = ?
                    """,
                    (QueueItemStatus.PENDING.value, item_id),
                )
                logger.warning(
                    f"Item {item_id} retry count: {row[0]}/{self.max_retry_count}"
                )

            conn.commit()

    async def _cleanup_if_full(self):
        """如果队列满了，删除最旧的已发送/失败项目"""
        with sqlite3.connect(self.db_path) as conn:
            # 获取总数
            cursor = conn.execute("SELECT COUNT(*) FROM queue_items")
            total_count = cursor.fetchone()[0]

            if total_count >= self.max_queue_size:
                # 删除最旧的已发送和已失败项目
                to_delete = total_count - self.max_queue_size + 100  # 多删一些，留出余量

                conn.execute(
                    """
                    DELETE FROM queue_items
                    WHERE id IN (
                        SELECT id FROM queue_items
                        WHERE status IN (?, ?)
                        ORDER BY created_at ASC
                        LIMIT ?
                    )
                    """,
                    (
                        QueueItemStatus.SENT.value,
                        QueueItemStatus.FAILED.value,
                        to_delete,
                    ),
                )

                conn.commit()
                logger.info(f"Cleaned up {to_delete} old queue items")

    async def cleanup_old_items(self, days: int = 7):
        """
        清理超过指定天数的已发送和失败项目

        Args:
            days: 保留天数
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                DELETE FROM queue_items
                WHERE status IN (?, ?)
                AND created_at < ?
                """,
                (
                    QueueItemStatus.SENT.value,
                    QueueItemStatus.FAILED.value,
                    cutoff_date.isoformat(),
                ),
            )

            deleted_count = cursor.rowcount
            conn.commit()

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old queue items (>{days} days)")

    async def get_stats(self) -> Dict[str, int]:
        """获取队列统计信息"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT
                    status,
                    COUNT(*) as count
                FROM queue_items
                GROUP BY status
                """
            )

            stats = {
                QueueItemStatus.PENDING.value: 0,
                QueueItemStatus.SENDING.value: 0,
                QueueItemStatus.SENT.value: 0,
                QueueItemStatus.FAILED.value: 0,
            }

            for row in cursor:
                stats[row[0]] = row[1]

            # 添加总数
            stats["total"] = sum(stats.values())

            return stats
