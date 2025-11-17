"""
网络请求重试机制

实现指数退避策略的重试功能
"""

import asyncio
import logging
from typing import Callable, TypeVar, Any
from functools import wraps

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryConfig:
    """重试配置"""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        """
        Args:
            max_attempts: 最大重试次数（包括首次尝试）
            base_delay: 基础延迟时间（秒）
            max_delay: 最大延迟时间（秒）
            exponential_base: 指数退避的基数
            jitter: 是否添加随机抖动（避免惊群效应）
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def get_delay(self, attempt: int) -> float:
        """计算延迟时间（指数退避 + 可选抖动）"""
        import random

        # 指数退避: delay = base_delay * (exponential_base ** attempt)
        delay = min(
            self.base_delay * (self.exponential_base ** (attempt - 1)), self.max_delay
        )

        # 添加随机抖动（0.5 ~ 1.5 倍）
        if self.jitter:
            delay = delay * (0.5 + random.random())

        return delay


# 默认重试配置
DEFAULT_RETRY_CONFIG = RetryConfig(
    max_attempts=3,  # 最多尝试 3 次
    base_delay=1.0,  # 基础延迟 1 秒
    max_delay=30.0,  # 最大延迟 30 秒
    exponential_base=2.0,  # 指数基数 2 (1s, 2s, 4s, ...)
    jitter=True,  # 启用抖动
)


def is_retryable_error(error: Exception) -> bool:
    """判断错误是否可重试"""
    # 网络相关错误
    if isinstance(
        error,
        (
            httpx.ConnectError,
            httpx.TimeoutException,
            httpx.NetworkError,
            httpx.RemoteProtocolError,
        ),
    ):
        return True

    # HTTP 状态码错误
    if isinstance(error, httpx.HTTPStatusError):
        # 5xx 错误可重试
        if 500 <= error.response.status_code < 600:
            return True
        # 429 Too Many Requests 可重试
        if error.response.status_code == 429:
            return True

    return False


async def retry_async(
    func: Callable[..., Any],
    *args,
    config: RetryConfig = DEFAULT_RETRY_CONFIG,
    **kwargs,
) -> T:
    """
    异步函数重试装饰器

    Args:
        func: 要重试的异步函数
        config: 重试配置
        *args, **kwargs: 传递给函数的参数

    Returns:
        函数返回值

    Raises:
        最后一次尝试的异常
    """
    last_exception = None

    for attempt in range(1, config.max_attempts + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e

            # 检查是否可重试
            if not is_retryable_error(e):
                logger.warning(f"Non-retryable error in {func.__name__}: {e}")
                raise

            # 最后一次尝试失败，直接抛出
            if attempt >= config.max_attempts:
                logger.error(
                    f"Failed after {config.max_attempts} attempts in {func.__name__}: {e}"
                )
                raise

            # 计算延迟并等待
            delay = config.get_delay(attempt)
            logger.warning(
                f"Attempt {attempt}/{config.max_attempts} failed in {func.__name__}: {e}. "
                f"Retrying in {delay:.2f}s..."
            )
            await asyncio.sleep(delay)

    # 理论上不会到这里
    if last_exception:
        raise last_exception


def with_retry(config: RetryConfig = DEFAULT_RETRY_CONFIG):
    """
    异步函数重试装饰器（decorator 形式）

    Usage:
        @with_retry(RetryConfig(max_attempts=5))
        async def my_http_request():
            ...
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_async(func, *args, config=config, **kwargs)

        return wrapper

    return decorator


# 预定义的重试配置

# 快速重试（低延迟场景）
FAST_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=0.5,
    max_delay=10.0,
    exponential_base=2.0,
    jitter=True,
)

# 耐心重试（高延迟场景）
PATIENT_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=2.0,
    max_delay=60.0,
    exponential_base=2.0,
    jitter=True,
)

# 关键任务重试（尽最大努力）
CRITICAL_RETRY_CONFIG = RetryConfig(
    max_attempts=10,
    base_delay=1.0,
    max_delay=120.0,
    exponential_base=2.0,
    jitter=True,
)
