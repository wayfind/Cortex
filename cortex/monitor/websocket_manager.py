"""
WebSocket 连接管理器

负责管理所有 WebSocket 客户端连接并广播消息
"""

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

    async def broadcast_report_received(
        self,
        agent_id: str,
        report_id: int,
        summary: Dict[str, Any]
    ):
        """
        广播报告接收事件

        Args:
            agent_id: Agent ID
            report_id: 报告 ID
            summary: 报告摘要
        """
        await self.broadcast({
            "type": "report_received",
            "agent_id": agent_id,
            "report_id": report_id,
            "summary": summary,
            "message": f"New report received from {agent_id}"
        })

    async def broadcast_alert_triggered(
        self,
        alert_id: int,
        agent_id: str,
        level: str,
        alert_type: str,
        description: str
    ):
        """
        广播告警触发事件

        Args:
            alert_id: 告警 ID
            agent_id: Agent ID
            level: 告警级别 (L1/L2/L3)
            alert_type: 告警类型
            description: 告警描述
        """
        await self.broadcast({
            "type": "alert_triggered",
            "alert_id": alert_id,
            "agent_id": agent_id,
            "level": level,
            "alert_type": alert_type,
            "description": description,
            "message": f"New {level} alert from {agent_id}: {alert_type}"
        })

    async def broadcast_decision_made(
        self,
        decision_id: int,
        agent_id: str,
        status: str,
        reason: str
    ):
        """
        广播决策完成事件

        Args:
            decision_id: 决策 ID
            agent_id: Agent ID
            status: 决策状态 (approved/rejected)
            reason: 决策原因
        """
        await self.broadcast({
            "type": "decision_made",
            "decision_id": decision_id,
            "agent_id": agent_id,
            "status": status,
            "reason": reason,
            "message": f"Decision {status} for {agent_id}"
        })

    async def broadcast_agent_status_changed(
        self,
        agent_id: str,
        old_status: str,
        new_status: str,
        health_status: str
    ):
        """
        广播 Agent 状态变化事件

        Args:
            agent_id: Agent ID
            old_status: 旧状态
            new_status: 新状态
            health_status: 健康状态
        """
        await self.broadcast({
            "type": "agent_status_changed",
            "agent_id": agent_id,
            "old_status": old_status,
            "new_status": new_status,
            "health_status": health_status,
            "message": f"Agent {agent_id} status changed: {old_status} -> {new_status}"
        })

    def get_connection_count(self) -> int:
        """获取当前连接数"""
        return len(self.active_connections)
