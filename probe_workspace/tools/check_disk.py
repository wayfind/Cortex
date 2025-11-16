#!/usr/bin/env python3
"""
磁盘空间检查工具

检查所有挂载点的磁盘使用率，输出 JSON 格式结果
"""

import json
import shutil
import sys
from pathlib import Path
from typing import Dict, List


def get_disk_usage() -> List[Dict]:
    """获取所有挂载点的磁盘使用情况"""
    partitions = []

    # 读取 /proc/mounts 获取所有挂载点
    try:
        with open("/proc/mounts", "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 2:
                    continue

                device = parts[0]
                mount_point = parts[1]
                fs_type = parts[2]

                # 跳过虚拟文件系统
                if fs_type in ["proc", "sysfs", "devtmpfs", "tmpfs", "cgroup", "cgroup2", "devpts"]:
                    continue

                # 跳过非标准挂载点（除了常见的用户挂载点）
                if not (
                    mount_point.startswith("/")
                    and not mount_point.startswith("/proc")
                    and not mount_point.startswith("/sys")
                    and not mount_point.startswith("/dev")
                    and not mount_point.startswith("/run")
                ):
                    continue

                try:
                    usage = shutil.disk_usage(mount_point)
                    percent = (usage.used / usage.total) * 100

                    partitions.append(
                        {
                            "device": device,
                            "mount_point": mount_point,
                            "filesystem": fs_type,
                            "total_gb": round(usage.total / (1024**3), 2),
                            "used_gb": round(usage.used / (1024**3), 2),
                            "free_gb": round(usage.free / (1024**3), 2),
                            "percent": round(percent, 2),
                        }
                    )
                except (PermissionError, OSError):
                    # 跳过无法访问的挂载点
                    continue

    except FileNotFoundError:
        # 非 Linux 系统，尝试使用根目录
        try:
            usage = shutil.disk_usage("/")
            percent = (usage.used / usage.total) * 100
            partitions.append(
                {
                    "device": "unknown",
                    "mount_point": "/",
                    "filesystem": "unknown",
                    "total_gb": round(usage.total / (1024**3), 2),
                    "used_gb": round(usage.used / (1024**3), 2),
                    "free_gb": round(usage.free / (1024**3), 2),
                    "percent": round(percent, 2),
                }
            )
        except OSError:
            pass

    return partitions


def find_large_directories(path: str = "/", min_size_gb: float = 1.0) -> List[Dict]:
    """查找大目录（用于问题分析）"""
    large_dirs = []

    # 只检查常见的可能占用大量空间的目录
    check_paths = ["/var/log", "/tmp", "/var/tmp", "/var/cache"]

    for check_path in check_paths:
        if not Path(check_path).exists():
            continue

        try:
            # 使用 du 命令获取目录大小
            import subprocess

            result = subprocess.run(
                ["du", "-sb", check_path],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                size_bytes = int(result.stdout.split()[0])
                size_gb = size_bytes / (1024**3)

                if size_gb >= min_size_gb:
                    large_dirs.append(
                        {
                            "path": check_path,
                            "size_gb": round(size_gb, 2),
                        }
                    )
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, ValueError, PermissionError):
            continue

    return sorted(large_dirs, key=lambda x: x["size_gb"], reverse=True)


def main():
    """主函数"""
    partitions = get_disk_usage()

    if not partitions:
        result = {
            "status": "error",
            "message": "Unable to retrieve disk usage information",
        }
        print(json.dumps(result, indent=2))
        sys.exit(1)

    # 找出使用率最高的分区
    max_usage = max(p["percent"] for p in partitions)

    # 如果使用率较高，收集大目录信息
    large_dirs = []
    if max_usage > 70:
        large_dirs = find_large_directories()

    result = {
        "status": "ok",
        "max_usage_percent": max_usage,
        "partitions": partitions,
        "large_directories": large_dirs,
    }

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
