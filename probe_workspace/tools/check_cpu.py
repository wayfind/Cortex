#!/usr/bin/env python3
"""
CPU 使用率检查工具

检查系统 CPU 使用率和负载，输出 JSON 格式结果
"""

import json
import os
import sys
import time
from typing import Dict, List, Optional


def get_cpu_percent(interval: float = 1.0) -> Optional[float]:
    """计算 CPU 使用率百分比"""
    try:
        # 读取两次 /proc/stat 计算使用率
        def read_cpu_stats():
            with open("/proc/stat", "r") as f:
                line = f.readline()
                # cpu  user nice system idle iowait irq softirq steal guest guest_nice
                parts = line.split()
                if parts[0] == "cpu":
                    return [int(x) for x in parts[1:]]
            return None

        stats1 = read_cpu_stats()
        if stats1 is None:
            return None

        time.sleep(interval)

        stats2 = read_cpu_stats()
        if stats2 is None:
            return None

        # 计算差值
        deltas = [stats2[i] - stats1[i] for i in range(len(stats1))]

        # total = user + nice + system + idle + iowait + irq + softirq + steal
        total = sum(deltas)
        if total == 0:
            return 0.0

        # idle time is at index 3
        idle = deltas[3]
        used = total - idle

        percent = (used / total) * 100
        return round(percent, 2)

    except (FileNotFoundError, IndexError, ValueError):
        return None


def get_load_average() -> Optional[Dict]:
    """获取系统负载"""
    try:
        load1, load5, load15 = os.getloadavg()
        return {
            "1min": round(load1, 2),
            "5min": round(load5, 2),
            "15min": round(load15, 2),
        }
    except (OSError, AttributeError):
        return None


def get_cpu_count() -> int:
    """获取 CPU 核心数"""
    try:
        return os.cpu_count() or 1
    except Exception:
        return 1


def get_cpu_info() -> Optional[Dict]:
    """读取 CPU 信息"""
    try:
        with open("/proc/cpuinfo", "r") as f:
            model_name = None
            cpu_mhz = None
            cores = 0

            for line in f:
                if line.startswith("model name"):
                    model_name = line.split(":", 1)[1].strip()
                elif line.startswith("cpu MHz"):
                    cpu_mhz = float(line.split(":", 1)[1].strip())
                elif line.startswith("processor"):
                    cores += 1

            return {
                "model": model_name or "Unknown",
                "cores": cores if cores > 0 else get_cpu_count(),
                "mhz": round(cpu_mhz, 2) if cpu_mhz else None,
            }

    except FileNotFoundError:
        return {"cores": get_cpu_count()}


def get_top_cpu_processes(limit: int = 5) -> List[Dict]:
    """获取 CPU 占用最高的进程"""
    processes = []

    try:
        import subprocess

        result = subprocess.run(
            ["ps", "aux", "--sort=-%cpu"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            for line in lines[1 : limit + 1]:
                parts = line.split(None, 10)
                if len(parts) >= 11:
                    try:
                        processes.append(
                            {
                                "user": parts[0],
                                "pid": int(parts[1]),
                                "cpu_percent": float(parts[2]),
                                "mem_percent": float(parts[3]),
                                "command": parts[10],
                            }
                        )
                    except ValueError:
                        continue

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        pass

    return processes


def main():
    """主函数"""
    cpu_percent = get_cpu_percent(interval=1.0)
    load_avg = get_load_average()
    cpu_info = get_cpu_info()

    if cpu_percent is None:
        result = {
            "status": "error",
            "message": "Unable to retrieve CPU usage information",
        }
        print(json.dumps(result, indent=2))
        sys.exit(1)

    # 如果 CPU 使用率或负载较高，获取占用 CPU 最多的进程
    top_processes = []
    if cpu_percent > 70 or (load_avg and load_avg["1min"] > cpu_info.get("cores", 1) * 0.7):
        top_processes = get_top_cpu_processes()

    result = {
        "status": "ok",
        "cpu_percent": cpu_percent,
        "load_average": load_avg,
        "cpu_info": cpu_info,
        "top_processes": top_processes,
    }

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
