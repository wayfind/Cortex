#!/usr/bin/env python3
"""
内存使用检查工具

检查系统内存使用率，输出 JSON 格式结果
"""

import json
import sys
from typing import Dict, List, Optional


def get_memory_info() -> Optional[Dict]:
    """读取 /proc/meminfo 获取内存信息"""
    try:
        with open("/proc/meminfo", "r") as f:
            meminfo = {}
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    # 提取数值（单位是 kB）
                    value_str = parts[1].strip().split()[0]
                    meminfo[key] = int(value_str)

            total = meminfo.get("MemTotal", 0)
            available = meminfo.get("MemAvailable", meminfo.get("MemFree", 0))
            buffers = meminfo.get("Buffers", 0)
            cached = meminfo.get("Cached", 0)
            swap_total = meminfo.get("SwapTotal", 0)
            swap_free = meminfo.get("SwapFree", 0)

            used = total - available
            percent = (used / total * 100) if total > 0 else 0

            swap_used = swap_total - swap_free
            swap_percent = (swap_used / swap_total * 100) if swap_total > 0 else 0

            return {
                "total_gb": round(total / (1024**2), 2),
                "used_gb": round(used / (1024**2), 2),
                "available_gb": round(available / (1024**2), 2),
                "buffers_gb": round(buffers / (1024**2), 2),
                "cached_gb": round(cached / (1024**2), 2),
                "percent": round(percent, 2),
                "swap_total_gb": round(swap_total / (1024**2), 2),
                "swap_used_gb": round(swap_used / (1024**2), 2),
                "swap_percent": round(swap_percent, 2),
            }

    except FileNotFoundError:
        return None


def get_top_memory_processes(limit: int = 5) -> List[Dict]:
    """获取内存占用最高的进程"""
    processes = []

    try:
        import subprocess

        # 使用 ps 命令获取进程信息
        result = subprocess.run(
            ["ps", "aux", "--sort=-%mem"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            # 跳过表头
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
                                "vsz_kb": int(parts[4]),
                                "rss_kb": int(parts[5]),
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
    memory_info = get_memory_info()

    if memory_info is None:
        result = {
            "status": "error",
            "message": "Unable to retrieve memory information",
        }
        print(json.dumps(result, indent=2))
        sys.exit(1)

    # 如果内存使用率较高，获取占用内存最多的进程
    top_processes = []
    if memory_info["percent"] > 70:
        top_processes = get_top_memory_processes()

    result = {
        "status": "ok",
        "memory": memory_info,
        "top_processes": top_processes,
    }

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
