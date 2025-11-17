"""
测试 Health API
"""

import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
class TestHealthAPI:
    """测试健康检查 API"""

    async def test_health_check_success(self, test_app):
        """测试健康检查端点返回成功"""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    async def test_health_check_response_structure(self, test_app):
        """测试健康检查响应结构"""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()

        # 验证必需字段
        assert "status" in data
        assert "timestamp" in data

        # 验证字段类型
        assert isinstance(data["status"], str)
        assert isinstance(data["timestamp"], str)

        # 验证 timestamp 格式（ISO 8601）
        from datetime import datetime
        datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))  # 应该不抛出异常
