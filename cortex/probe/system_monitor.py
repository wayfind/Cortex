"""
系统监控工具 - 使用 psutil 收集系统信息
"""

import os
import time
from typing import Dict, Tuple

import psutil

from cortex.common.models import SystemMetrics


class SystemMonitor:
    """系统监控器"""

    def __init__(self) -> None:
        self._boot_time = psutil.boot_time()

    def collect_metrics(self) -> SystemMetrics:
        """收集系统指标"""
        return SystemMetrics(
            cpu_percent=self.get_cpu_percent(),
            memory_percent=self.get_memory_percent(),
            disk_percent=self.get_disk_percent(),
            load_average=self.get_load_average(),
            uptime_seconds=self.get_uptime_seconds(),
            process_count=self.get_process_count(),
            disk_io=self.get_disk_io(),
            network_io=self.get_network_io(),
        )

    @staticmethod
    def get_cpu_percent() -> float:
        """获取 CPU 使用率"""
        return psutil.cpu_percent(interval=1.0)

    @staticmethod
    def get_memory_percent() -> float:
        """获取内存使用率"""
        return psutil.virtual_memory().percent

    @staticmethod
    def get_disk_percent(path: str = "/") -> float:
        """获取磁盘使用率"""
        return psutil.disk_usage(path).percent

    @staticmethod
    def get_load_average() -> Tuple[float, float, float]:
        """获取系统负载"""
        if hasattr(os, "getloadavg"):
            return tuple(os.getloadavg())  # type: ignore
        # Windows 不支持 getloadavg，返回默认值
        return (0.0, 0.0, 0.0)

    def get_uptime_seconds(self) -> int:
        """获取系统运行时间（秒）"""
        return int(time.time() - self._boot_time)

    @staticmethod
    def get_process_count() -> int:
        """获取进程数量"""
        return len(psutil.pids())

    @staticmethod
    def get_disk_io() -> Dict[str, int]:
        """获取磁盘 IO 统计"""
        disk_io = psutil.disk_io_counters()
        if disk_io:
            return {
                "read_bytes": disk_io.read_bytes,
                "write_bytes": disk_io.write_bytes,
                "read_count": disk_io.read_count,
                "write_count": disk_io.write_count,
            }
        return {}

    @staticmethod
    def get_network_io() -> Dict[str, int]:
        """获取网络 IO 统计"""
        net_io = psutil.net_io_counters()
        if net_io:
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv,
            }
        return {}

    @staticmethod
    def check_process_running(process_name: str) -> bool:
        """检查进程是否运行"""
        for proc in psutil.process_iter(["name"]):
            try:
                if process_name.lower() in proc.info["name"].lower():
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return False

    @staticmethod
    def check_port_listening(port: int) -> bool:
        """检查端口是否在监听"""
        for conn in psutil.net_connections(kind="inet"):
            if conn.status == psutil.CONN_LISTEN and conn.laddr.port == port:
                return True
        return False

    def get_critical_processes_status(self, processes: list[str]) -> Dict[str, bool]:
        """批量检查关键进程状态"""
        return {name: self.check_process_running(name) for name in processes}
