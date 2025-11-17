"""
心跳检测服务

定期检查所有 Agent 的心跳状态，将超时的 Agent 标记为 offline。
"""

import asyncio
from datetime import datetime, timedelta, timezone

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.monitor.database import Agent
from cortex.monitor.db_manager import DatabaseManager
from cortex.monitor.dependencies import get_ws_manager


class HeartbeatChecker:
    """心跳检测器"""

    def __init__(self, db_manager: DatabaseManager, timeout_minutes: int = 5, check_interval_seconds: int = 60):
        """
        初始化心跳检测器

        Args:
            db_manager: 数据库管理器
            timeout_minutes: 心跳超时时间（分钟），默认 5 分钟
            check_interval_seconds: 检查间隔（秒），默认 60 秒
        """
        self.db_manager = db_manager
        self.timeout_minutes = timeout_minutes
        self.check_interval_seconds = check_interval_seconds
        self._task = None
        self._running = False

    async def _check_heartbeats(self) -> None:
        """检查所有 Agent 的心跳状态"""
        try:
            async for session in self.db_manager.get_session():
                # 计算超时时间点
                timeout_threshold = datetime.now(timezone.utc) - timedelta(minutes=self.timeout_minutes)

                # 查询所有 online 状态的 Agent
                result = await session.execute(
                    select(Agent).where(Agent.status == "online")
                )
                online_agents = result.scalars().all()

                # 检查每个 online Agent 的心跳
                offline_count = 0
                offline_agents = []
                for agent in online_agents:
                    # 如果 last_heartbeat 为 None 或超时，标记为 offline
                    if agent.last_heartbeat is None or agent.last_heartbeat < timeout_threshold:
                        old_status = agent.status
                        agent.status = "offline"
                        offline_count += 1
                        offline_agents.append((agent, old_status))
                        logger.warning(
                            f"Agent {agent.id} ({agent.name}) marked as offline - "
                            f"last heartbeat: {agent.last_heartbeat.isoformat() if agent.last_heartbeat else 'never'}"
                        )

                if offline_count > 0:
                    await session.commit()
                    logger.info(f"Heartbeat check: {offline_count} agents marked as offline")

                    # 广播 Agent 状态变化事件
                    try:
                        ws_manager = get_ws_manager()
                        for agent, old_status in offline_agents:
                            await ws_manager.broadcast_agent_status_changed(
                                agent_id=agent.id,
                                old_status=old_status,
                                new_status="offline",
                                health_status=agent.health_status or "unknown"
                            )
                    except Exception as e:
                        logger.warning(f"Failed to broadcast agent status changes: {e}")
                else:
                    logger.debug("Heartbeat check: all agents are responsive")

        except Exception as e:
            logger.error(f"Error checking heartbeats: {e}")

    async def _run_loop(self) -> None:
        """后台循环任务"""
        logger.info(
            f"Heartbeat checker started - timeout: {self.timeout_minutes}m, interval: {self.check_interval_seconds}s"
        )

        while self._running:
            try:
                await self._check_heartbeats()
            except Exception as e:
                logger.error(f"Error in heartbeat checker loop: {e}")

            # 等待下一次检查
            await asyncio.sleep(self.check_interval_seconds)

        logger.info("Heartbeat checker stopped")

    def start(self) -> None:
        """启动心跳检测器"""
        if self._running:
            logger.warning("Heartbeat checker is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.success("Heartbeat checker task created")

    async def stop(self) -> None:
        """停止心跳检测器"""
        if not self._running:
            return

        self._running = False
        if self._task:
            await self._task
            logger.info("Heartbeat checker task completed")
