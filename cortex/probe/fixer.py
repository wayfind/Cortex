"""
L1 自动修复器 - 执行安全的自动修复操作
"""

import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from loguru import logger

from cortex.common.models import ActionReport, ActionResult, IssueReport


class FixResult:
    """修复结果"""

    def __init__(
        self, success: bool, action: str = "", details: str = "", reason: str = ""
    ) -> None:
        self.success = success
        self.action = action
        self.details = details
        self.reason = reason


class L1AutoFixer:
    """L1 问题自动修复器"""

    def __init__(self) -> None:
        self.fixers = {
            "disk_space_low": self.fix_disk_space_low,
            "temp_files_cleanup": self.fix_temp_files_cleanup,
            "log_rotation_needed": self.fix_log_rotation,
            "cache_cleanup": self.fix_cache_cleanup,
        }

    async def fix(self, issue: IssueReport) -> Optional[ActionReport]:
        """
        执行自动修复

        Args:
            issue: 问题报告

        Returns:
            修复操作报告，如果无法修复则返回 None
        """
        fixer_method = self.fixers.get(issue.type)

        if not fixer_method:
            logger.warning(f"No fixer available for issue type: {issue.type}")
            return None

        try:
            # 执行修复
            logger.info(f"Attempting to fix {issue.type}: {issue.description}")
            result = await fixer_method(issue)

            if not result.success:
                logger.warning(f"Fix failed for {issue.type}: {result.reason}")
                return ActionReport(
                    level="L1",
                    action=result.action or issue.type,
                    result=ActionResult.FAILED,
                    details=result.reason,
                    timestamp=datetime.utcnow(),
                )

            # 修复成功
            logger.success(f"Fix succeeded for {issue.type}: {result.details}")
            return ActionReport(
                level="L1",
                action=result.action,
                result=ActionResult.SUCCESS,
                details=result.details,
                timestamp=datetime.utcnow(),
            )

        except Exception as e:
            logger.error(f"Exception during fix for {issue.type}: {e}")
            return ActionReport(
                level="L1",
                action=issue.type,
                result=ActionResult.FAILED,
                details=f"Exception: {str(e)}",
                timestamp=datetime.utcnow(),
            )

    async def fix_disk_space_low(self, issue: IssueReport) -> FixResult:
        """
        修复磁盘空间不足问题

        策略：
        1. 清理 /tmp 目录中 7 天前的文件
        2. 清理旧日志文件（30 天前的 .gz 文件）
        """
        freed_space = 0

        # 清理 /tmp
        try:
            before = shutil.disk_usage("/tmp").used
            self._cleanup_directory("/tmp", days=7)
            after = shutil.disk_usage("/tmp").used
            freed_space += (before - after) / (1024**3)  # 转换为 GB
        except Exception as e:
            logger.warning(f"Failed to cleanup /tmp: {e}")

        # 清理旧日志
        try:
            before = shutil.disk_usage("/var/log").used if Path("/var/log").exists() else 0
            self._cleanup_old_logs("/var/log", days=30)
            after = shutil.disk_usage("/var/log").used if Path("/var/log").exists() else 0
            freed_space += (before - after) / (1024**3)
        except Exception as e:
            logger.warning(f"Failed to cleanup /var/log: {e}")

        if freed_space > 0:
            return FixResult(
                success=True,
                action="cleaned_disk_space",
                details=f"Cleaned /tmp and old logs, freed {freed_space:.2f} GB",
            )
        else:
            return FixResult(
                success=False,
                action="cleaned_disk_space",
                reason="No space could be freed",
            )

    async def fix_temp_files_cleanup(self, issue: IssueReport) -> FixResult:
        """清理临时文件"""
        try:
            before = shutil.disk_usage("/tmp").used
            self._cleanup_directory("/tmp", days=3)
            after = shutil.disk_usage("/tmp").used
            freed = (before - after) / (1024**3)

            return FixResult(
                success=True,
                action="cleaned_temp_files",
                details=f"Cleaned /tmp, freed {freed:.2f} GB",
            )
        except Exception as e:
            return FixResult(success=False, action="cleaned_temp_files", reason=str(e))

    async def fix_log_rotation(self, issue: IssueReport) -> FixResult:
        """执行日志轮转"""
        try:
            # 调用 logrotate（如果可用）
            result = subprocess.run(
                ["logrotate", "-f", "/etc/logrotate.conf"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                return FixResult(
                    success=True,
                    action="log_rotation",
                    details="Logrotate executed successfully",
                )
            else:
                return FixResult(
                    success=False,
                    action="log_rotation",
                    reason=f"Logrotate failed: {result.stderr}",
                )
        except FileNotFoundError:
            return FixResult(
                success=False, action="log_rotation", reason="logrotate command not found"
            )
        except Exception as e:
            return FixResult(success=False, action="log_rotation", reason=str(e))

    async def fix_cache_cleanup(self, issue: IssueReport) -> FixResult:
        """清理缓存"""
        freed = 0

        # 清理 apt cache（如果是 Debian/Ubuntu）
        if Path("/var/cache/apt").exists():
            try:
                before = shutil.disk_usage("/var/cache/apt").used
                subprocess.run(["apt-get", "clean"], check=True, timeout=60)
                after = shutil.disk_usage("/var/cache/apt").used
                freed += (before - after) / (1024**3)
            except Exception as e:
                logger.warning(f"Failed to clean apt cache: {e}")

        # 清理 yum cache（如果是 RHEL/CentOS）
        if Path("/var/cache/yum").exists():
            try:
                subprocess.run(["yum", "clean", "all"], check=True, timeout=60)
            except Exception as e:
                logger.warning(f"Failed to clean yum cache: {e}")

        if freed > 0:
            return FixResult(
                success=True,
                action="cache_cleanup",
                details=f"Cleaned package cache, freed {freed:.2f} GB",
            )
        else:
            return FixResult(
                success=True,
                action="cache_cleanup",
                details="Cache cleanup completed (no significant space freed)",
            )

    def _cleanup_directory(self, directory: str, days: int) -> None:
        """清理目录中旧文件"""
        cutoff_time = datetime.now() - timedelta(days=days)
        cutoff_timestamp = cutoff_time.timestamp()

        dir_path = Path(directory)
        if not dir_path.exists():
            return

        for item in dir_path.rglob("*"):
            try:
                if item.is_file() and item.stat().st_atime < cutoff_timestamp:
                    item.unlink()
            except (PermissionError, FileNotFoundError):
                pass

    def _cleanup_old_logs(self, log_dir: str, days: int) -> None:
        """清理旧日志文件"""
        cutoff_time = datetime.now() - timedelta(days=days)
        cutoff_timestamp = cutoff_time.timestamp()

        log_path = Path(log_dir)
        if not log_path.exists():
            return

        # 删除旧的压缩日志
        for log_file in log_path.rglob("*.gz"):
            try:
                if log_file.stat().st_mtime < cutoff_timestamp:
                    log_file.unlink()
            except (PermissionError, FileNotFoundError):
                pass
