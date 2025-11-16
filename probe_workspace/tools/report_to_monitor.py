#!/usr/bin/env python3
"""
报告上报工具

将 Probe 报告上报到 Monitor
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any

try:
    import httpx
except ImportError:
    print("Error: httpx library is required. Install with: pip install httpx")
    sys.exit(1)


def load_config() -> Dict[str, Any]:
    """加载 Agent 配置"""
    config_path = Path("/etc/cortex/config.yaml")

    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}", file=sys.stderr)
        return {}

    try:
        import yaml
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    except ImportError:
        print("Error: PyYAML library is required. Install with: pip install pyyaml")
        sys.exit(1)
    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        return {}


def load_report(report_path: str) -> Dict[str, Any]:
    """加载报告 JSON"""
    try:
        with open(report_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Report file not found: {report_path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in report file: {e}", file=sys.stderr)
        sys.exit(1)


def upload_report(report: Dict[str, Any], monitor_url: str, api_key: str = None) -> Dict[str, Any]:
    """
    上报报告到 Monitor

    Args:
        report: 报告 JSON
        monitor_url: Monitor 的 URL（例如：http://monitor.example.com）
        api_key: API 密钥（可选）

    Returns:
        Monitor 的响应

    Raises:
        HTTPError: 如果请求失败
    """
    # 构建完整的 API 端点
    api_url = f"{monitor_url.rstrip('/')}/api/reports"

    # 准备请求头
    headers = {
        "Content-Type": "application/json",
    }
    if api_key:
        headers["X-API-Key"] = api_key

    # 发送请求
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                api_url,
                json=report,
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    except httpx.TimeoutException:
        print(f"Error: Request timeout when uploading to {api_url}", file=sys.stderr)
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        print(
            f"Error: HTTP {e.response.status_code} when uploading to {api_url}",
            file=sys.stderr
        )
        print(f"Response: {e.response.text}", file=sys.stderr)
        sys.exit(1)
    except httpx.RequestError as e:
        print(f"Error: Network error when uploading to {api_url}: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="上报 Probe 报告到 Monitor")
    parser.add_argument(
        "report",
        help="报告 JSON 文件路径"
    )
    parser.add_argument(
        "--monitor-url",
        help="Monitor URL（如未指定，从配置文件读取）"
    )
    parser.add_argument(
        "--api-key",
        help="API 密钥（如未指定，从配置文件读取）"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅打印报告，不实际上报"
    )

    args = parser.parse_args()

    # 加载报告
    report = load_report(args.report)

    # 如果是 dry-run，只打印报告
    if args.dry_run:
        print("=== Report (dry-run mode) ===")
        print(json.dumps(report, indent=2))
        return

    # 确定 Monitor URL
    monitor_url = args.monitor_url
    api_key = args.api_key

    if not monitor_url:
        # 从配置文件读取
        config = load_config()
        monitor_url = config.get("agent", {}).get("upstream_monitor_url")

        if not monitor_url:
            print(
                "Error: Monitor URL not specified and not found in configuration",
                file=sys.stderr
            )
            print(
                "Either use --monitor-url or set agent.upstream_monitor_url in /etc/cortex/config.yaml",
                file=sys.stderr
            )
            sys.exit(1)

        # 尝试从配置读取 API key
        if not api_key:
            api_key = config.get("agent", {}).get("monitor_api_key")

    # 上报报告
    print(f"Uploading report to {monitor_url}...")
    try:
        response = upload_report(report, monitor_url, api_key)

        print("✓ Report uploaded successfully")
        print(f"  Report ID: {response.get('data', {}).get('report_id')}")

        # 打印 L2 决策结果
        l2_decisions = response.get('data', {}).get('l2_decisions', [])
        if l2_decisions:
            print(f"\n  L2 Decisions ({len(l2_decisions)}):")
            for decision in l2_decisions:
                print(f"    - {decision.get('issue_type')}: {decision.get('status')} ({decision.get('reason')})")

        # 打印 L3 告警数量
        l3_count = response.get('data', {}).get('l3_alerts_triggered', 0)
        if l3_count > 0:
            print(f"\n  L3 Alerts Triggered: {l3_count}")

    except Exception as e:
        print(f"✗ Failed to upload report: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
