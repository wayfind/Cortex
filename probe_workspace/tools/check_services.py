#!/usr/bin/env python3
"""
关键服务状态检查工具

检查系统关键服务的运行状态，输出 JSON 格式结果
"""

import json
import subprocess
import sys
from typing import Dict, List, Optional


# 默认检查的关键服务列表
DEFAULT_SERVICES = [
    "sshd",
    "cron",
    "rsyslog",
    "systemd-journald",
]


def check_service_systemd(service_name: str) -> Optional[Dict]:
    """使用 systemctl 检查服务状态"""
    try:
        # 检查服务是否存在
        result = subprocess.run(
            ["systemctl", "status", service_name],
            capture_output=True,
            text=True,
            timeout=5,
        )

        # 获取服务状态
        is_active = subprocess.run(
            ["systemctl", "is-active", service_name],
            capture_output=True,
            text=True,
            timeout=5,
        )

        is_enabled = subprocess.run(
            ["systemctl", "is-enabled", service_name],
            capture_output=True,
            text=True,
            timeout=5,
        )

        active_state = is_active.stdout.strip()
        enabled_state = is_enabled.stdout.strip()

        return {
            "name": service_name,
            "manager": "systemd",
            "active": active_state == "active",
            "enabled": enabled_state == "enabled",
            "status": active_state,
            "enabled_status": enabled_state,
        }

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        return None


def check_service_init(service_name: str) -> Optional[Dict]:
    """使用传统 init 脚本检查服务状态"""
    try:
        result = subprocess.run(
            ["service", service_name, "status"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        # 根据返回码判断状态
        is_running = result.returncode == 0

        return {
            "name": service_name,
            "manager": "init",
            "active": is_running,
            "enabled": None,  # init 无法判断是否开机自启
            "status": "active" if is_running else "inactive",
        }

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        return None


def check_service(service_name: str) -> Optional[Dict]:
    """检查服务状态（自动选择合适的方法）"""
    # 优先使用 systemd
    result = check_service_systemd(service_name)
    if result:
        return result

    # 尝试使用 init
    result = check_service_init(service_name)
    if result:
        return result

    return {
        "name": service_name,
        "manager": "unknown",
        "active": None,
        "enabled": None,
        "status": "unknown",
        "error": "Unable to determine service status",
    }


def get_failed_services() -> List[str]:
    """获取所有失败的 systemd 服务"""
    failed_services = []

    try:
        result = subprocess.run(
            ["systemctl", "list-units", "--state=failed", "--no-pager"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            for line in lines:
                # 跳过表头和底部统计
                if line.startswith("●") or line.startswith("UNIT"):
                    parts = line.split()
                    if len(parts) > 0 and parts[0] not in ["●", "UNIT"]:
                        service_name = parts[0].replace("●", "").strip()
                        if service_name and service_name.endswith(".service"):
                            failed_services.append(service_name)

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        pass

    return failed_services


def main():
    """主函数"""
    # 从命令行参数读取要检查的服务列表
    if len(sys.argv) > 1:
        services_to_check = sys.argv[1:]
    else:
        services_to_check = DEFAULT_SERVICES

    # 检查每个服务
    services_status = []
    for service in services_to_check:
        status = check_service(service)
        if status:
            services_status.append(status)

    # 获取所有失败的服务
    failed_services = get_failed_services()

    # 统计
    total = len(services_status)
    active_count = sum(1 for s in services_status if s.get("active") is True)
    inactive_count = sum(1 for s in services_status if s.get("active") is False)
    unknown_count = sum(1 for s in services_status if s.get("active") is None)

    result = {
        "status": "ok",
        "summary": {
            "total": total,
            "active": active_count,
            "inactive": inactive_count,
            "unknown": unknown_count,
        },
        "services": services_status,
        "failed_services": failed_services,
    }

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
