"""
上级转发器

在集群模式下，将 L2 决策请求转发到上级 Monitor
"""

from typing import Optional

import httpx
from loguru import logger

from cortex.common.models import IssueReport
from cortex.common.retry import retry_async, PATIENT_RETRY_CONFIG
from cortex.monitor.database import Agent


class UpstreamForwarder:
    """上级转发器 - 负责将 L2 请求转发到上级 Monitor"""

    def __init__(self, timeout: int = 30):
        """
        初始化上级转发器

        Args:
            timeout: HTTP 请求超时时间（秒）
        """
        self.timeout = timeout

    async def forward_decision_request(
        self, issue: IssueReport, agent_id: str, upstream_monitor_url: str
    ) -> Optional[dict]:
        """
        将 L2 决策请求转发到上级 Monitor（带重试机制）

        Args:
            issue: 问题报告
            agent_id: 报告此问题的 Agent ID
            upstream_monitor_url: 上级 Monitor 的 URL

        Returns:
            上级 Monitor 的决策响应，如果失败返回 None
        """
        url = f"{upstream_monitor_url.rstrip('/')}/api/v1/decisions/request"

        payload = {
            "agent_id": agent_id,
            "issue_type": issue.type,
            "issue_description": issue.description,
            "severity": issue.severity.value,
            "proposed_action": issue.proposed_fix,
            "risk_assessment": issue.risk_assessment,
            "details": issue.details,
        }

        logger.info(
            f"Forwarding L2 decision request to upstream {upstream_monitor_url} "
            f"for agent {agent_id}, issue: {issue.type}"
        )

        # 定义实际的请求函数（用于重试）
        async def _make_request():
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                return response.json()

        try:
            # 使用重试机制执行请求
            decision_data = await retry_async(
                _make_request, config=PATIENT_RETRY_CONFIG
            )

            logger.success(
                f"Received decision from upstream: {decision_data['data']['status'].upper()} - "
                f"{decision_data['data']['reason']}"
            )

            return decision_data["data"]

        except httpx.HTTPError as e:
            logger.error(f"HTTP error forwarding to upstream after retries: {e}")
            return None
        except Exception as e:
            logger.error(
                f"Error forwarding to upstream after retries: {e}", exc_info=True
            )
            return None

    async def check_agent_needs_upstream(self, agent: Agent) -> bool:
        """
        检查 Agent 是否需要转发到上级

        Args:
            agent: Agent 对象

        Returns:
            True 如果需要转发到上级，False 否则
        """
        # 如果 Agent 配置了 upstream_monitor_url，说明它在集群模式下
        return agent.upstream_monitor_url is not None and agent.upstream_monitor_url != ""
