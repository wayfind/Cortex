"""
Probe CLI 入口
"""

import asyncio
import signal
import sys
from pathlib import Path

from loguru import logger

from cortex.config.settings import get_settings
from cortex.probe.scheduler import ProbeScheduler


def setup_logger() -> None:
    """配置日志"""
    logger.remove()  # 移除默认处理器

    # 添加控制台输出
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO",
    )

    # 添加文件输出
    log_file = Path("logs/probe.log")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_file,
        rotation="1 day",
        retention="30 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )


async def run_probe_service() -> None:
    """运行 Probe 服务"""
    # 加载配置
    try:
        settings = get_settings()
    except Exception as e:
        logger.error(f"Failed to load settings: {e}")
        sys.exit(1)

    # 创建调度器
    scheduler = ProbeScheduler(settings)

    # 设置信号处理
    shutdown_event = asyncio.Event()

    def signal_handler(signum: int, frame: any) -> None:
        logger.warning(f"Received signal {signum}, shutting down...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 启动调度器
    try:
        await scheduler.start()

        # 等待关闭信号
        logger.info("Probe service is running. Press Ctrl+C to stop.")
        await shutdown_event.wait()

    except Exception as e:
        logger.error(f"Error in probe service: {e}", exc_info=True)

    finally:
        # 停止调度器
        await scheduler.stop()
        logger.info("Probe service stopped")


def main() -> None:
    """主入口函数"""
    setup_logger()

    logger.info("Starting Cortex Probe...")
    logger.info(f"Python version: {sys.version}")

    try:
        asyncio.run(run_probe_service())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, exiting...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
