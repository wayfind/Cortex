"""
Probe 调度器 - 使用 APScheduler 实现定时巡检
"""

import asyncio
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from cortex.config.settings import Settings
from cortex.probe.executor import ProbeExecutor


class ProbeScheduler:
    """Probe 调度器 - 负责定时触发巡检"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.scheduler = AsyncIOScheduler()
        self.executor = ProbeExecutor(settings)
        self._running = False

    async def start(self) -> None:
        """启动调度器"""
        if self._running:
            logger.warning("Probe scheduler is already running")
            return

        logger.info(f"Starting probe scheduler with cron: {self.settings.probe.schedule}")

        # 添加定时任务
        self.scheduler.add_job(
            self.run_inspection,
            trigger=CronTrigger.from_crontab(self.settings.probe.schedule),
            id="probe_inspection",
            name="Probe Inspection Job",
            max_instances=1,  # 同时只运行一个实例
            coalesce=True,  # 错过的任务合并执行
        )

        # 启动调度器
        self.scheduler.start()
        self._running = True

        logger.success("Probe scheduler started successfully")

        # 可选：立即执行一次巡检
        await self.run_inspection()

    async def run_inspection(self) -> None:
        """执行巡检任务"""
        try:
            logger.info("=" * 50)
            logger.info("Running scheduled probe inspection")
            logger.info("=" * 50)

            # 执行巡检
            report = await self.executor.execute()

            # 发送上报
            await self.executor.send_report(report)

            logger.info("Probe inspection completed successfully")

        except Exception as e:
            logger.error(f"Error during probe inspection: {e}", exc_info=True)

    async def stop(self) -> None:
        """停止调度器"""
        if not self._running:
            return

        logger.info("Stopping probe scheduler...")
        self.scheduler.shutdown(wait=True)
        await self.executor.cleanup()
        self._running = False
        logger.info("Probe scheduler stopped")

    async def run_once(self) -> None:
        """手动执行一次巡检（不启动调度器）"""
        logger.info("Running one-time probe inspection")
        await self.run_inspection()
        await self.executor.cleanup()

    def is_running(self) -> bool:
        """检查调度器是否运行中"""
        return self._running
