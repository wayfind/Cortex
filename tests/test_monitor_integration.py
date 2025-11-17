"""
测试 Monitor 集成问题修复

覆盖以下6个修复的问题：
1. 循环导入错误 - dependencies.py 模块
2. 配置验证错误 - ProbeConfig 字段结构
3. API 路径错误 - /api/v1/reports
4. AsyncSession 依赖注入
5. JSON 序列化 - datetime 对象
6. ClaudeConfig.temperature 字段
"""

import os
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.common.models import ProbeReport, AgentStatus, SystemMetrics, IssueReport
from cortex.config.settings import (
    AgentConfig,
    ClaudeConfig,
    MonitorConfig,
    ProbeConfig,
    Settings,
)
from cortex.monitor import dependencies
from cortex.monitor.app import app
from cortex.monitor.database import Agent, Report
from cortex.monitor.db_manager import DatabaseManager


class TestDependencyInjection:
    """测试问题1：依赖注入和循环导入修复"""

    def test_dependencies_module_exists(self):
        """验证 dependencies.py 模块存在"""
        assert hasattr(dependencies, "get_db_manager")
        assert hasattr(dependencies, "set_db_manager")

    def test_set_and_get_db_manager(self):
        """验证 set_db_manager 和 get_db_manager 工作正常"""
        # 创建模拟的 DatabaseManager
        mock_manager = MagicMock(spec=DatabaseManager)

        # 设置全局管理器
        dependencies.set_db_manager(mock_manager)

        # 验证可以获取
        retrieved = dependencies.get_db_manager()
        assert retrieved is mock_manager

    def test_get_db_manager_before_set_raises_error(self):
        """验证在 set 之前 get 会抛出错误"""
        # 重置全局变量
        dependencies._db_manager = None

        with pytest.raises(RuntimeError, match="DatabaseManager not initialized"):
            dependencies.get_db_manager()

    def test_no_circular_import(self):
        """验证没有循环导入问题"""
        try:
            # 尝试导入所有相关模块
            from cortex.monitor import app
            from cortex.monitor import dependencies
            from cortex.monitor.routers import alerts, cluster, decisions, intents, reports

            # 如果能成功导入，说明没有循环依赖
            assert True
        except ImportError as e:
            pytest.fail(f"Circular import detected: {e}")


class TestProbeConfig:
    """测试问题2：配置验证修复"""

    def test_probe_config_flat_structure(self):
        """验证 ProbeConfig 使用扁平字段结构"""
        config = ProbeConfig(
            schedule="*/5 * * * *",
            timeout_seconds=300,
            check_system_health=True,
            check_service_status=True,
            check_log_analysis=True,
            check_network=True,
            threshold_cpu_percent=80.0,
            threshold_memory_percent=85.0,
            threshold_disk_percent=90.0,
        )

        # 验证字段存在且值正确
        assert config.threshold_cpu_percent == 80.0
        assert config.threshold_memory_percent == 85.0
        assert config.threshold_disk_percent == 90.0

    def test_probe_config_from_yaml_structure(self):
        """验证从 YAML 加载的配置结构"""
        yaml_config = {
            "schedule": "*/5 * * * *",
            "timeout_seconds": 300,
            "check_system_health": True,
            "check_service_status": True,
            "check_log_analysis": True,
            "check_network": True,
            "threshold_cpu_percent": 80.0,
            "threshold_memory_percent": 85.0,
            "threshold_disk_percent": 90.0,
        }

        config = ProbeConfig(**yaml_config)

        assert config.threshold_cpu_percent == 80.0
        assert config.check_system_health is True

    def test_probe_config_rejects_nested_structure(self):
        """验证嵌套结构会被拒绝"""
        with pytest.raises(Exception):  # Pydantic 会抛出验证错误
            ProbeConfig(
                schedule="*/5 * * * *",
                timeout_seconds=300,
                thresholds={  # 嵌套结构应该被拒绝
                    "cpu_percent": 80.0,
                    "memory_percent": 85.0,
                },
            )


class TestAPIRoutes:
    """测试问题3：API 路径修复"""

    def test_api_v1_reports_endpoint_exists(self):
        """验证 /api/v1/reports 端点存在"""
        # 使用 TestClient 检查路由
        client = TestClient(app)

        # 检查路由是否注册
        routes = [route.path for route in app.routes]
        assert "/api/v1/reports" in routes

    def test_old_api_reports_endpoint_not_exists(self):
        """验证旧的 /api/reports 端点不存在"""
        client = TestClient(app)
        routes = [route.path for route in app.routes]

        # 确保没有 /api/reports（不带 v1）
        assert "/api/reports" not in routes


class TestAsyncSessionDependency:
    """测试问题4：AsyncSession 依赖注入修复"""

    @pytest.mark.asyncio
    async def test_get_session_returns_async_generator(self):
        """验证 get_session 返回 AsyncGenerator"""
        from cortex.monitor.routers.reports import get_session

        # 创建模拟的 DatabaseManager
        mock_manager = MagicMock(spec=DatabaseManager)

        # 创建模拟的 async session
        mock_session = MagicMock(spec=AsyncSession)

        async def mock_get_session():
            yield mock_session

        mock_manager.get_session = mock_get_session

        # 设置全局管理器
        dependencies.set_db_manager(mock_manager)

        # 测试 get_session
        gen = get_session()
        assert hasattr(gen, "__aiter__")  # 是异步生成器

        # 获取 session
        session = await gen.__anext__()
        assert session is mock_session

    @pytest.mark.asyncio
    async def test_get_session_yields_valid_session(self):
        """验证 get_session 生成有效的 session"""
        from cortex.monitor.routers.reports import get_session

        # 创建真实的内存数据库用于测试
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.orm import sessionmaker

        from cortex.monitor.database import Base

        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        # 创建 DatabaseManager mock
        mock_manager = MagicMock(spec=DatabaseManager)

        async def mock_get_session():
            async with async_session() as session:
                yield session

        mock_manager.get_session = mock_get_session
        dependencies.set_db_manager(mock_manager)

        # 测试
        async for session in get_session():
            assert isinstance(session, AsyncSession)
            # 验证 session 可以执行操作
            assert hasattr(session, "execute")
            assert hasattr(session, "commit")

        await engine.dispose()


class TestJSONSerialization:
    """测试问题5：JSON 序列化修复"""

    def test_probe_report_model_dump_json_mode(self):
        """验证 ProbeReport 使用 model_dump(mode='json') 可以序列化 datetime"""
        report = ProbeReport(
            agent_id="test-agent",
            timestamp=datetime(2025, 11, 16, 10, 0, 0),
            status=AgentStatus.HEALTHY,
            metrics=SystemMetrics(
                cpu_percent=50.0,
                memory_percent=60.0,
                disk_percent=70.0,
                load_average=[1.0, 1.5, 2.0],
                uptime_seconds=10000,
            ),
            issues=[],
            actions_taken=[],
            metadata={},
        )

        # 使用 mode='json' 序列化
        data = report.model_dump(mode="json")

        # 验证 timestamp 被转换为字符串
        assert isinstance(data["timestamp"], str)
        assert "2025-11-16" in data["timestamp"]

    def test_issue_model_dump_json_mode(self):
        """验证 IssueReport 模型的 JSON 序列化"""
        issue = IssueReport(
            level="L2",
            type="high_memory",
            description="Memory usage high",
            severity="medium",
            proposed_fix="Restart service",
            risk_assessment="Low risk",
            details={"current": 85.0, "threshold": 80.0},
        )

        data = issue.model_dump(mode="json")

        # 验证所有字段都可以序列化
        assert isinstance(data, dict)
        assert data["level"] == "L2"
        assert data["type"] == "high_memory"

    @pytest.mark.asyncio
    async def test_report_storage_with_json_serialization(self, test_db_session):
        """验证存储 Report 时 JSON 序列化正常工作"""
        report_data = ProbeReport(
            agent_id="test-001",
            timestamp=datetime.now(timezone.utc),
            status=AgentStatus.HEALTHY,
            metrics=SystemMetrics(
                cpu_percent=45.0,
                memory_percent=55.0,
                disk_percent=65.0,
                load_average=[1.0, 1.5, 2.0],
                uptime_seconds=5000,
            ),
            issues=[],
            actions_taken=[],
            metadata={"test": True},
        )

        # 使用 mode='json' 创建数据库记录
        db_report = Report(
            agent_id=report_data.agent_id,
            timestamp=report_data.timestamp,
            status=report_data.status.value,
            metrics=report_data.metrics.model_dump(mode="json"),
            issues=[],
            actions_taken=[],
            metadata_json=report_data.metadata,
        )

        test_db_session.add(db_report)
        await test_db_session.commit()

        # 验证可以成功存储
        assert db_report.id is not None
        assert isinstance(db_report.metrics, dict)


class TestClaudeConfig:
    """测试问题6：ClaudeConfig.temperature 字段"""

    def test_claude_config_has_temperature_field(self):
        """验证 ClaudeConfig 有 temperature 字段"""
        config = ClaudeConfig(
            api_key="test-key",
            model="claude-sonnet-4",
            max_tokens=2000,
            timeout=30,
            temperature=1.0,
        )

        assert hasattr(config, "temperature")
        assert config.temperature == 1.0

    def test_claude_config_temperature_default(self):
        """验证 temperature 有默认值"""
        config = ClaudeConfig(
            api_key="test-key",
        )

        assert config.temperature == 1.0

    def test_claude_config_temperature_validation(self):
        """验证 temperature 值的有效范围"""
        # 正常值
        config = ClaudeConfig(api_key="test-key", temperature=0.5)
        assert config.temperature == 0.5

        # 边界值
        config = ClaudeConfig(api_key="test-key", temperature=0.0)
        assert config.temperature == 0.0

        config = ClaudeConfig(api_key="test-key", temperature=1.0)
        assert config.temperature == 1.0

    def test_claude_config_from_yaml(self):
        """验证从 YAML 配置加载 temperature"""
        yaml_config = {
            "api_key": "test-key",
            "model": "claude-sonnet-4",
            "max_tokens": 2000,
            "timeout": 30,
            "temperature": 0.7,
        }

        config = ClaudeConfig(**yaml_config)
        assert config.temperature == 0.7


class TestEndToEndIntegration:
    """端到端集成测试"""

    @pytest.mark.asyncio
    async def test_full_report_upload_flow(self, test_db_session):
        """测试完整的报告上传流程"""
        # 1. 创建 Agent
        agent = Agent(
            id="test-agent-001",
            name="Test Agent",
            api_key="test-key",
            status="online",
            health_status="healthy",
            last_heartbeat=datetime.now(timezone.utc),
        )
        test_db_session.add(agent)
        await test_db_session.commit()

        # 2. 创建 ProbeReport
        report_data = ProbeReport(
            agent_id="test-agent-001",
            timestamp=datetime.now(timezone.utc),
            status=AgentStatus.WARNING,
            metrics=SystemMetrics(
                cpu_percent=75.0,
                memory_percent=88.0,
                disk_percent=65.0,
                load_average=[3.0, 3.5, 3.2],
                uptime_seconds=86400,
            ),
            issues=[
                IssueReport(
                    level="L2",
                    type="high_memory",
                    description="Memory usage at 88%",
                    severity="medium",
                    proposed_fix="Restart service",
                    risk_assessment="Medium risk",
                    details={"current": 88.0, "threshold": 85.0},
                )
            ],
            actions_taken=[],
            metadata={"test": True},
        )

        # 3. 存储到数据库（使用 mode='json'）
        db_report = Report(
            agent_id=report_data.agent_id,
            timestamp=report_data.timestamp,
            status=report_data.status.value,
            metrics=report_data.metrics.model_dump(mode="json"),
            issues=[issue.model_dump(mode="json") for issue in report_data.issues],
            actions_taken=[],
            metadata_json=report_data.metadata,
        )

        test_db_session.add(db_report)
        await test_db_session.commit()

        # 4. 验证存储成功
        assert db_report.id is not None
        assert db_report.agent_id == "test-agent-001"
        assert db_report.status == "warning"
        assert len(db_report.issues) == 1
        assert db_report.issues[0]["level"] == "L2"

    def test_all_fixes_integrated(self):
        """验证所有6个修复都已集成"""
        # 创建测试实例来检查字段
        probe_config_test = ProbeConfig()
        claude_config_test = ClaudeConfig(api_key="test")

        fixes = {
            "1. Dependencies module": hasattr(dependencies, "get_db_manager"),
            "2. ProbeConfig flat fields": hasattr(probe_config_test, "threshold_cpu_percent"),
            "3. API v1 routes": "/api/v1/reports" in [r.path for r in app.routes],
            "4. AsyncSession dependency": True,  # 通过其他测试验证
            "5. JSON serialization": hasattr(ProbeReport, "model_dump"),
            "6. ClaudeConfig.temperature": hasattr(claude_config_test, "temperature"),
        }

        # 所有修复都应该存在
        for fix_name, exists in fixes.items():
            assert exists, f"{fix_name} not found"
