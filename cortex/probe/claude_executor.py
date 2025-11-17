"""
Claude -p 执行器

负责执行基于 claude -p 的文档驱动巡检
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ExecutionStatus(str, Enum):
    """执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class ExecutionResult(BaseModel):
    """执行结果"""
    execution_id: str
    status: ExecutionStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    exit_code: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    report: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class ClaudeExecutor:
    """
    Claude -p 执行器

    负责异步执行 claude -p 命令进行文档驱动巡检
    """

    def __init__(self, workspace_path: str, timeout: int = 300):
        """
        初始化执行器

        Args:
            workspace_path: probe_workspace 目录路径
            timeout: 超时时间（秒）
        """
        self.workspace_path = Path(workspace_path)
        self.timeout = timeout
        self.current_execution: Optional[ExecutionResult] = None

        # 验证 workspace 存在
        if not self.workspace_path.exists():
            raise ValueError(f"Workspace path does not exist: {workspace_path}")

        logger.info(f"ClaudeExecutor initialized with workspace: {workspace_path}")

    async def execute(self, execution_id: Optional[str] = None) -> ExecutionResult:
        """
        执行一次 claude -p 巡检

        Args:
            execution_id: 执行 ID（可选，自动生成）

        Returns:
            ExecutionResult: 执行结果
        """
        if not execution_id:
            execution_id = str(uuid.uuid4())

        started_at = datetime.now(timezone.utc)

        result = ExecutionResult(
            execution_id=execution_id,
            status=ExecutionStatus.RUNNING,
            started_at=started_at
        )

        self.current_execution = result

        logger.info(f"Starting claude -p execution: {execution_id}")

        try:
            # 构建提示词
            prompt = self._build_prompt()

            # 执行 claude -p
            stdout, stderr, exit_code = await self._run_claude_command(prompt)

            # 计算执行时间
            completed_at = datetime.now(timezone.utc)
            duration = (completed_at - started_at).total_seconds()

            # 更新结果
            result.completed_at = completed_at
            result.duration_seconds = duration
            result.exit_code = exit_code
            result.stdout = stdout
            result.stderr = stderr

            # 检查执行结果
            if exit_code == 0:
                # 读取生成的报告
                report = self._read_report()

                result.status = ExecutionStatus.COMPLETED
                result.report = report

                logger.info(
                    f"Execution {execution_id} completed successfully "
                    f"in {duration:.2f}s"
                )
            else:
                result.status = ExecutionStatus.FAILED
                result.error_message = f"Claude exited with code {exit_code}"

                logger.error(
                    f"Execution {execution_id} failed with exit code {exit_code}"
                )
                logger.error(f"stderr: {stderr}")

        except asyncio.TimeoutError:
            result.status = ExecutionStatus.TIMEOUT
            result.error_message = f"Execution timed out after {self.timeout}s"
            result.completed_at = datetime.now(timezone.utc)

            logger.error(f"Execution {execution_id} timed out")

        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error_message = str(e)
            result.completed_at = datetime.now(timezone.utc)

            logger.error(f"Execution {execution_id} failed: {e}", exc_info=True)

        finally:
            self.current_execution = None

        return result

    def _build_prompt(self) -> str:
        """构建 Claude 提示词"""
        return """Execute a full system inspection as a Cortex Probe Agent.

Follow these steps:

1. Read CLAUDE.md to understand your role and workflow
2. List all inspection requirements in inspections/*.md
3. For each inspection:
   - Run the corresponding tool in tools/
   - Analyze the results
   - Determine if there are any issues (L1/L2/L3)
   - For L1 issues, execute fixes using available tools
   - Collect all results
4. Use tools/report_builder.py to generate the final report
5. Use tools/report_to_monitor.py to upload the report

Important:
- Work systematically through each inspection
- Record all findings and actions
- Generate a complete JSON report at output/report.json
- If any step fails, log the error and continue with other inspections
- At the end, print a summary of the inspection results

Begin the inspection now."""

    async def _run_claude_command(
        self,
        prompt: str
    ) -> tuple[str, str, int]:
        """
        运行 claude -p 命令

        Args:
            prompt: 提示词

        Returns:
            (stdout, stderr, exit_code)
        """
        # 构建命令
        cmd = [
            'claude',
            '-p',
            '--dangerously-skip-permissions',
            prompt
        ]

        logger.debug(f"Running command: {' '.join(cmd[:2])} ...")

        # 创建子进程
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.workspace_path)
        )

        # 等待执行完成（带超时）
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout
            )

            stdout = stdout_bytes.decode('utf-8', errors='replace')
            stderr = stderr_bytes.decode('utf-8', errors='replace')
            exit_code = process.returncode

            return stdout, stderr, exit_code

        except asyncio.TimeoutError:
            # 超时，杀死进程
            try:
                process.kill()
                await process.wait()
            except Exception as e:
                logger.error(f"Failed to kill timed out process: {e}")

            raise

    def _read_report(self) -> Optional[Dict[str, Any]]:
        """
        读取生成的报告文件

        Returns:
            报告内容（JSON）
        """
        report_path = self.workspace_path / "output" / "report.json"

        if not report_path.exists():
            logger.warning(f"Report file not found: {report_path}")
            return None

        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                report = json.load(f)

            logger.debug(f"Report loaded successfully from {report_path}")
            return report

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse report JSON: {e}")
            return None

        except Exception as e:
            logger.error(f"Failed to read report: {e}")
            return None

    def is_running(self) -> bool:
        """检查是否有正在执行的任务"""
        return self.current_execution is not None

    def get_current_status(self) -> Optional[Dict[str, Any]]:
        """获取当前执行状态"""
        if not self.current_execution:
            return None

        return {
            "execution_id": self.current_execution.execution_id,
            "status": self.current_execution.status,
            "started_at": self.current_execution.started_at.isoformat(),
            "duration_seconds": (
                (datetime.now(timezone.utc) - self.current_execution.started_at).total_seconds()
                if self.current_execution.status == ExecutionStatus.RUNNING
                else self.current_execution.duration_seconds
            )
        }
