"""
测试配置加载和验证

专注于测试 config.yaml 的加载和 Pydantic 验证
"""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from cortex.config.settings import (
    AgentConfig,
    ClaudeConfig,
    MonitorConfig,
    ProbeConfig,
    Settings,
    TelegramConfig,
    IntentEngineConfig,
    LoggingConfig,
)


class TestProbeConfigLoading:
    """测试 ProbeConfig 加载的各种情况"""

    def test_load_flat_structure_from_dict(self):
        """测试从扁平字典加载配置"""
        config_dict = {
            "schedule": "*/10 * * * *",
            "timeout_seconds": 600,
            "check_system_health": True,
            "check_service_status": False,
            "check_log_analysis": True,
            "check_network": False,
            "threshold_cpu_percent": 75.0,
            "threshold_memory_percent": 80.0,
            "threshold_disk_percent": 85.0,
        }

        config = ProbeConfig(**config_dict)

        assert config.threshold_cpu_percent == 75.0
        assert config.threshold_memory_percent == 80.0
        assert config.threshold_disk_percent == 85.0
        assert config.check_service_status is False

    def test_reject_nested_thresholds(self):
        """测试拒绝嵌套的 thresholds 结构"""
        config_dict = {
            "schedule": "*/5 * * * *",
            "timeout_seconds": 300,
            "thresholds": {  # 这应该被拒绝
                "cpu_percent": 80.0,
                "memory_percent": 85.0,
            },
        }

        with pytest.raises(Exception):  # Pydantic ValidationError
            ProbeConfig(**config_dict)

    def test_reject_nested_checks(self):
        """测试拒绝嵌套的 checks 结构"""
        config_dict = {
            "schedule": "*/5 * * * *",
            "timeout_seconds": 300,
            "checks": {  # 这应该被拒绝
                "system_health": True,
                "service_status": False,
            },
        }

        with pytest.raises(Exception):  # Pydantic ValidationError
            ProbeConfig(**config_dict)

    def test_default_values(self):
        """测试默认值"""
        config = ProbeConfig()

        assert config.schedule == "0 * * * *"
        assert config.timeout_seconds == 300
        assert config.check_system_health is True
        assert config.threshold_cpu_percent == 80.0


class TestClaudeConfigLoading:
    """测试 ClaudeConfig 加载"""

    def test_temperature_field_required(self):
        """测试 temperature 字段存在"""
        config = ClaudeConfig(api_key="test-key")

        assert hasattr(config, "temperature")
        assert config.temperature == 1.0  # 默认值

    def test_custom_temperature(self):
        """测试自定义 temperature 值"""
        config = ClaudeConfig(api_key="test-key", temperature=0.5)

        assert config.temperature == 0.5

    def test_all_fields_from_dict(self):
        """测试从字典加载所有字段"""
        config_dict = {
            "api_key": "sk-test-123",
            "model": "claude-opus-4",
            "max_tokens": 4000,
            "timeout": 60,
            "temperature": 0.7,
        }

        config = ClaudeConfig(**config_dict)

        assert config.api_key == "sk-test-123"
        assert config.model == "claude-opus-4"
        assert config.max_tokens == 4000
        assert config.timeout == 60
        assert config.temperature == 0.7


class TestSettingsFromYAML:
    """测试从 YAML 文件加载完整配置"""

    def test_load_complete_config_from_yaml(self):
        """测试加载完整的 YAML 配置"""
        yaml_content = """
agent:
  id: "test-node-001"
  name: "Test Node"
  mode: "standalone"

probe:
  schedule: "*/5 * * * *"
  timeout_seconds: 300
  check_system_health: true
  check_service_status: true
  check_log_analysis: true
  check_network: true
  threshold_cpu_percent: 80.0
  threshold_memory_percent: 85.0
  threshold_disk_percent: 90.0

monitor:
  host: "0.0.0.0"
  port: 8000
  database_url: "sqlite:///./test.db"
  registration_token: "test-token"

claude:
  api_key: "test-key"
  model: "claude-sonnet-4"
  max_tokens: 2000
  timeout: 30
  temperature: 1.0

telegram:
  enabled: false

intent_engine:
  enabled: true
  database_url: "sqlite:///./test_intents.db"

logging:
  level: "INFO"
  format: "standard"
"""

        # 创建临时 YAML 文件
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            temp_file = f.name

        try:
            # 加载配置
            settings = Settings.from_yaml(temp_file)

            # 验证所有配置正确加载
            assert settings.agent.id == "test-node-001"
            assert settings.probe.threshold_cpu_percent == 80.0
            assert settings.monitor.port == 8000
            assert settings.claude.temperature == 1.0
            assert settings.telegram.enabled is False
            assert settings.intent_engine.enabled is True

        finally:
            # 清理临时文件
            os.unlink(temp_file)

    def test_yaml_with_wrong_probe_structure_fails(self):
        """测试错误的 Probe 结构会失败"""
        yaml_content = """
agent:
  id: "test-node"
  name: "Test"
  mode: "standalone"

probe:
  schedule: "*/5 * * * *"
  timeout_seconds: 300
  thresholds:
    cpu_percent: 80.0
    memory_percent: 85.0

monitor:
  host: "0.0.0.0"
  port: 8000
  database_url: "sqlite:///./test.db"
  registration_token: "test-token"

claude:
  api_key: "test-key"
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            temp_file = f.name

        try:
            with pytest.raises(Exception):  # 应该抛出验证错误
                Settings.from_yaml(temp_file)
        finally:
            os.unlink(temp_file)

    def test_yaml_missing_claude_temperature_uses_default(self):
        """测试 YAML 缺少 temperature 时使用默认值"""
        yaml_content = """
agent:
  id: "test-node"
  name: "Test"
  mode: "standalone"

probe:
  threshold_cpu_percent: 80.0
  threshold_memory_percent: 85.0
  threshold_disk_percent: 90.0

monitor:
  host: "0.0.0.0"
  port: 8000
  database_url: "sqlite:///./test.db"
  registration_token: "test-token"

claude:
  api_key: "test-key"
  # temperature 未指定，应使用默认值 1.0
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            temp_file = f.name

        try:
            settings = Settings.from_yaml(temp_file)
            assert settings.claude.temperature == 1.0  # 默认值
        finally:
            os.unlink(temp_file)


class TestConfigEnvironmentVariables:
    """测试环境变量配置"""

    def test_probe_config_from_env(self, monkeypatch):
        """测试从环境变量加载 ProbeConfig"""
        # 设置环境变量
        monkeypatch.setenv("CORTEX_PROBE_THRESHOLD_CPU_PERCENT", "75.0")
        monkeypatch.setenv("CORTEX_PROBE_THRESHOLD_MEMORY_PERCENT", "80.0")
        monkeypatch.setenv("CORTEX_PROBE_CHECK_SYSTEM_HEALTH", "false")

        config = ProbeConfig()

        assert config.threshold_cpu_percent == 75.0
        assert config.threshold_memory_percent == 80.0
        assert config.check_system_health is False

    def test_claude_config_from_env(self, monkeypatch):
        """测试从环境变量加载 ClaudeConfig"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-test-key")
        monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-4")
        monkeypatch.setenv("ANTHROPIC_TEMPERATURE", "0.5")

        config = ClaudeConfig()

        assert config.api_key == "env-test-key"
        assert config.model == "claude-opus-4"
        assert config.temperature == 0.5


class TestConfigEdgeCases:
    """测试配置边界情况"""

    def test_probe_threshold_boundary_values(self):
        """测试阈值边界值"""
        # 最小值
        config = ProbeConfig(
            threshold_cpu_percent=0.0,
            threshold_memory_percent=0.0,
            threshold_disk_percent=0.0,
        )
        assert config.threshold_cpu_percent == 0.0

        # 最大值
        config = ProbeConfig(
            threshold_cpu_percent=100.0,
            threshold_memory_percent=100.0,
            threshold_disk_percent=100.0,
        )
        assert config.threshold_cpu_percent == 100.0

    def test_claude_temperature_boundary_values(self):
        """测试 temperature 边界值"""
        # 最小值
        config = ClaudeConfig(api_key="test", temperature=0.0)
        assert config.temperature == 0.0

        # 最大值
        config = ClaudeConfig(api_key="test", temperature=1.0)
        assert config.temperature == 1.0

        # 中间值
        config = ClaudeConfig(api_key="test", temperature=0.5)
        assert config.temperature == 0.5

    def test_agent_mode_values(self):
        """测试 Agent mode 的有效值"""
        # standalone
        config = AgentConfig(id="test", name="Test", mode="standalone")
        assert config.mode == "standalone"

        # cluster
        config = AgentConfig(id="test", name="Test", mode="cluster")
        assert config.mode == "cluster"

        # 无效值应该失败
        with pytest.raises(Exception):  # Pydantic ValidationError
            AgentConfig(id="test", name="Test", mode="invalid")
