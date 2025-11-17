"""
Probe 服务集成测试

测试 FastAPI + APScheduler + Claude Executor + WebSocket 的完整架构
"""

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from cortex.config.settings import Settings, AgentConfig, ProbeConfig, MonitorConfig, ClaudeConfig
from cortex.probe.app import app, ws_manager, scheduler_service


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    """创建测试配置"""
    workspace = tmp_path / "probe_workspace"
    workspace.mkdir()

    # 创建必要的子目录
    (workspace / "output").mkdir()
    (workspace / "inspections").mkdir()
    (workspace / "tools").mkdir()

    return Settings(
        agent=AgentConfig(
            id="test-probe",
            name="Test Probe",
            mode="standalone"
        ),
        probe=ProbeConfig(
            host="127.0.0.1",
            port=8001,
            schedule="0 * * * *",
            timeout_seconds=60,
            workspace=str(workspace)
        ),
        monitor=MonitorConfig(
            host="127.0.0.1",
            port=8000,
            database_url="sqlite:///:memory:",
            registration_token="test-token"
        ),
        claude=ClaudeConfig(
            api_key="test-key"
        )
    )


@pytest.fixture
def client(test_settings: Settings, monkeypatch) -> TestClient:
    """创建测试客户端"""
    # Mock get_settings to return test settings
    from cortex.config import settings as settings_module
    monkeypatch.setattr(settings_module, '_settings', test_settings)

    # Create client with lifespan
    with TestClient(app) as client:
        yield client


class TestProbeAPI:
    """Probe API 测试"""

    def test_health_check(self, client: TestClient):
        """测试健康检查端点"""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "timestamp" in data

    def test_get_status(self, client: TestClient):
        """测试状态查询端点"""
        response = client.get("/status")
        assert response.status_code == 200

        data = response.json()
        assert "scheduler_status" in data
        assert "paused" in data

    def test_get_schedule(self, client: TestClient):
        """测试调度信息查询"""
        response = client.get("/schedule")
        assert response.status_code == 200

        data = response.json()
        assert "jobs" in data
        assert "scheduler_running" in data

    def test_pause_resume_schedule(self, client: TestClient):
        """测试暂停和恢复调度"""
        # 暂停
        response = client.post("/schedule/pause")
        assert response.status_code == 200
        assert response.json()["status"] == "paused"

        # 恢复
        response = client.post("/schedule/resume")
        assert response.status_code == 200
        assert response.json()["status"] == "resumed"

    def test_get_reports(self, client: TestClient):
        """测试报告列表查询"""
        response = client.get("/reports")
        assert response.status_code == 200

        data = response.json()
        assert "reports" in data
        assert isinstance(data["reports"], list)


class TestClaudeExecutor:
    """Claude Executor 测试"""

    @pytest.mark.asyncio
    async def test_executor_initialization(self, test_settings: Settings):
        """测试执行器初始化"""
        from cortex.probe.claude_executor import ClaudeExecutor

        workspace = test_settings.probe.workspace
        timeout = test_settings.probe.timeout_seconds

        executor = ClaudeExecutor(workspace_path=workspace, timeout=timeout)

        assert executor.workspace_path == Path(workspace)
        assert executor.timeout == timeout
        assert not executor.is_running()

    @pytest.mark.asyncio
    async def test_executor_status_tracking(self, test_settings: Settings):
        """测试执行状态跟踪"""
        from cortex.probe.claude_executor import ClaudeExecutor

        workspace = test_settings.probe.workspace
        executor = ClaudeExecutor(workspace_path=workspace, timeout=5)

        # 初始状态
        assert executor.get_current_status() is None

        # 注意：实际执行会失败，因为没有真实的 claude 命令
        # 这里只测试状态跟踪机制


class TestWebSocketManager:
    """WebSocket Manager 测试"""

    @pytest.mark.asyncio
    async def test_connection_management(self):
        """测试连接管理"""
        from cortex.probe.websocket_manager import WebSocketManager

        manager = WebSocketManager()

        # 初始状态
        assert manager.get_connection_count() == 0

    @pytest.mark.asyncio
    async def test_broadcast_messages(self):
        """测试消息广播"""
        from cortex.probe.websocket_manager import WebSocketManager

        manager = WebSocketManager()

        # 测试消息构建（无实际连接）
        await manager.broadcast_inspection_started("test-exec-123")
        # 应该不会抛出异常


class TestSchedulerService:
    """Scheduler Service 测试"""

    @pytest.mark.asyncio
    async def test_scheduler_initialization(self, test_settings: Settings):
        """测试调度器初始化"""
        from cortex.probe.scheduler_service import ProbeSchedulerService
        from cortex.probe.websocket_manager import WebSocketManager

        ws_mgr = WebSocketManager()
        scheduler = ProbeSchedulerService(test_settings, ws_mgr)

        assert scheduler.settings == test_settings
        assert scheduler.ws_manager == ws_mgr
        assert not scheduler.is_running()

    @pytest.mark.asyncio
    async def test_scheduler_start_stop(self, test_settings: Settings):
        """测试调度器启动和停止"""
        from cortex.probe.scheduler_service import ProbeSchedulerService
        from cortex.probe.websocket_manager import WebSocketManager

        ws_mgr = WebSocketManager()
        scheduler = ProbeSchedulerService(test_settings, ws_mgr)

        # 启动
        await scheduler.start()
        assert scheduler.is_running()

        # 获取状态
        status = scheduler.get_status()
        assert status["scheduler_status"] == "running"

        # 停止
        await scheduler.stop()
        assert not scheduler.is_running()


class TestIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_full_startup_sequence(self, test_settings: Settings):
        """测试完整启动流程"""
        from cortex.probe.scheduler_service import ProbeSchedulerService
        from cortex.probe.websocket_manager import WebSocketManager

        # 1. 创建 WebSocket 管理器
        ws_mgr = WebSocketManager()
        assert ws_mgr.get_connection_count() == 0

        # 2. 创建调度器服务
        scheduler = ProbeSchedulerService(test_settings, ws_mgr)
        assert not scheduler.is_running()

        # 3. 启动调度器
        await scheduler.start()
        assert scheduler.is_running()

        # 4. 获取状态
        status = scheduler.get_status()
        assert status["scheduler_status"] == "running"
        assert "next_inspection" in status

        # 5. 获取调度信息
        schedule_info = scheduler.get_schedule_info()
        assert schedule_info["scheduler_running"]
        assert len(schedule_info["jobs"]) > 0

        # 6. 停止调度器
        await scheduler.stop()
        assert not scheduler.is_running()

    def test_api_endpoints_integration(self, client: TestClient):
        """测试 API 端点集成"""
        # 健康检查
        response = client.get("/health")
        assert response.status_code == 200

        # 状态查询
        response = client.get("/status")
        assert response.status_code == 200

        # 调度信息
        response = client.get("/schedule")
        assert response.status_code == 200

        # 报告列表
        response = client.get("/reports")
        assert response.status_code == 200

        # 暂停
        response = client.post("/schedule/pause")
        assert response.status_code == 200

        # 恢复
        response = client.post("/schedule/resume")
        assert response.status_code == 200
