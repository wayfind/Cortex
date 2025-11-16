"""
Probe 执行器 - 核心巡检逻辑
"""

import asyncio
from datetime import datetime
from typing import Dict, List

import httpx
from anthropic import Anthropic
from loguru import logger

from cortex.common.intent_recorder import IntentRecorder
from cortex.common.models import (
    ActionReport,
    AgentStatus,
    IssueReport,
    ProbeReport,
    Severity,
    SystemMetrics,
)
from cortex.config.settings import ProbeConfig, Settings
from cortex.probe.classifier import IssueClassifier
from cortex.probe.fixer import L1AutoFixer
from cortex.probe.system_monitor import SystemMonitor


class ProbeExecutor:
    """Probe 执行器 - 实际执行巡检逻辑"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.probe_config: ProbeConfig = settings.probe
        self.agent_id = settings.agent.id

        # 初始化组件
        self.system_monitor = SystemMonitor()
        self.issue_classifier = IssueClassifier()
        self.auto_fixer = L1AutoFixer()

        # Intent 记录器
        self.intent_recorder = IntentRecorder(settings)

        # Claude SDK
        self.claude_client = Anthropic(api_key=settings.claude.api_key)

        # HTTP 客户端（用于上报）
        self.http_client = httpx.AsyncClient(timeout=30.0)

    async def execute(self) -> ProbeReport:
        """
        执行完整的巡检流程

        Returns:
            生成的 Probe 上报数据
        """
        logger.info(f"Starting probe execution for agent: {self.agent_id}")

        # 初始化 Intent 记录器
        await self.intent_recorder.initialize()

        # 记录巡检开始
        await self.intent_recorder.record_milestone(
            agent_id=self.agent_id,
            category="probe_execution_start",
            description=f"Starting probe execution for {self.agent_id}",
        )

        # 1. 收集系统信息
        system_info = self.system_monitor.collect_metrics()
        logger.debug(f"Collected system metrics: {system_info}")

        # 2. 分析系统指标，发现潜在问题
        issues = await self.analyze_metrics(system_info)
        logger.info(f"Discovered {len(issues)} potential issues")

        # 3. 问题分级
        classified_issues = self.issue_classifier.classify(issues)
        logger.info(
            f"Classified issues - L1: {len(classified_issues['L1'])}, "
            f"L2: {len(classified_issues['L2'])}, L3: {len(classified_issues['L3'])}"
        )

        # 4. L1 问题自动修复（带意图记录）
        fixed_issues: List[ActionReport] = []
        for l1_issue in classified_issues["L1"]:
            action_report = await self.auto_fixer.fix(l1_issue)
            if action_report:
                fixed_issues.append(action_report)

                # 记录 L1 修复决策
                await self.intent_recorder.record_decision(
                    agent_id=self.agent_id,
                    level="L1",
                    category=l1_issue.type,
                    description=f"Auto-fixed: {l1_issue.description}",
                    status="completed" if action_report.result.value == "success" else "failed",
                    metadata={
                        "issue_type": l1_issue.type,
                        "action": action_report.action,
                        "result": action_report.result.value,
                        "details": action_report.details,
                    },
                )

        # 记录 L3 严重问题
        for l3_issue in classified_issues["L3"]:
            await self.intent_recorder.record_blocker(
                agent_id=self.agent_id,
                category=l3_issue.type,
                description=l3_issue.description,
                metadata={
                    "severity": l3_issue.severity.value,
                    "proposed_fix": l3_issue.proposed_fix,
                    "risk_assessment": l3_issue.risk_assessment,
                },
            )

        # 5. 确定整体状态
        status = self._determine_status(system_info, classified_issues)

        # 6. 生成上报数据
        report = ProbeReport(
            agent_id=self.agent_id,
            timestamp=datetime.utcnow(),
            status=status,
            metrics=system_info,
            issues=classified_issues["L2"] + classified_issues["L3"],  # 只上报 L2/L3
            actions_taken=fixed_issues,
            metadata={
                "probe_version": "1.0.0",
                "execution_time_seconds": 0,  # TODO: 计算实际执行时间
                "llm_model": self.settings.claude.model,
            },
        )

        # 记录巡检完成
        await self.intent_recorder.record_milestone(
            agent_id=self.agent_id,
            category="probe_execution_completed",
            description=f"Probe execution completed. Status: {status.value}, "
            f"L1 fixes: {len(fixed_issues)}, L2 issues: {len(classified_issues['L2'])}, "
            f"L3 issues: {len(classified_issues['L3'])}",
            metadata={
                "status": status.value,
                "l1_fixes_count": len(fixed_issues),
                "l2_issues_count": len(classified_issues["L2"]),
                "l3_issues_count": len(classified_issues["L3"]),
            },
        )

        logger.success(f"Probe execution completed. Status: {status}")
        return report

    async def analyze_metrics(self, metrics: SystemMetrics) -> List[IssueReport]:
        """
        分析系统指标，识别问题

        Args:
            metrics: 系统指标

        Returns:
            发现的问题列表
        """
        issues: List[IssueReport] = []

        # 基于阈值的简单分析
        if metrics.cpu_percent > self.probe_config.threshold_cpu_percent:
            issues.append(
                IssueReport(
                    level="L2",  # 将被 classifier 重新分类
                    type="cpu_high",
                    description=f"CPU usage is {metrics.cpu_percent:.1f}%, exceeding threshold {self.probe_config.threshold_cpu_percent}%",
                    severity=Severity.MEDIUM,
                    proposed_fix="Investigate high CPU processes",
                    details={"cpu_percent": metrics.cpu_percent},
                )
            )

        if metrics.memory_percent > self.probe_config.threshold_memory_percent:
            issues.append(
                IssueReport(
                    level="L2",
                    type="memory_high",
                    description=f"Memory usage is {metrics.memory_percent:.1f}%, exceeding threshold {self.probe_config.threshold_memory_percent}%",
                    severity=Severity.HIGH,
                    proposed_fix="Restart memory-intensive services or clear cache",
                    details={"memory_percent": metrics.memory_percent},
                )
            )

        if metrics.disk_percent > self.probe_config.threshold_disk_percent:
            issues.append(
                IssueReport(
                    level="L1",  # 磁盘清理是 L1 操作
                    type="disk_space_low",
                    description=f"Disk usage is {metrics.disk_percent:.1f}%, exceeding threshold {self.probe_config.threshold_disk_percent}%",
                    severity=Severity.HIGH,
                    proposed_fix="Clean up old files and logs",
                    details={"disk_percent": metrics.disk_percent},
                )
            )

        # TODO: 集成 LLM 进行更智能的分析
        # llm_issues = await self.llm_inspect(metrics)
        # issues.extend(llm_issues)

        return issues

    def _determine_status(
        self, metrics: SystemMetrics, classified_issues: Dict[str, List[IssueReport]]
    ) -> AgentStatus:
        """
        根据指标和问题确定节点整体状态

        Args:
            metrics: 系统指标
            classified_issues: 分类后的问题

        Returns:
            节点状态
        """
        # 有 L3 问题 -> critical
        if classified_issues["L3"]:
            return AgentStatus.CRITICAL

        # 有 L2 问题或指标超过阈值 -> warning
        if classified_issues["L2"] or any(
            [
                metrics.cpu_percent > self.probe_config.threshold_cpu_percent,
                metrics.memory_percent > self.probe_config.threshold_memory_percent,
                metrics.disk_percent > self.probe_config.threshold_disk_percent,
            ]
        ):
            return AgentStatus.WARNING

        # 其他情况 -> healthy
        return AgentStatus.HEALTHY

    async def send_report(self, report: ProbeReport) -> None:
        """
        发送上报数据到 Monitor

        Args:
            report: 上报数据
        """
        # 确定目标 URL
        if self.settings.agent.mode == "cluster" and self.settings.agent.upstream_monitor_url:
            monitor_url = self.settings.agent.upstream_monitor_url
        else:
            # 独立模式：上报给本地 Monitor
            monitor_url = (
                f"http://{self.settings.monitor.host}:{self.settings.monitor.port}"
            )

        endpoint = f"{monitor_url}/api/v1/reports"

        try:
            logger.info(f"Sending report to {endpoint}")
            response = await self.http_client.post(
                endpoint,
                json=report.model_dump(mode="json"),
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            logger.success(f"Report sent successfully: {response.status_code}")

        except httpx.HTTPError as e:
            logger.error(f"Failed to send report: {e}")
            # TODO: 保存到本地队列，稍后重试

    async def cleanup(self) -> None:
        """清理资源"""
        await self.http_client.aclose()
        await self.intent_recorder.close()
