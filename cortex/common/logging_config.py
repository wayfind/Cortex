"""
统一的日志配置模块

提供基于 loguru 的日志配置，支持多种输出格式和轮转策略。
"""

import sys
from pathlib import Path
from typing import Optional

from loguru import logger


class LoggingConfig:
    """
    日志配置管理器

    支持：
    - 多种日志级别（DEBUG/INFO/WARNING/ERROR/CRITICAL）
    - 多种输出格式（标准格式/JSON）
    - 文件轮转和清理
    - 模块级别日志配置
    """

    # 标准日志格式
    STANDARD_FORMAT = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    # JSON 日志格式（用于生产环境）
    JSON_FORMAT = (
        "{{"
        '"time": "{time:YYYY-MM-DD HH:mm:ss.SSS}", '
        '"level": "{level}", '
        '"module": "{name}", '
        '"function": "{function}", '
        '"line": {line}, '
        '"message": "{message}"'
        "}}"
    )

    # 简化格式（用于控制台）
    SIMPLE_FORMAT = (
        "<green>{time:HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<level>{message}</level>"
    )

    @classmethod
    def configure(
        cls,
        level: str = "INFO",
        format_type: str = "standard",
        console: bool = True,
        console_level: Optional[str] = None,
        file_path: Optional[str] = None,
        file_level: Optional[str] = None,
        rotation: str = "10 MB",
        retention: str = "30 days",
        compression: str = "zip",
        json_logs: bool = False,
    ):
        """
        配置日志系统

        Args:
            level: 全局日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL)
            format_type: 日志格式类型 (standard/json/simple)
            console: 是否输出到控制台
            console_level: 控制台日志级别（默认使用 level）
            file_path: 日志文件路径
            file_level: 文件日志级别（默认使用 level）
            rotation: 文件轮转策略（如 "10 MB", "1 day"）
            retention: 日志保留时间（如 "30 days", "1 week"）
            compression: 压缩格式（zip/gz）
            json_logs: 是否强制使用 JSON 格式

        Example:
            LoggingConfig.configure(
                level="INFO",
                console=True,
                file_path="logs/cortex.log",
                rotation="10 MB",
                retention="30 days"
            )
        """
        # 移除默认的 handler
        logger.remove()

        # 确定使用的格式
        if json_logs or format_type == "json":
            log_format = cls.JSON_FORMAT
        elif format_type == "simple":
            log_format = cls.SIMPLE_FORMAT
        else:
            log_format = cls.STANDARD_FORMAT

        # 添加控制台输出
        if console:
            console_level = console_level or level
            logger.add(
                sys.stderr,
                format=log_format if format_type != "simple" else cls.SIMPLE_FORMAT,
                level=console_level,
                colorize=True,
            )

        # 添加文件输出
        if file_path:
            file_level = file_level or level
            log_file = Path(file_path)

            # 确保日志目录存在
            log_file.parent.mkdir(parents=True, exist_ok=True)

            logger.add(
                str(log_file),
                format=log_format,
                level=file_level,
                rotation=rotation,
                retention=retention,
                compression=compression,
                enqueue=True,  # 异步写入
            )

        logger.info(f"Logging configured: level={level}, format={format_type}")

    @classmethod
    def configure_for_module(
        cls,
        module_name: str,
        level: str,
        file_path: Optional[str] = None,
    ):
        """
        为特定模块配置日志级别

        Args:
            module_name: 模块名称（如 "cortex.monitor"）
            level: 该模块的日志级别
            file_path: 可选的模块专属日志文件

        Example:
            LoggingConfig.configure_for_module(
                "cortex.monitor",
                "DEBUG",
                "logs/monitor_debug.log"
            )
        """
        if file_path:
            log_file = Path(file_path)
            log_file.parent.mkdir(parents=True, exist_ok=True)

            logger.add(
                str(log_file),
                format=cls.STANDARD_FORMAT,
                level=level,
                filter=lambda record: record["name"].startswith(module_name),
                rotation="10 MB",
                retention="7 days",
                enqueue=True,
            )

        logger.info(f"Module logging configured: {module_name} -> {level}")

    @classmethod
    def set_level(cls, level: str):
        """
        动态调整全局日志级别

        Args:
            level: 新的日志级别

        Example:
            LoggingConfig.set_level("DEBUG")
        """
        # 注意：loguru 不支持直接修改已添加的 handler 的级别
        # 需要重新配置，这里提供一个简化版本
        logger.info(f"Changing log level to {level}")
        logger.level(level)

    @classmethod
    def add_context(cls, **context):
        """
        添加上下文信息到日志

        Args:
            **context: 上下文键值对

        Example:
            LoggingConfig.add_context(agent_id="agent-001", request_id="req-123")
        """
        return logger.contextualize(**context)

    @classmethod
    def configure_from_settings(cls, settings):
        """
        从配置对象加载日志配置

        Args:
            settings: Cortex 配置对象

        Example:
            from cortex.config import get_settings
            settings = get_settings()
            LoggingConfig.configure_from_settings(settings)
        """
        # 检查是否有日志配置
        if not hasattr(settings, "logging"):
            # 使用默认配置
            cls.configure(level="INFO", console=True)
            return

        logging_config = settings.logging

        # 注意：配置中使用 'file' 字段，我们映射到 'file_path'
        cls.configure(
            level=logging_config.level,
            format_type=logging_config.format,
            console=logging_config.console,
            console_level=logging_config.console_level,
            file_path=logging_config.file,
            file_level=logging_config.file_level,
            rotation=logging_config.rotation,
            retention=logging_config.retention,
            compression=logging_config.compression,
            json_logs=(logging_config.format == "json"),
        )

        # 配置模块级别日志
        if logging_config.modules:
            for module_name, module_level in logging_config.modules.items():
                cls.configure_for_module(module_name, module_level)


# 便捷函数
def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    json_logs: bool = False,
):
    """
    快速设置日志

    Args:
        level: 日志级别
        log_file: 日志文件路径
        json_logs: 是否使用 JSON 格式

    Example:
        from cortex.common.logging_config import setup_logging
        setup_logging(level="DEBUG", log_file="logs/app.log")
    """
    LoggingConfig.configure(
        level=level,
        console=True,
        file_path=log_file,
        json_logs=json_logs,
    )


def get_logger(name: str = None):
    """
    获取 logger 实例（兼容性函数）

    Args:
        name: logger 名称（loguru 会自动处理）

    Returns:
        logger 实例

    Example:
        from cortex.common.logging_config import get_logger
        logger = get_logger(__name__)
        logger.info("Hello, world!")
    """
    # loguru 使用单例模式，直接返回
    return logger
