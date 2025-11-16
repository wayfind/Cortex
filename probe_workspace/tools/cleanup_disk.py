#!/usr/bin/env python3
"""
磁盘清理工具

执行 L1 级安全的磁盘空间清理操作
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple


def get_disk_usage(path: str = "/") -> Tuple[float, float, float]:
    """
    获取磁盘使用情况

    Returns:
        (total_gb, used_gb, free_gb)
    """
    usage = shutil.disk_usage(path)
    return (
        usage.total / (1024**3),
        usage.used / (1024**3),
        usage.free / (1024**3),
    )


def cleanup_tmp_directory(dry_run: bool = False, days: int = 7) -> Dict:
    """
    清理 /tmp 目录中的旧文件

    Args:
        dry_run: 仅模拟，不实际删除
        days: 清理多少天之前的文件

    Returns:
        清理结果
    """
    result = {
        "path": "/tmp",
        "files_removed": 0,
        "space_freed_mb": 0,
        "errors": []
    }

    tmp_path = Path("/tmp")
    if not tmp_path.exists():
        return result

    try:
        # 使用 find 命令查找旧文件
        cmd = [
            "find", str(tmp_path),
            "-type", "f",
            "-atime", f"+{days}",
            "-print0"
        ]

        if not dry_run:
            cmd.extend(["-delete"])

        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )

        if process.returncode == 0:
            # 计算删除的文件数（通过 null 分隔符）
            if process.stdout:
                files = [f for f in process.stdout.split('\0') if f]
                result["files_removed"] = len(files)

                # 估算释放的空间（实际中已删除，这里只能估算）
                # 在 dry-run 模式下可以获取文件大小
                if dry_run:
                    total_size = 0
                    for file_path in files:
                        try:
                            total_size += os.path.getsize(file_path)
                        except (OSError, FileNotFoundError):
                            continue
                    result["space_freed_mb"] = round(total_size / (1024**2), 2)

        else:
            result["errors"].append(f"find command failed: {process.stderr}")

    except subprocess.TimeoutExpired:
        result["errors"].append("Cleanup timeout after 60s")
    except Exception as e:
        result["errors"].append(f"Error: {str(e)}")

    return result


def cleanup_old_logs(dry_run: bool = False, days: int = 30) -> Dict:
    """
    清理旧的压缩日志文件

    Args:
        dry_run: 仅模拟，不实际删除
        days: 清理多少天之前的文件

    Returns:
        清理结果
    """
    result = {
        "path": "/var/log",
        "files_removed": 0,
        "space_freed_mb": 0,
        "errors": []
    }

    log_path = Path("/var/log")
    if not log_path.exists():
        return result

    try:
        # 查找旧的 .gz 日志文件
        cmd = [
            "find", str(log_path),
            "-type", "f",
            "-name", "*.gz",
            "-mtime", f"+{days}",
            "-print0"
        ]

        if not dry_run:
            cmd.extend(["-delete"])

        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )

        if process.returncode == 0:
            if process.stdout:
                files = [f for f in process.stdout.split('\0') if f]
                result["files_removed"] = len(files)

                if dry_run:
                    total_size = 0
                    for file_path in files:
                        try:
                            total_size += os.path.getsize(file_path)
                        except (OSError, FileNotFoundError):
                            continue
                    result["space_freed_mb"] = round(total_size / (1024**2), 2)

        else:
            result["errors"].append(f"find command failed: {process.stderr}")

    except subprocess.TimeoutExpired:
        result["errors"].append("Cleanup timeout after 60s")
    except Exception as e:
        result["errors"].append(f"Error: {str(e)}")

    return result


def cleanup_package_cache(dry_run: bool = False) -> Dict:
    """
    清理包管理器缓存

    Returns:
        清理结果
    """
    result = {
        "package_manager": None,
        "space_freed_mb": 0,
        "errors": []
    }

    # 检测包管理器
    if shutil.which("apt-get"):
        result["package_manager"] = "apt"
        cmd = ["apt-get", "clean"]

        if dry_run:
            # 检查缓存大小
            cache_path = Path("/var/cache/apt/archives")
            if cache_path.exists():
                try:
                    cache_size = sum(
                        f.stat().st_size
                        for f in cache_path.rglob("*")
                        if f.is_file()
                    )
                    result["space_freed_mb"] = round(cache_size / (1024**2), 2)
                except Exception as e:
                    result["errors"].append(f"Error calculating cache size: {e}")
        else:
            try:
                subprocess.run(cmd, check=True, timeout=30, capture_output=True)
            except subprocess.CalledProcessError as e:
                result["errors"].append(f"apt-get clean failed: {e.stderr.decode()}")
            except subprocess.TimeoutExpired:
                result["errors"].append("apt-get clean timeout")

    elif shutil.which("yum"):
        result["package_manager"] = "yum"
        cmd = ["yum", "clean", "all"]

        if not dry_run:
            try:
                subprocess.run(cmd, check=True, timeout=30, capture_output=True)
            except subprocess.CalledProcessError as e:
                result["errors"].append(f"yum clean failed: {e.stderr.decode()}")
            except subprocess.TimeoutExpired:
                result["errors"].append("yum clean timeout")

    elif shutil.which("dnf"):
        result["package_manager"] = "dnf"
        cmd = ["dnf", "clean", "all"]

        if not dry_run:
            try:
                subprocess.run(cmd, check=True, timeout=30, capture_output=True)
            except subprocess.CalledProcessError as e:
                result["errors"].append(f"dnf clean failed: {e.stderr.decode()}")
            except subprocess.TimeoutExpired:
                result["errors"].append("dnf clean timeout")
    else:
        result["errors"].append("No supported package manager found")

    return result


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="L1 磁盘空间清理工具")
    parser.add_argument(
        "--safe",
        action="store_true",
        help="仅执行安全的清理操作（推荐）"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅报告将要执行的操作，不实际删除"
    )
    parser.add_argument(
        "--tmp-days",
        type=int,
        default=7,
        help="清理 /tmp 中多少天之前的文件（默认：7）"
    )
    parser.add_argument(
        "--log-days",
        type=int,
        default=30,
        help="清理 /var/log 中多少天之前的压缩日志（默认：30）"
    )
    parser.add_argument(
        "-o", "--output",
        help="输出结果到 JSON 文件"
    )

    args = parser.parse_args()

    # 检查权限
    if os.geteuid() != 0 and not args.dry_run:
        print("Warning: This script should be run as root for full functionality", file=sys.stderr)

    # 记录清理前的磁盘使用情况
    total_gb, used_before, free_before = get_disk_usage("/")
    usage_percent_before = (used_before / total_gb) * 100

    print(f"=== Disk Cleanup Tool ===")
    print(f"Mode: {'DRY-RUN' if args.dry_run else 'EXECUTE'}")
    print(f"Safety mode: {'ON' if args.safe else 'OFF'}")
    print(f"\nDisk usage before: {usage_percent_before:.1f}% ({used_before:.1f}GB / {total_gb:.1f}GB)")
    print(f"Free space: {free_before:.1f}GB\n")

    # 执行清理操作
    results = []

    # 1. 清理 /tmp
    print("1. Cleaning /tmp directory...")
    tmp_result = cleanup_tmp_directory(dry_run=args.dry_run, days=args.tmp_days)
    results.append(tmp_result)
    print(f"   Files: {tmp_result['files_removed']}, Space: {tmp_result['space_freed_mb']}MB")
    if tmp_result['errors']:
        for error in tmp_result['errors']:
            print(f"   Error: {error}")

    # 2. 清理旧日志
    print("2. Cleaning old logs...")
    log_result = cleanup_old_logs(dry_run=args.dry_run, days=args.log_days)
    results.append(log_result)
    print(f"   Files: {log_result['files_removed']}, Space: {log_result['space_freed_mb']}MB")
    if log_result['errors']:
        for error in log_result['errors']:
            print(f"   Error: {error}")

    # 3. 清理包管理器缓存
    print("3. Cleaning package manager cache...")
    cache_result = cleanup_package_cache(dry_run=args.dry_run)
    results.append(cache_result)
    print(f"   Package manager: {cache_result['package_manager']}")
    if cache_result['errors']:
        for error in cache_result['errors']:
            print(f"   Error: {error}")

    # 记录清理后的磁盘使用情况
    total_gb, used_after, free_after = get_disk_usage("/")
    usage_percent_after = (used_after / total_gb) * 100

    space_freed = free_after - free_before

    print(f"\n=== Results ===")
    print(f"Disk usage after: {usage_percent_after:.1f}% ({used_after:.1f}GB / {total_gb:.1f}GB)")
    print(f"Free space: {free_after:.1f}GB")
    print(f"Space freed: {space_freed:.2f}GB")

    # 生成最终报告
    final_report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "dry_run" if args.dry_run else "execute",
        "disk_usage_before": round(usage_percent_before, 2),
        "disk_usage_after": round(usage_percent_after, 2),
        "space_freed_gb": round(space_freed, 2),
        "operations": results
    }

    # 输出到文件
    if args.output:
        with open(args.output, "w") as f:
            json.dump(final_report, f, indent=2)
        print(f"\nReport saved to: {args.output}")
    else:
        print(f"\nJSON Report:")
        print(json.dumps(final_report, indent=2))


if __name__ == "__main__":
    main()
