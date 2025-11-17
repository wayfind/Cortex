"""
Cortex 配置管理
"""

import os
import secrets
from typing import Dict, Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentConfig(BaseSettings):
    """Agent 基础配置"""

    id: str = Field("cortex-agent", description="节点唯一标识")
    name: str = Field("Cortex Agent", description="节点名称")
    mode: Literal["standalone", "cluster"] = Field("standalone", description="运行模式")
    upstream_monitor_url: Optional[str] = Field(None, description="上级 Monitor URL")

    model_config = SettingsConfigDict(env_prefix="CORTEX_AGENT_")


class ProbeConfig(BaseSettings):
    """Probe 配置"""

    # Web 服务配置
    host: str = Field("0.0.0.0", description="Web 服务监听地址")
    port: int = Field(8001, description="Web 服务端口")

    # 调度配置
    schedule: str = Field("0 * * * *", description="Cron 调度表达式（默认每小时）")
    timeout_seconds: int = Field(300, description="巡检超时时间（秒）")

    # Claude -p 配置
    workspace: Optional[str] = Field(None, description="probe_workspace 目录路径")

    # 报告配置
    report_retention_days: int = Field(30, description="报告保留天数")

    # 巡检项目开关（旧版兼容，暂保留）
    check_system_health: bool = Field(True, description="系统健康检查")
    check_service_status: bool = Field(True, description="服务状态检查")
    check_log_analysis: bool = Field(True, description="日志分析")
    check_network: bool = Field(True, description="网络连通性检查")

    # 阈值配置
    threshold_cpu_percent: float = Field(80.0, description="CPU 使用率告警阈值")
    threshold_memory_percent: float = Field(85.0, description="内存使用率告警阈值")
    threshold_disk_percent: float = Field(90.0, description="磁盘使用率告警阈值")

    model_config = SettingsConfigDict(env_prefix="CORTEX_PROBE_")


class MonitorConfig(BaseSettings):
    """Monitor 配置"""

    host: str = Field("0.0.0.0", description="监听地址")
    port: int = Field(8000, description="监听端口")
    database_url: str = Field("sqlite:///./cortex.db", description="数据库 URL")
    registration_token: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        description="节点注册密钥（自动生成）"
    )

    model_config = SettingsConfigDict(env_prefix="CORTEX_MONITOR_")


class ClaudeConfig(BaseSettings):
    """Claude API 配置"""

    api_key: Optional[str] = Field(None, description="Claude API Key（运行时必需）")
    model: str = Field("claude-sonnet-4", description="模型名称")
    max_tokens: int = Field(2000, description="最大 token 数")
    timeout: int = Field(30, description="请求超时时间（秒）")
    temperature: float = Field(1.0, description="生成温度（0.0-1.0）")

    model_config = SettingsConfigDict(env_prefix="ANTHROPIC_")


class TelegramConfig(BaseSettings):
    """Telegram 配置"""

    enabled: bool = Field(False, description="是否启用")
    bot_token: Optional[str] = Field(None, description="Bot Token")
    chat_id: Optional[str] = Field(None, description="Chat ID")

    model_config = SettingsConfigDict(env_prefix="TELEGRAM_")


class LoggingConfig(BaseSettings):
    """日志配置"""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        "INFO", description="全局日志级别"
    )
    format: Literal["standard", "json", "simple"] = Field(
        "standard", description="日志格式"
    )
    console: bool = Field(True, description="是否输出到控制台")
    console_level: Optional[str] = Field(None, description="控制台日志级别")
    file: Optional[str] = Field("logs/cortex.log", description="日志文件路径")
    file_level: Optional[str] = Field(None, description="文件日志级别")
    rotation: str = Field("10 MB", description="日志轮转策略")
    retention: str = Field("30 days", description="日志保留时间")
    compression: str = Field("zip", description="压缩格式")
    modules: Dict[str, str] = Field(default_factory=dict, description="模块级别配置")

    model_config = SettingsConfigDict(env_prefix="CORTEX_LOG_")


class IntentEngineConfig(BaseSettings):
    """Intent-Engine 配置"""

    enabled: bool = Field(True, description="是否启用意图记录")
    database_url: str = Field("sqlite:///./cortex_intents.db", description="Intent 数据库 URL")

    model_config = SettingsConfigDict(env_prefix="CORTEX_INTENT_")


class AuthConfig(BaseSettings):
    """认证配置"""

    secret_key: str = Field("your-secret-key-change-in-production", description="JWT 密钥")
    algorithm: str = Field("HS256", description="JWT 算法")
    access_token_expire_minutes: int = Field(30, description="Token 过期时间（分钟）")

    model_config = SettingsConfigDict(env_prefix="CORTEX_AUTH_")


class Settings(BaseSettings):
    """全局配置"""

    agent: AgentConfig
    probe: ProbeConfig
    monitor: MonitorConfig
    claude: ClaudeConfig
    telegram: TelegramConfig = TelegramConfig()
    intent_engine: IntentEngineConfig = IntentEngineConfig()
    logging: LoggingConfig = LoggingConfig()
    auth: AuthConfig = AuthConfig()

    @classmethod
    def from_yaml(cls, config_file: str = "config.yaml") -> "Settings":
        """从 YAML 文件加载配置"""
        import yaml

        if not os.path.exists(config_file):
            raise FileNotFoundError(f"配置文件不存在: {config_file}")

        with open(config_file, "r", encoding="utf-8") as f:
            config_dict = yaml.safe_load(f)

        return cls(
            agent=AgentConfig(**config_dict.get("agent", {})),
            probe=ProbeConfig(**config_dict.get("probe", {})),
            monitor=MonitorConfig(**config_dict.get("monitor", {})),
            claude=ClaudeConfig(**config_dict.get("claude", {})),
            telegram=TelegramConfig(**config_dict.get("telegram", {})),
            intent_engine=IntentEngineConfig(**config_dict.get("intent_engine", {})),
            logging=LoggingConfig(**config_dict.get("logging", {})),
            auth=AuthConfig(**config_dict.get("auth", {})),
        )


# 全局配置实例（延迟初始化）
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """获取全局配置实例"""
    global _settings
    if _settings is None:
        # 优先从环境变量 CORTEX_CONFIG 指定的文件加载
        config_file = os.getenv("CORTEX_CONFIG", "config.yaml")
        try:
            _settings = Settings.from_yaml(config_file)
        except FileNotFoundError:
            # 如果配置文件不存在，使用环境变量
            _settings = Settings(
                agent=AgentConfig(),
                probe=ProbeConfig(),
                monitor=MonitorConfig(),
                claude=ClaudeConfig(),
                telegram=TelegramConfig(),
                intent_engine=IntentEngineConfig(),
                logging=LoggingConfig(),
                auth=AuthConfig(),
            )
    return _settings
