"""
Monitor CLI 入口

启动 Monitor Web 服务（FastAPI + Uvicorn）
"""

import argparse
import os
import sys
from pathlib import Path

import uvicorn
from loguru import logger

from cortex.common.logging_config import LoggingConfig


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="Cortex Monitor Web Service")

    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Host to bind (default: from config or 0.0.0.0)"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to bind (default: from config or 8000)"
    )

    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to config.yaml (default: CORTEX_CONFIG env or config.yaml)"
    )

    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Log level (default: INFO)"
    )

    return parser.parse_args()


def main():
    """主入口函数"""
    args = parse_args()

    # 加载配置
    if args.config:
        os.environ["CORTEX_CONFIG"] = args.config

    # 导入配置以触发加载
    from cortex.config import get_settings
    settings = get_settings()

    # 配置日志（从配置文件或命令行参数）
    if args.log_level:
        # 命令行参数优先
        LoggingConfig.configure(
            level=args.log_level,
            console=True,
            file_path="logs/monitor.log",
            format_type="standard",
        )
    else:
        # 从配置文件加载
        LoggingConfig.configure_from_settings(settings)

    logger.info("Starting Cortex Monitor Web Service...")
    logger.info(f"Python version: {sys.version}")

    if args.config:
        logger.info(f"Using config file: {args.config}")

    # 确定监听地址和端口
    host = args.host or settings.monitor.host
    port = args.port or settings.monitor.port

    logger.info(f"Binding to {host}:{port}")
    logger.info(f"Database: {settings.monitor.database_url}")

    # 启动 Uvicorn 服务器
    uvicorn.run(
        "cortex.monitor.app:app",
        host=host,
        port=port,
        reload=args.reload,
        log_level=args.log_level.lower() if args.log_level else "info",
        access_log=True
    )


if __name__ == "__main__":
    main()
