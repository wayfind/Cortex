#!/usr/bin/env python3
"""
报告构建工具

聚合所有巡检结果，生成统一的 Probe 报告
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def load_config() -> Dict[str, Any]:
    """加载 Agent 配置"""
    config_path = Path("/etc/cortex/config.yaml")

    # 如果配置文件不存在，使用默认值
    if not config_path.exists():
        return {
            "agent": {
                "id": "agent-unknown",
                "name": "Cortex Agent"
            }
        }

    try:
        import yaml
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    except (ImportError, Exception):
        # 如果 yaml 不可用或读取失败，返回默认值
        return {
            "agent": {
                "id": "agent-unknown",
                "name": "Cortex Agent"
            }
        }


def determine_overall_status(issues: List[Dict], actions: List[Dict]) -> str:
    """
    根据问题和修复动作确定整体状态

    Returns:
        "healthy" | "warning" | "critical"
    """
    # 如果有 L3 问题，状态为 critical
    for issue in issues:
        if issue.get("level") == "L3":
            return "critical"

    # 如果有 L2 问题，状态为 warning
    for issue in issues:
        if issue.get("level") == "L2":
            return "warning"

    # 如果有 L1 问题但已修复，状态为 healthy
    # 如果有 L1 问题但修复失败，状态为 warning
    for action in actions:
        if action.get("level") == "L1" and action.get("result") == "failed":
            return "warning"

    # 没有问题或所有问题已修复
    return "healthy"


def build_report(
    metrics: Dict[str, float],
    issues: List[Dict],
    actions: List[Dict],
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    构建最终报告

    Args:
        metrics: 系统指标 {"cpu_percent": 45.2, "memory_percent": 62.1, ...}
        issues: 发现的问题列表
        actions: 已执行的修复动作列表
        config: Agent 配置

    Returns:
        完整的报告 JSON
    """
    agent_id = config.get("agent", {}).get("id", "agent-unknown")
    status = determine_overall_status(issues, actions)

    report = {
        "agent_id": agent_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "metrics": metrics,
        "issues": issues,
        "actions_taken": actions,
    }

    return report


def load_json_file(file_path: str) -> Any:
    """加载 JSON 文件"""
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: File not found: {file_path}", file=sys.stderr)
        return None
    except json.JSONDecodeError as e:
        print(f"Warning: Invalid JSON in {file_path}: {e}", file=sys.stderr)
        return None


def extract_metrics_from_checks(
    disk_result: Dict,
    memory_result: Dict,
    cpu_result: Dict
) -> Dict[str, float]:
    """从各个检查结果中提取关键指标"""
    metrics = {}

    # 磁盘指标
    if disk_result and disk_result.get("status") == "ok":
        metrics["disk_percent"] = disk_result.get("max_usage_percent", 0.0)

    # 内存指标
    if memory_result and memory_result.get("status") == "ok":
        metrics["memory_percent"] = memory_result.get("memory_percent", 0.0)

    # CPU 指标
    if cpu_result and cpu_result.get("status") == "ok":
        metrics["cpu_percent"] = cpu_result.get("cpu_percent", 0.0)

    return metrics


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="构建 Probe 巡检报告")
    parser.add_argument(
        "--disk",
        help="磁盘检查结果 JSON 文件"
    )
    parser.add_argument(
        "--memory",
        help="内存检查结果 JSON 文件"
    )
    parser.add_argument(
        "--cpu",
        help="CPU 检查结果 JSON 文件"
    )
    parser.add_argument(
        "--services",
        help="服务检查结果 JSON 文件"
    )
    parser.add_argument(
        "--issues",
        help="问题列表 JSON 文件（手动汇总的问题）"
    )
    parser.add_argument(
        "--actions",
        help="修复动作列表 JSON 文件（手动记录的动作）"
    )
    parser.add_argument(
        "-o", "--output",
        default="report.json",
        help="输出报告文件路径（默认：report.json）"
    )

    args = parser.parse_args()

    # 加载配置
    config = load_config()

    # 加载各个检查结果
    disk_result = load_json_file(args.disk) if args.disk else {}
    memory_result = load_json_file(args.memory) if args.memory else {}
    cpu_result = load_json_file(args.cpu) if args.cpu else {}
    services_result = load_json_file(args.services) if args.services else {}

    # 提取指标
    metrics = extract_metrics_from_checks(disk_result, memory_result, cpu_result)

    # 加载问题和动作列表
    issues = []
    actions = []

    if args.issues:
        loaded_issues = load_json_file(args.issues)
        if loaded_issues and isinstance(loaded_issues, list):
            issues = loaded_issues

    if args.actions:
        loaded_actions = load_json_file(args.actions)
        if loaded_actions and isinstance(loaded_actions, list):
            actions = loaded_actions

    # 从检查结果中自动提取问题
    # 磁盘问题
    if disk_result and disk_result.get("status") in ["warning", "fixed"]:
        if disk_result.get("level") in ["L1", "L2", "L3"]:
            issue = {
                "level": disk_result["level"],
                "type": disk_result.get("type", "disk_space"),
                "severity": disk_result.get("severity", "medium"),
                "description": disk_result.get("description", "Disk space issue"),
                "proposed_fix": disk_result.get("proposed_fix", ""),
                "risk_assessment": disk_result.get("risk_assessment", ""),
                "details": disk_result.get("details", {})
            }

            # 如果已修复，记录为 action
            if disk_result.get("status") == "fixed":
                action = {
                    "level": disk_result["level"],
                    "action": "disk_cleanup",
                    "result": "success",
                    "details": disk_result.get("description", "Fixed disk issue"),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                actions.append(action)
            else:
                issues.append(issue)

    # 类似地处理内存问题
    if memory_result and memory_result.get("status") in ["warning", "fixed"]:
        if memory_result.get("level") in ["L1", "L2", "L3"]:
            issue = {
                "level": memory_result["level"],
                "type": memory_result.get("type", "memory_high"),
                "severity": memory_result.get("severity", "medium"),
                "description": memory_result.get("description", "Memory issue"),
                "proposed_fix": memory_result.get("proposed_fix", ""),
                "risk_assessment": memory_result.get("risk_assessment", ""),
                "details": memory_result.get("details", {})
            }

            if memory_result.get("status") == "fixed":
                action = {
                    "level": memory_result["level"],
                    "action": "memory_cleanup",
                    "result": "success",
                    "details": memory_result.get("description", "Fixed memory issue"),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                actions.append(action)
            else:
                issues.append(issue)

    # CPU 问题
    if cpu_result and cpu_result.get("status") in ["warning", "fixed"]:
        if cpu_result.get("level") in ["L1", "L2", "L3"]:
            issue = {
                "level": cpu_result["level"],
                "type": cpu_result.get("type", "cpu_high"),
                "severity": cpu_result.get("severity", "medium"),
                "description": cpu_result.get("description", "CPU issue"),
                "proposed_fix": cpu_result.get("proposed_fix", ""),
                "risk_assessment": cpu_result.get("risk_assessment", ""),
                "details": cpu_result.get("details", {})
            }

            if cpu_result.get("status") == "fixed":
                action = {
                    "level": cpu_result["level"],
                    "action": "cpu_throttle",
                    "result": "success",
                    "details": cpu_result.get("description", "Fixed CPU issue"),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                actions.append(action)
            else:
                issues.append(issue)

    # 服务问题
    if services_result and services_result.get("status") in ["warning", "fixed"]:
        if services_result.get("level") in ["L1", "L2", "L3"]:
            issue = {
                "level": services_result["level"],
                "type": services_result.get("type", "service_failed"),
                "severity": services_result.get("severity", "high"),
                "description": services_result.get("description", "Service issue"),
                "proposed_fix": services_result.get("proposed_fix", ""),
                "risk_assessment": services_result.get("risk_assessment", ""),
                "details": services_result.get("details", {})
            }

            if services_result.get("status") == "fixed":
                action = {
                    "level": services_result["level"],
                    "action": "service_restart",
                    "result": "success",
                    "details": services_result.get("description", "Fixed service issue"),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                actions.append(action)
            else:
                issues.append(issue)

    # 构建最终报告
    report = build_report(metrics, issues, actions, config)

    # 输出报告
    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)

    print(f"Report generated: {args.output}")
    print(f"Status: {report['status']}")
    print(f"Issues: {len(report['issues'])}")
    print(f"Actions taken: {len(report['actions_taken'])}")


if __name__ == "__main__":
    main()
