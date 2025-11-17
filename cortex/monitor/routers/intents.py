"""
意图记录查询路由
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.common.intent_recorder import IntentRecord, IntentRecorder
from cortex.config.settings import get_settings
from cortex.monitor.dependencies import get_db_manager

router = APIRouter()


class IntentResponse(BaseModel):
    """意图记录响应模型"""

    id: int
    timestamp: str
    agent_id: str
    intent_type: str
    level: Optional[str]
    category: str
    description: str
    metadata_json: Optional[str]
    status: Optional[str]

    class Config:
        from_attributes = True


class IntentListResponse(BaseModel):
    """意图列表响应"""

    total: int
    items: List[IntentResponse]
    offset: int
    limit: int


@router.get("/intents", response_model=IntentListResponse)
async def query_intents(
    agent_id: Optional[str] = Query(None, description="筛选特定 Agent"),
    intent_type: Optional[str] = Query(
        None, description="筛选意图类型 (decision/blocker/milestone/note)"
    ),
    level: Optional[str] = Query(None, description="筛选问题级别 (L1/L2/L3)"),
    category: Optional[str] = Query(None, description="筛选操作类别"),
    offset: int = Query(0, ge=0, description="分页偏移量"),
    limit: int = Query(50, ge=1, le=500, description="返回数量限制"),
) -> IntentListResponse:
    """
    查询意图记录

    支持多种过滤条件和分页。
    """
    settings = get_settings()

    if not settings.intent_engine.enabled:
        raise HTTPException(status_code=503, detail="Intent-Engine is disabled")

    # 创建 IntentRecorder 实例
    intent_recorder = IntentRecorder(settings)
    await intent_recorder.initialize()

    try:
        async with intent_recorder.async_session_factory() as session:
            # 构建查询
            query = select(IntentRecord).order_by(IntentRecord.timestamp.desc())

            # 应用过滤条件
            if agent_id:
                query = query.where(IntentRecord.agent_id == agent_id)
            if intent_type:
                query = query.where(IntentRecord.intent_type == intent_type)
            if level:
                query = query.where(IntentRecord.level == level)
            if category:
                query = query.where(IntentRecord.category.like(f"%{category}%"))

            # 获取总数
            from sqlalchemy import func

            count_query = select(func.count()).select_from(query.subquery())
            total_result = await session.execute(count_query)
            total = total_result.scalar() or 0

            # 应用分页
            query = query.offset(offset).limit(limit)

            # 执行查询
            result = await session.execute(query)
            records = result.scalars().all()

            # 转换为响应格式
            items = [
                IntentResponse(
                    id=record.id,
                    timestamp=record.timestamp.isoformat(),
                    agent_id=record.agent_id,
                    intent_type=record.intent_type,
                    level=record.level,
                    category=record.category,
                    description=record.description,
                    metadata_json=record.metadata_json,
                    status=record.status,
                )
                for record in records
            ]

            logger.info(
                f"Queried {len(items)} intents (total: {total}, offset: {offset}, limit: {limit})"
            )

            return IntentListResponse(total=total, items=items, offset=offset, limit=limit)

    except Exception as e:
        logger.error(f"Error querying intents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to query intents: {str(e)}")
    finally:
        await intent_recorder.close()


@router.get("/intents/{intent_id}", response_model=IntentResponse)
async def get_intent(intent_id: int) -> IntentResponse:
    """
    获取单个意图记录详情
    """
    settings = get_settings()

    if not settings.intent_engine.enabled:
        raise HTTPException(status_code=503, detail="Intent-Engine is disabled")

    intent_recorder = IntentRecorder(settings)
    await intent_recorder.initialize()

    try:
        async with intent_recorder.async_session_factory() as session:
            result = await session.execute(select(IntentRecord).where(IntentRecord.id == intent_id))
            record = result.scalar_one_or_none()

            if not record:
                raise HTTPException(status_code=404, detail=f"Intent {intent_id} not found")

            return IntentResponse(
                id=record.id,
                timestamp=record.timestamp.isoformat(),
                agent_id=record.agent_id,
                intent_type=record.intent_type,
                level=record.level,
                category=record.category,
                description=record.description,
                metadata_json=record.metadata_json,
                status=record.status,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting intent {intent_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get intent: {str(e)}")
    finally:
        await intent_recorder.close()


@router.get("/intents/stats/summary")
async def get_intent_stats(
    agent_id: Optional[str] = Query(None, description="筛选特定 Agent"),
    hours: int = Query(24, ge=1, le=168, description="统计时间范围（小时）"),
) -> dict:
    """
    获取意图统计摘要

    返回按类型、级别等维度的统计信息。
    """
    settings = get_settings()

    if not settings.intent_engine.enabled:
        raise HTTPException(status_code=503, detail="Intent-Engine is disabled")

    intent_recorder = IntentRecorder(settings)
    await intent_recorder.initialize()

    try:
        from datetime import datetime, timedelta, timezone

        async with intent_recorder.async_session_factory() as session:
            # 时间过滤
            time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours)

            query = select(IntentRecord).where(IntentRecord.timestamp >= time_threshold)

            if agent_id:
                query = query.where(IntentRecord.agent_id == agent_id)

            result = await session.execute(query)
            records = result.scalars().all()

            # 统计
            by_type = {}
            by_level = {}
            by_agent = {}
            by_category = {}

            for record in records:
                # 按类型统计
                by_type[record.intent_type] = by_type.get(record.intent_type, 0) + 1

                # 按级别统计
                if record.level:
                    by_level[record.level] = by_level.get(record.level, 0) + 1

                # 按 Agent 统计
                by_agent[record.agent_id] = by_agent.get(record.agent_id, 0) + 1

                # 按类别统计
                by_category[record.category] = by_category.get(record.category, 0) + 1

            return {
                "total": len(records),
                "time_range_hours": hours,
                "by_type": by_type,
                "by_level": by_level,
                "by_agent": by_agent,
                "top_categories": sorted(by_category.items(), key=lambda x: x[1], reverse=True)[:10],
            }

    except Exception as e:
        logger.error(f"Error getting intent stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")
    finally:
        await intent_recorder.close()
