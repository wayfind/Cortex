"""
WebSocket 连接管理器

负责管理所有 WebSocket 客户端连接并广播消息
"""

import json
import logging
from datetime import datetime, UTC
from typing import List, Dict, Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        """初始化管理器"""
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """
        接受新的 WebSocket 连接

        Args:
            websocket: WebSocket 连接
        """
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """
        断开 WebSocket 连接

        Args:
            websocket: WebSocket 连接
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket client disconnected. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """
        发送消息到特定客户端

        Args:
            message: 消息内容
            websocket: 目标客户端
        """
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send message to client: {e}")
            self.disconnect(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        """
        广播消息到所有连接的客户端

        Args:
            message: 消息内容
        """
        # 添加时间戳
        if "timestamp" not in message:
            message["timestamp"] = datetime.now(UTC).isoformat()

        logger.debug(f"Broadcasting message to {len(self.active_connections)} clients: {message.get('type')}")

        # 发送到所有客户端
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to broadcast to client: {e}")
                disconnected.append(connection)

        # 移除断开的连接
        for connection in disconnected:
            self.disconnect(connection)

    async def broadcast_inspection_started(self, execution_id: str):
        """广播巡检开始事件"""
        await self.broadcast({
            "type": "inspection_started",
            "execution_id": execution_id,
            "message": "System inspection started"
        })

    async def broadcast_inspection_progress(
        self,
        execution_id: str,
        progress: str,
        details: Dict[str, Any] = None
    ):
        """
        广播巡检进度事件

        Args:
            execution_id: 执行 ID
            progress: 进度描述
            details: 详细信息
        """
        message = {
            "type": "inspection_progress",
            "execution_id": execution_id,
            "progress": progress
        }
        if details:
            message["details"] = details

        await self.broadcast(message)

    async def broadcast_inspection_completed(
        self,
        execution_id: str,
        report: Dict[str, Any]
    ):
        """
        广播巡检完成事件

        Args:
            execution_id: 执行 ID
            report: 巡检报告
        """
        await self.broadcast({
            "type": "inspection_completed",
            "execution_id": execution_id,
            "status": report.get("status", "unknown"),
            "summary": {
                "issues_found": len(report.get("issues", [])),
                "actions_taken": len(report.get("actions_taken", [])),
                "metrics": report.get("metrics", {})
            },
            "message": "System inspection completed"
        })

    async def broadcast_inspection_failed(
        self,
        execution_id: str,
        error_message: str
    ):
        """
        广播巡检失败事件

        Args:
            execution_id: 执行 ID
            error_message: 错误信息
        """
        await self.broadcast({
            "type": "inspection_failed",
            "execution_id": execution_id,
            "error": error_message,
            "message": "System inspection failed"
        })

    def get_connection_count(self) -> int:
        """获取当前连接数"""
        return len(self.active_connections)
