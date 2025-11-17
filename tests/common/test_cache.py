"""
测试 API 响应缓存
"""

import asyncio
import pytest

from cortex.common.cache import TTLCache, generate_cache_key, get_cache, with_cache


class TestTTLCache:
    """测试 TTL 缓存"""

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        """测试基本的设置和获取"""
        cache = TTLCache(default_ttl=60)

        await cache.set("test_key", "test_value")
        value = await cache.get("test_key")

        assert value == "test_value"

    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self):
        """测试获取不存在的键"""
        cache = TTLCache(default_ttl=60)

        value = await cache.get("nonexistent")

        assert value is None

    @pytest.mark.asyncio
    async def test_ttl_expiration(self):
        """测试 TTL 过期"""
        cache = TTLCache(default_ttl=1)  # 1 秒过期

        await cache.set("expire_key", "expire_value", ttl=1)

        # 立即获取应该成功
        value = await cache.get("expire_key")
        assert value == "expire_value"

        # 等待过期
        await asyncio.sleep(1.1)

        # 过期后应该返回 None
        value = await cache.get("expire_key")
        assert value is None

    @pytest.mark.asyncio
    async def test_delete(self):
        """测试删除缓存"""
        cache = TTLCache(default_ttl=60)

        await cache.set("delete_key", "delete_value")
        await cache.delete("delete_key")

        value = await cache.get("delete_key")
        assert value is None

    @pytest.mark.asyncio
    async def test_clear(self):
        """测试清空所有缓存"""
        cache = TTLCache(default_ttl=60)

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")

        await cache.clear()

        assert await cache.get("key1") is None
        assert await cache.get("key2") is None

    @pytest.mark.asyncio
    async def test_clear_pattern(self):
        """测试按模式清除缓存"""
        cache = TTLCache(default_ttl=60)

        await cache.set("user:1:profile", "user1")
        await cache.set("user:2:profile", "user2")
        await cache.set("post:1:content", "post1")

        # 清除所有 user 相关缓存
        await cache.clear_pattern("user:")

        assert await cache.get("user:1:profile") is None
        assert await cache.get("user:2:profile") is None
        assert await cache.get("post:1:content") == "post1"  # 不受影响

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """测试获取统计信息"""
        cache = TTLCache(default_ttl=60)

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")

        stats = cache.get_stats()

        assert stats["total_items"] == 2
        assert "key1" in stats["items"]
        assert "key2" in stats["items"]


class TestCacheKeyGeneration:
    """测试缓存键生成"""

    def test_generate_cache_key_with_args(self):
        """测试带位置参数的键生成"""
        key1 = generate_cache_key("arg1", "arg2")
        key2 = generate_cache_key("arg1", "arg2")
        key3 = generate_cache_key("arg1", "arg3")

        # 相同参数应生成相同键
        assert key1 == key2
        # 不同参数应生成不同键
        assert key1 != key3

    def test_generate_cache_key_with_kwargs(self):
        """测试带关键字参数的键生成"""
        key1 = generate_cache_key(status="online", limit=10)
        key2 = generate_cache_key(status="online", limit=10)
        key3 = generate_cache_key(status="offline", limit=10)

        assert key1 == key2
        assert key1 != key3

    def test_generate_cache_key_order_independence(self):
        """测试参数顺序独立性"""
        key1 = generate_cache_key(a=1, b=2)
        key2 = generate_cache_key(b=2, a=1)

        # 关键字参数顺序不同但内容相同，应生成相同键
        assert key1 == key2


class TestCacheDecorator:
    """测试缓存装饰器"""

    @pytest.mark.asyncio
    async def test_with_cache_decorator(self):
        """测试缓存装饰器基本功能"""
        call_count = 0

        @with_cache(ttl=60, key_prefix="test")
        async def expensive_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)  # 模拟耗时操作
            return x * 2

        # 第一次调用，应该执行函数
        result1 = await expensive_function(5)
        assert result1 == 10
        assert call_count == 1

        # 第二次调用，应该从缓存获取
        result2 = await expensive_function(5)
        assert result2 == 10
        assert call_count == 1  # 没有再次执行函数

        # 不同参数，应该执行函数
        result3 = await expensive_function(10)
        assert result3 == 20
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_with_cache_ttl(self):
        """测试缓存装饰器的 TTL"""
        call_count = 0

        @with_cache(ttl=1, key_prefix="test")
        async def short_cache_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 3

        # 第一次调用
        result1 = await short_cache_function(7)
        assert result1 == 21
        assert call_count == 1

        # 缓存未过期，应该使用缓存
        result2 = await short_cache_function(7)
        assert result2 == 21
        assert call_count == 1

        # 等待缓存过期
        await asyncio.sleep(1.1)

        # 缓存过期，应该重新执行
        result3 = await short_cache_function(7)
        assert result3 == 21
        assert call_count == 2


class TestGlobalCache:
    """测试全局缓存实例"""

    @pytest.mark.asyncio
    async def test_get_cache_singleton(self):
        """测试全局缓存单例"""
        cache1 = get_cache()
        cache2 = get_cache()

        # 应该返回同一个实例
        assert cache1 is cache2

    @pytest.mark.asyncio
    async def test_global_cache_shared_state(self):
        """测试全局缓存共享状态"""
        cache1 = get_cache()
        cache2 = get_cache()

        await cache1.set("shared_key", "shared_value")

        # 从另一个引用获取应该能访问相同数据
        value = await cache2.get("shared_key")
        assert value == "shared_value"
