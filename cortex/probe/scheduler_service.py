"""
Probe 调度服务

负责：
- 使用 APScheduler 周期性触发 claude -p 巡检
- 管理执行历史
- 协调 ClaudeExecutor 和 WebSocketManager
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from cortex.config import Settings
from cortex.probe.claude_executor import ClaudeExecutor, ExecutionResult, ExecutionStatus
from cortex.probe.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)


class ProbeSchedulerService:
    """
    Probe 调度服务

    管理定时巡检任务的执行和历史记录
    """

    def __init__(self, settings: Settings, ws_manager: WebSocketManager):
        """
        初始化调度服务

        Args:
            settings: 配置对象
            ws_manager: WebSocket 管理器
        """
        self.settings = settings
        self.ws_manager = ws_manager

        # 初始化 APScheduler
        self.scheduler = AsyncIOScheduler()

        # 初始化 Claude 执行器
        workspace_path = settings.probe.workspace or str(
            Path(__file__).parent.parent.parent / "probe_workspace"
        )
        timeout = settings.probe.timeout_seconds or 300

        self.executor = ClaudeExecutor(
            workspace_path=workspace_path,
            timeout=timeout
        )

        # 执行历史（内存存储，可以后续改为数据库）
        self.execution_history: List[ExecutionResult] = []
        self.max_history = 100  # 最多保留 100 条历史

        # 调度任务 ID
        self.schedule_job_id = "probe_inspection"

        # 调度状态
        self._paused = False
        self._running = False

        logger.info("ProbeSchedulerService initialized")

    async def start(self):
        """启动调度服务"""
        logger.info("Starting ProbeSchedulerService...")

        # 配置定时任务
        schedule_cron = self.settings.probe.schedule
        if schedule_cron:
            try:
                # 使用 cron 表达式
                trigger = CronTrigger.from_crontab(schedule_cron)
                self.scheduler.add_job(
                    self._scheduled_inspection,
                    trigger=trigger,
                    id=self.schedule_job_id,
                    name="Periodic Inspection",
                    replace_existing=True
                )
                logger.info(f"Scheduled inspection with cron: {schedule_cron}")

            except Exception as e:
                logger.error(f"Failed to parse cron expression '{schedule_cron}': {e}")
                raise

        # 启动调度器
        self.scheduler.start()
        self._running = True

        logger.info("ProbeSchedulerService started successfully")

    async def stop(self):
        """停止调度服务"""
        logger.info("Stopping ProbeSchedulerService...")

        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

        self._running = False

        logger.info("ProbeSchedulerService stopped")

    async def _scheduled_inspection(self):
        """定时触发的巡检任务"""
        logger.info("Scheduled inspection triggered")

        try:
            await self.execute_once(force=False)
        except RuntimeError as e:
            logger.warning(f"Scheduled inspection skipped: {e}")
        except Exception as e:
            logger.error(f"Scheduled inspection failed: {e}", exc_info=True)

    async def execute_once(self, force: bool = False) -> str:
        """
        执行一次巡检

        Args:
            force: 是否强制执行（即使已有任务在运行）

        Returns:
            execution_id: 执行 ID

        Raises:
            RuntimeError: 如果已有任务在运行且 force=False
        """
        # 检查是否已有任务在运行
        if self.executor.is_running() and not force:
            raise RuntimeError("Inspection already running")

        # 生成执行 ID
        import uuid
        execution_id = str(uuid.uuid4())

        logger.info(f"Starting inspection execution: {execution_id}")

        # 广播开始事件
        await self.ws_manager.broadcast_inspection_started(execution_id)

        # 启动异步执行任务（不阻塞）
        asyncio.create_task(self._execute_and_record(execution_id))

        return execution_id

    async def _execute_and_record(self, execution_id: str):
        """
        执行巡检并记录结果

        Args:
            execution_id: 执行 ID
        """
        try:
            # 执行 claude -p
            result = await self.executor.execute(execution_id)

            # 记录历史
            self._add_to_history(result)

            # 广播结果
            if result.status == ExecutionStatus.COMPLETED:
                if result.report:
                    await self.ws_manager.broadcast_inspection_completed(
                        execution_id,
                        result.report
                    )
                else:
                    await self.ws_manager.broadcast_inspection_failed(
                        execution_id,
                        "Report not generated"
                    )
            else:
                await self.ws_manager.broadcast_inspection_failed(
                    execution_id,
                    result.error_message or f"Execution failed with status: {result.status}"
                )

            logger.info(f"Inspection {execution_id} finished with status: {result.status}")

        except Exception as e:
            logger.error(f"Inspection {execution_id} failed with exception: {e}", exc_info=True)

            # 广播失败事件
            await self.ws_manager.broadcast_inspection_failed(
                execution_id,
                str(e)
            )

    def _add_to_history(self, result: ExecutionResult):
        """
        添加执行结果到历史记录

        Args:
            result: 执行结果
        """
        self.execution_history.append(result)

        # 限制历史记录数量
        if len(self.execution_history) > self.max_history:
            self.execution_history = self.execution_history[-self.max_history:]

    def get_status(self) -> Dict[str, Any]:
        """
        获取调度服务状态

        Returns:
            状态信息
        """
        # 获取下次执行时间
        next_run_time = None
        if self.scheduler.running:
            job = self.scheduler.get_job(self.schedule_job_id)
            if job and job.next_run_time:
                next_run_time = job.next_run_time.isoformat()

        # 获取上次执行信息
        last_inspection = None
        if self.execution_history:
            last_result = self.execution_history[-1]
            last_inspection = {
                "execution_id": last_result.execution_id,
                "status": last_result.status,
                "started_at": last_result.started_at.isoformat(),
                "completed_at": last_result.completed_at.isoformat() if last_result.completed_at else None,
                "duration_seconds": last_result.duration_seconds
            }

        return {
            "scheduler_status": "running" if self._running else "stopped",
            "paused": self._paused,
            "next_inspection": next_run_time,
            "last_inspection": last_inspection,
            "current_execution": self.executor.get_current_status(),
            "total_executions": len(self.execution_history)
        }

    def get_schedule_info(self) -> Dict[str, Any]:
        """
        获取调度任务信息

        Returns:
            调度任务详情
        """
        jobs = []

        if self.scheduler.running:
            for job in self.scheduler.get_jobs():
                jobs.append({
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                    "trigger": str(job.trigger)
                })

        return {
            "jobs": jobs,
            "scheduler_running": self.scheduler.running,
            "paused": self._paused
        }

    def pause_schedule(self):
        """暂停定时巡检"""
        if self.scheduler.running:
            job = self.scheduler.get_job(self.schedule_job_id)
            if job:
                job.pause()
                self._paused = True
                logger.info("Scheduled inspections paused")

    def resume_schedule(self):
        """恢复定时巡检"""
        if self.scheduler.running:
            job = self.scheduler.get_job(self.schedule_job_id)
            if job:
                job.resume()
                self._paused = False
                logger.info("Scheduled inspections resumed")

    def get_recent_reports(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取最近的报告列表

        Args:
            limit: 返回数量

        Returns:
            报告列表
        """
        recent = self.execution_history[-limit:]

        return [
            {
                "execution_id": r.execution_id,
                "status": r.status,
                "started_at": r.started_at.isoformat(),
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "duration_seconds": r.duration_seconds,
                "has_report": r.report is not None
            }
            for r in reversed(recent)  # 最新的在前
        ]

    def get_report(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定的报告

        Args:
            execution_id: 执行 ID

        Returns:
            报告详情
        """
        for result in reversed(self.execution_history):
            if result.execution_id == execution_id:
                return {
                    "execution_id": result.execution_id,
                    "status": result.status,
                    "started_at": result.started_at.isoformat(),
                    "completed_at": result.completed_at.isoformat() if result.completed_at else None,
                    "duration_seconds": result.duration_seconds,
                    "exit_code": result.exit_code,
                    "error_message": result.error_message,
                    "report": result.report
                }

        return None

    def is_running(self) -> bool:
        """检查调度服务是否运行中"""
        return self._running
