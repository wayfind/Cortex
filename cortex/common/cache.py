"""
API 响应缓存工具

提供基于内存的 TTL 缓存，用于缓存 API 响应以提升性能。
"""

import asyncio
import hashlib
import json
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Callable, Optional

from loguru import logger


class TTLCache:
    """
    带过期时间的内存缓存

    每个缓存项包含：
    - value: 缓存的值
    - expires_at: 过期时间
    """

    def __init__(self, default_ttl: int = 60):
        """
        初始化缓存

        Args:
            default_ttl: 默认缓存时间（秒）
        """
        self._cache: dict[str, dict] = {}
        self._default_ttl = default_ttl
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存的值，如果不存在或已过期则返回 None
        """
        async with self._lock:
            if key not in self._cache:
                return None

            item = self._cache[key]

            # 检查是否过期
            if datetime.now(timezone.utc) >= item["expires_at"]:
                # 过期，删除并返回 None
                del self._cache[key]
                logger.debug(f"Cache expired: {key}")
                return None

            logger.debug(f"Cache hit: {key}")
            return item["value"]

    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 要缓存的值
            ttl: 缓存时间（秒），如果为 None 则使用默认值
        """
        if ttl is None:
            ttl = self._default_ttl

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)

        async with self._lock:
            self._cache[key] = {
                "value": value,
                "expires_at": expires_at,
            }
            logger.debug(f"Cache set: {key} (TTL: {ttl}s)")

    async def delete(self, key: str):
        """
        删除缓存项

        Args:
            key: 缓存键
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Cache deleted: {key}")

    async def clear(self):
        """清空所有缓存"""
        async with self._lock:
            self._cache.clear()
            logger.debug("Cache cleared")

    async def clear_pattern(self, pattern: str):
        """
        清除匹配模式的所有缓存项

        Args:
            pattern: 键的前缀或模式
        """
        async with self._lock:
            keys_to_delete = [k for k in self._cache.keys() if pattern in k]
            for key in keys_to_delete:
                del self._cache[key]
            logger.debug(f"Cache cleared for pattern '{pattern}': {len(keys_to_delete)} items")

    def get_stats(self) -> dict:
        """获取缓存统计信息"""
        return {
            "total_items": len(self._cache),
            "items": list(self._cache.keys()),
        }


def generate_cache_key(*args, **kwargs) -> str:
    """
    生成缓存键

    基于参数生成唯一的缓存键。

    Args:
        *args: 位置参数
        **kwargs: 关键字参数

    Returns:
        缓存键（哈希字符串）
    """
    # 将参数转换为可序列化的字符串
    key_data = {
        "args": args,
        "kwargs": sorted(kwargs.items()),  # 排序以确保一致性
    }

    key_string = json.dumps(key_data, sort_keys=True, default=str)

    # 生成 SHA256 哈希
    return hashlib.sha256(key_string.encode()).hexdigest()


# 全局缓存实例
_global_cache: Optional[TTLCache] = None


def get_cache() -> TTLCache:
    """获取全局缓存实例"""
    global _global_cache
    if _global_cache is None:
        _global_cache = TTLCache(default_ttl=60)
    return _global_cache


def with_cache(ttl: int = 60, key_prefix: str = ""):
    """
    缓存装饰器

    用于缓存异步函数的返回值。

    Args:
        ttl: 缓存时间（秒）
        key_prefix: 缓存键前缀（用于区分不同的函数）

    Example:
        @with_cache(ttl=300, key_prefix="agents")
        async def get_all_agents():
            # 复杂的数据库查询
            return agents
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_cache()

            # 生成缓存键
            cache_key = f"{key_prefix}:{func.__name__}:{generate_cache_key(*args, **kwargs)}"

            # 尝试从缓存获取
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # 缓存未命中，执行函数
            result = await func(*args, **kwargs)

            # 存入缓存
            await cache.set(cache_key, result, ttl=ttl)

            return result

        return wrapper

    return decorator


async def invalidate_cache_pattern(pattern: str):
    """
    使匹配模式的缓存失效

    Args:
        pattern: 缓存键模式
    """
    cache = get_cache()
    await cache.clear_pattern(pattern)
