"""
Probe CLI 入口

启动 Probe Web 服务（FastAPI + Uvicorn）
"""

import argparse
import logging
import os
import sys
from pathlib import Path

import uvicorn

logger = logging.getLogger(__name__)


def setup_logging(level: str = "INFO") -> None:
    """配置日志"""
    # 创建日志目录
    log_file = Path("logs/probe.log")
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # 配置日志格式
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stderr),
            logging.FileHandler(log_file)
        ]
    )


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="Cortex Probe Web Service")

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
        help="Port to bind (default: from config or 8001)"
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


def main() -> None:
    """主入口函数"""
    args = parse_args()

    # 配置日志
    setup_logging(args.log_level)

    logger.info("Starting Cortex Probe Web Service...")
    logger.info(f"Python version: {sys.version}")

    # 设置配置文件环境变量
    if args.config:
        os.environ["CORTEX_CONFIG"] = args.config
        logger.info(f"Using config file: {args.config}")

    # 加载配置以获取默认值
    try:
        from cortex.config import get_settings
        settings = get_settings()

        host = args.host or settings.probe.host
        port = args.port or settings.probe.port

        logger.info(f"Binding to {host}:{port}")
        logger.info(f"Workspace: {settings.probe.workspace or 'probe_workspace/'}")
        logger.info(f"Schedule: {settings.probe.schedule}")

    except Exception as e:
        logger.error(f"Failed to load settings: {e}")
        sys.exit(1)

    # 启动 Uvicorn 服务器
    try:
        uvicorn.run(
            "cortex.probe.app:app",
            host=host,
            port=port,
            reload=args.reload,
            log_level=args.log_level.lower(),
            access_log=True
        )

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, exiting...")

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
