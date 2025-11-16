"""
问题分级器 - 将发现的问题分为 L1/L2/L3 三个级别
"""

from typing import Dict, List

from cortex.common.models import IssueLevel, IssueReport, Severity


class IssueClassifier:
    """问题分级器"""

    # L1 问题类型（可安全自动修复）
    L1_ISSUE_TYPES = {
        "disk_space_low",
        "temp_files_cleanup",
        "log_rotation_needed",
        "cache_cleanup",
        "old_package_cleanup",
    }

    # L2 问题类型（需要决策批准）
    L2_ISSUE_TYPES = {
        "service_down",
        "service_failed",
        "process_crashed",
        "config_drift",
        "certificate_expiring",
        "memory_leak",
    }

    # L3 直接触发条件
    L3_SEVERITY = {Severity.CRITICAL}

    def classify(self, issues: List[IssueReport]) -> Dict[str, List[IssueReport]]:
        """
        将问题分为 L1/L2/L3 三个级别

        Args:
            issues: 问题列表

        Returns:
            分类后的问题字典
        """
        classified: Dict[str, List[IssueReport]] = {
            "L1": [],
            "L2": [],
            "L3": [],
        }

        for issue in issues:
            level = self.determine_level(issue)
            # 更新 issue 的 level 字段
            issue.level = IssueLevel(level)
            classified[level].append(issue)

        return classified

    def determine_level(self, issue: IssueReport) -> str:
        """
        判断问题级别

        优先级规则：
        1. 严重程度为 critical 或类型为 unknown -> L3
        2. 问题类型在 L1 列表中 -> L1
        3. 问题类型在 L2 列表中 -> L2
        4. 默认 -> L2（保守策略）
        """
        # 规则 1: Critical 级别或未知问题 -> L3
        if issue.severity == Severity.CRITICAL or issue.type == "unknown":
            return "L3"

        # 规则 2: 可安全自动修复的问题 -> L1
        if issue.type in self.L1_ISSUE_TYPES:
            return "L1"

        # 规则 3: 已知的需决策问题 -> L2
        if issue.type in self.L2_ISSUE_TYPES:
            return "L2"

        # 规则 4: 默认保守策略 -> L2
        return "L2"

    def add_l1_type(self, issue_type: str) -> None:
        """动态添加 L1 问题类型"""
        self.L1_ISSUE_TYPES.add(issue_type)

    def add_l2_type(self, issue_type: str) -> None:
        """动态添加 L2 问题类型"""
        self.L2_ISSUE_TYPES.add(issue_type)
