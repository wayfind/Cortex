"""
健康检查路由
"""

from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    """健康检查端点"""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}
