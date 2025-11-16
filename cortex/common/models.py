"""
Cortex 共享数据模型定义
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field


class IssueLevel(str, Enum):
    """问题级别"""

    L1 = "L1"  # 可自动修复
    L2 = "L2"  # 需决策批准
    L3 = "L3"  # 严重/未知问题


class Severity(str, Enum):
    """严重程度"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActionResult(str, Enum):
    """操作结果"""

    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class AgentStatus(str, Enum):
    """Agent 状态"""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"


# ==================== 系统指标模型 ====================


class SystemMetrics(BaseModel):
    """系统指标"""

    cpu_percent: float = Field(..., description="CPU 使用率 (%)")
    memory_percent: float = Field(..., description="内存使用率 (%)")
    disk_percent: float = Field(..., description="磁盘使用率 (%)")
    load_average: Tuple[float, float, float] = Field(..., description="系统负载 (1/5/15分钟)")
    uptime_seconds: int = Field(..., description="运行时间 (秒)")

    # 可选的详细指标
    process_count: Optional[int] = Field(None, description="进程数量")
    disk_io: Optional[Dict[str, int]] = Field(None, description="磁盘 IO 统计")
    network_io: Optional[Dict[str, int]] = Field(None, description="网络 IO 统计")

    class Config:
        json_schema_extra = {
            "example": {
                "cpu_percent": 45.2,
                "memory_percent": 62.1,
                "disk_percent": 85.0,
                "load_average": [1.2, 1.5, 1.8],
                "uptime_seconds": 864000,
                "process_count": 156,
            }
        }


# ==================== 问题报告模型 ====================


class IssueReport(BaseModel):
    """问题报告"""

    level: IssueLevel = Field(..., description="问题级别")
    type: str = Field(..., description="问题类型")
    description: str = Field(..., description="问题描述")
    severity: Severity = Field(..., description="严重程度")

    # L2 决策相关字段
    proposed_fix: Optional[str] = Field(None, description="建议修复操作")
    risk_assessment: Optional[str] = Field(None, description="风险评估")

    # 附加信息
    details: Dict[str, Any] = Field(default_factory=dict, description="详细信息")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="发现时间")

    class Config:
        json_schema_extra = {
            "example": {
                "level": "L2",
                "type": "service_down",
                "description": "nginx 服务意外停止",
                "severity": "high",
                "proposed_fix": "systemctl restart nginx",
                "risk_assessment": "中风险：重启会短暂中断 Web 服务",
                "details": {"service": "nginx", "last_active": "2025-11-16T09:45:00Z"},
                "timestamp": "2025-11-16T10:00:00Z",
            }
        }


# ==================== 操作报告模型 ====================


class ActionReport(BaseModel):
    """修复操作报告"""

    level: Literal["L1", "L2"] = Field(..., description="操作级别")
    action: str = Field(..., description="执行的操作")
    result: ActionResult = Field(..., description="操作结果")
    details: str = Field(..., description="详细说明")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="执行时间")

    # Intent-Engine 意图 ID（如已记录）
    intent_id: Optional[int] = Field(None, description="关联的意图 ID")

    class Config:
        json_schema_extra = {
            "example": {
                "level": "L1",
                "action": "cleaned_disk_space",
                "result": "success",
                "details": "Cleaned /tmp and old logs, freed 5.2GB",
                "timestamp": "2025-11-16T10:00:15Z",
                "intent_id": 1234,
            }
        }


# ==================== Probe 上报数据模型 ====================


class ProbeReport(BaseModel):
    """Probe 上报数据"""

    agent_id: str = Field(..., description="节点 ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="上报时间")
    status: AgentStatus = Field(..., description="节点状态")

    # 系统指标
    metrics: SystemMetrics = Field(..., description="系统指标")

    # 发现的问题
    issues: List[IssueReport] = Field(default_factory=list, description="问题列表")

    # 已执行的修复操作
    actions_taken: List[ActionReport] = Field(default_factory=list, description="已执行操作")

    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")

    class Config:
        json_schema_extra = {
            "example": {
                "agent_id": "node-prod-001",
                "timestamp": "2025-11-16T10:00:00Z",
                "status": "warning",
                "metrics": {
                    "cpu_percent": 45.2,
                    "memory_percent": 62.1,
                    "disk_percent": 92.5,
                    "load_average": [1.2, 1.5, 1.8],
                    "uptime_seconds": 864000,
                },
                "issues": [],
                "actions_taken": [],
                "metadata": {"probe_version": "1.0.0"},
            }
        }


# ==================== 决策相关模型 ====================


class DecisionRequest(BaseModel):
    """L2 决策请求"""

    agent_id: str = Field(..., description="节点 ID")
    issue: IssueReport = Field(..., description="问题详情")
    context: Dict[str, Any] = Field(default_factory=dict, description="上下文信息")


class DecisionResponse(BaseModel):
    """L2 决策响应"""

    decision_id: int = Field(..., description="决策 ID")
    status: Literal["approved", "rejected"] = Field(..., description="决策结果")
    reason: str = Field(..., description="决策理由")
    llm_analysis: Optional[str] = Field(None, description="LLM 分析结果")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="决策时间")
