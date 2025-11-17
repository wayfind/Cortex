"""
测试网络请求重试机制
"""

import asyncio
import pytest
import httpx

from cortex.common.retry import (
    RetryConfig,
    retry_async,
    is_retryable_error,
    with_retry,
    FAST_RETRY_CONFIG,
)


class TestRetryConfig:
    """测试重试配置"""

    def test_default_config(self):
        """测试默认配置"""
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True

    def test_get_delay_exponential_backoff(self):
        """测试指数退避计算"""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=False)

        # 第 1 次重试: 1.0 * 2^0 = 1.0
        assert config.get_delay(1) == 1.0

        # 第 2 次重试: 1.0 * 2^1 = 2.0
        assert config.get_delay(2) == 2.0

        # 第 3 次重试: 1.0 * 2^2 = 4.0
        assert config.get_delay(3) == 4.0

    def test_get_delay_max_delay(self):
        """测试最大延迟限制"""
        config = RetryConfig(base_delay=10.0, max_delay=20.0, jitter=False)

        # 即使指数计算 > 20，也不超过 max_delay
        delay = config.get_delay(5)
        assert delay <= 20.0

    def test_get_delay_with_jitter(self):
        """测试随机抖动"""
        config = RetryConfig(base_delay=10.0, jitter=True)

        # 抖动范围: 0.5 ~ 1.5 倍
        for _ in range(10):
            delay = config.get_delay(1)
            assert 5.0 <= delay <= 15.0


class TestIsRetryableError:
    """测试错误可重试性判断"""

    def test_retryable_network_errors(self):
        """测试可重试的网络错误"""
        # ConnectError
        assert is_retryable_error(httpx.ConnectError("Connection failed"))

        # TimeoutException
        assert is_retryable_error(httpx.TimeoutException("Timeout"))

        # NetworkError
        assert is_retryable_error(httpx.NetworkError("Network error"))

    def test_retryable_http_status_errors(self):
        """测试可重试的 HTTP 状态码错误"""
        # 创建模拟响应
        request = httpx.Request("GET", "http://example.com")

        # 500 Internal Server Error
        response_500 = httpx.Response(500, request=request)
        assert is_retryable_error(httpx.HTTPStatusError("", request=request, response=response_500))

        # 503 Service Unavailable
        response_503 = httpx.Response(503, request=request)
        assert is_retryable_error(httpx.HTTPStatusError("", request=request, response=response_503))

        # 429 Too Many Requests
        response_429 = httpx.Response(429, request=request)
        assert is_retryable_error(httpx.HTTPStatusError("", request=request, response=response_429))

    def test_non_retryable_http_status_errors(self):
        """测试不可重试的 HTTP 状态码错误"""
        request = httpx.Request("GET", "http://example.com")

        # 400 Bad Request (客户端错误，重试无意义)
        response_400 = httpx.Response(400, request=request)
        assert not is_retryable_error(
            httpx.HTTPStatusError("", request=request, response=response_400)
        )

        # 404 Not Found
        response_404 = httpx.Response(404, request=request)
        assert not is_retryable_error(
            httpx.HTTPStatusError("", request=request, response=response_404)
        )

    def test_non_retryable_generic_errors(self):
        """测试不可重试的通用错误"""
        assert not is_retryable_error(ValueError("Invalid value"))
        assert not is_retryable_error(KeyError("Missing key"))
        assert not is_retryable_error(TypeError("Type error"))


class TestRetryAsync:
    """测试异步重试功能"""

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self):
        """测试首次尝试成功"""
        call_count = 0

        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await retry_async(success_func, config=FAST_RETRY_CONFIG)

        assert result == "success"
        assert call_count == 1  # 只调用一次

    @pytest.mark.asyncio
    async def test_success_after_retries(self):
        """测试重试后成功"""
        call_count = 0

        async def retry_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.ConnectError("Connection failed")
            return "success"

        config = RetryConfig(max_attempts=5, base_delay=0.1, jitter=False)
        result = await retry_async(retry_then_success, config=config)

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_fail_after_max_attempts(self):
        """测试达到最大重试次数后失败"""
        call_count = 0

        async def always_fail():
            nonlocal call_count
            call_count += 1
            raise httpx.TimeoutException("Timeout")

        config = RetryConfig(max_attempts=3, base_delay=0.1, jitter=False)

        with pytest.raises(httpx.TimeoutException):
            await retry_async(always_fail, config=config)

        assert call_count == 3

    @pytest.mark.asyncio
    async def test_non_retryable_error_immediate_failure(self):
        """测试不可重试错误立即失败"""
        call_count = 0

        async def non_retryable_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid value")

        with pytest.raises(ValueError):
            await retry_async(non_retryable_error, config=FAST_RETRY_CONFIG)

        assert call_count == 1  # 不重试，只调用一次


class TestWithRetryDecorator:
    """测试 with_retry 装饰器"""

    @pytest.mark.asyncio
    async def test_decorator_basic(self):
        """测试装饰器基本功能"""
        call_count = 0

        @with_retry(RetryConfig(max_attempts=3, base_delay=0.1))
        async def decorated_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.ConnectError("Failed")
            return "success"

        result = await decorated_func()

        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_decorator_with_args(self):
        """测试装饰器处理函数参数"""

        @with_retry(FAST_RETRY_CONFIG)
        async def func_with_args(x: int, y: int):
            return x + y

        result = await func_with_args(1, 2)
        assert result == 3

        result = await func_with_args(x=10, y=20)
        assert result == 30


class TestIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_realistic_scenario(self):
        """测试真实场景：模拟网络不稳定"""
        call_count = 0
        delays = []

        async def unstable_network_request():
            nonlocal call_count
            call_count += 1

            # 前 2 次失败，第 3 次成功
            if call_count < 3:
                raise httpx.ConnectError("Connection failed")

            return {"status": "ok", "data": "response"}

        config = RetryConfig(max_attempts=5, base_delay=0.1, jitter=False)

        import time

        start = time.time()
        result = await retry_async(unstable_network_request, config=config)
        elapsed = time.time() - start

        # 验证结果
        assert result == {"status": "ok", "data": "response"}
        assert call_count == 3

        # 验证延迟：第 1 次重试 0.1s，第 2 次重试 0.2s
        # 总延迟应该约为 0.3s (允许误差)
        assert 0.2 <= elapsed <= 0.5
