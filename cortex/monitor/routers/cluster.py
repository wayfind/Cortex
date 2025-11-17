"""
集群管理路由
"""

from datetime import datetime, timedelta
from typing import AsyncGenerator, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.common.cache import invalidate_cache_pattern, with_cache
from cortex.config.settings import get_settings
from cortex.monitor.dependencies import get_db_manager
from cortex.monitor.database import Agent, Report

router = APIRouter()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话（依赖注入）"""
    async for session in get_db_manager().get_session():
        yield session


class AgentRegistration(BaseModel):
    """Agent 注册请求"""

    agent_id: str
    name: str
    api_key: str
    registration_token: str  # 用于验证注册请求的密钥
    parent_id: Optional[str] = None  # 父节点 Agent ID（集群模式下必填）
    upstream_monitor_url: Optional[str] = None  # 该节点自己的上级 Monitor URL
    metadata: Optional[dict] = None


@router.post("/agents")
async def register_agent(
    agent_reg: AgentRegistration,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    注册新 Agent 或更新已有 Agent

    集群模式下，下级节点通过此 API 注册到上级 Monitor。
    需要提供正确的 registration_token 进行验证。
    """
    try:
        # 1. 验证 registration_token
        settings = get_settings()
        if agent_reg.registration_token != settings.monitor.registration_token:
            logger.warning(f"Invalid registration token from {agent_reg.agent_id}")
            raise HTTPException(status_code=401, detail="Invalid registration token")

        # 2. 检查是否已存在
        result = await session.execute(select(Agent).where(Agent.id == agent_reg.agent_id))
        existing_agent = result.scalar_one_or_none()

        # 3. 验证 parent_id（如果提供）
        if agent_reg.parent_id:
            parent_result = await session.execute(
                select(Agent).where(Agent.id == agent_reg.parent_id)
            )
            parent_agent = parent_result.scalar_one_or_none()
            if not parent_agent:
                raise HTTPException(status_code=404, detail=f"Parent agent not found: {agent_reg.parent_id}")

        if existing_agent:
            # 更新已有 Agent（支持重新注册）
            existing_agent.name = agent_reg.name
            existing_agent.api_key = agent_reg.api_key
            existing_agent.parent_id = agent_reg.parent_id
            existing_agent.upstream_monitor_url = agent_reg.upstream_monitor_url
            existing_agent.metadata_json = agent_reg.metadata
            existing_agent.updated_at = datetime.utcnow()

            await session.commit()

            logger.info(f"Agent updated: {agent_reg.agent_id} ({agent_reg.name})")

            # 清除相关缓存
            await invalidate_cache_pattern("agents:")
            await invalidate_cache_pattern("cluster:")

            return {
                "success": True,
                "data": {
                    "agent_id": existing_agent.id,
                    "name": existing_agent.name,
                    "parent_id": existing_agent.parent_id,
                    "updated_at": existing_agent.updated_at.isoformat(),
                    "action": "updated",
                },
                "message": "Agent updated successfully",
                "timestamp": datetime.utcnow().isoformat(),
            }

        # 4. 创建新 Agent
        new_agent = Agent(
            id=agent_reg.agent_id,
            name=agent_reg.name,
            api_key=agent_reg.api_key,
            parent_id=agent_reg.parent_id,
            upstream_monitor_url=agent_reg.upstream_monitor_url,
            status="offline",
            health_status="unknown",
            metadata_json=agent_reg.metadata,
        )

        session.add(new_agent)
        await session.commit()

        logger.info(f"New agent registered: {agent_reg.agent_id} ({agent_reg.name})")

        # 清除相关缓存
        await invalidate_cache_pattern("agents:")
        await invalidate_cache_pattern("cluster:")

        return {
            "success": True,
            "data": {
                "agent_id": new_agent.id,
                "name": new_agent.name,
                "created_at": new_agent.created_at.isoformat(),
                "action": "created",
            },
            "message": "Agent registered successfully",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering agent: {e}")
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents")
@with_cache(ttl=30, key_prefix="agents:list")
async def list_agents(
    status: Optional[str] = Query(None, description="过滤状态: online/offline"),
    health_status: Optional[str] = Query(None, description="过滤健康状态: healthy/warning/critical"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    列出所有 Agent（带 30 秒缓存）
    """
    try:
        query = select(Agent).order_by(Agent.created_at.desc())

        if status:
            query = query.where(Agent.status == status)
        if health_status:
            query = query.where(Agent.health_status == health_status)

        result = await session.execute(query)
        agents = result.scalars().all()

        return {
            "success": True,
            "data": {
                "agents": [
                    {
                        "id": a.id,
                        "name": a.name,
                        "status": a.status,
                        "health_status": a.health_status,
                        "last_heartbeat": a.last_heartbeat.isoformat() if a.last_heartbeat else None,
                        "created_at": a.created_at.isoformat(),
                    }
                    for a in agents
                ],
                "count": len(agents),
            },
            "message": "Agents retrieved successfully",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error listing agents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/{agent_id}")
@with_cache(ttl=30, key_prefix="agents:detail")
async def get_agent(
    agent_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    获取单个 Agent 详情（带 30 秒缓存）
    """
    try:
        result = await session.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one_or_none()

        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        # 查询最近的报告统计
        reports_count_result = await session.execute(
            select(func.count(Report.id)).where(Report.agent_id == agent_id)
        )
        total_reports = reports_count_result.scalar() or 0

        # 查询最近 24 小时的报告数
        last_24h = datetime.utcnow() - timedelta(hours=24)
        recent_reports_result = await session.execute(
            select(func.count(Report.id)).where(
                Report.agent_id == agent_id, Report.timestamp >= last_24h
            )
        )
        recent_reports = recent_reports_result.scalar() or 0

        return {
            "success": True,
            "data": {
                "id": agent.id,
                "name": agent.name,
                "status": agent.status,
                "health_status": agent.health_status,
                "upstream_monitor_url": agent.upstream_monitor_url,
                "last_heartbeat": agent.last_heartbeat.isoformat() if agent.last_heartbeat else None,
                "created_at": agent.created_at.isoformat(),
                "updated_at": agent.updated_at.isoformat(),
                "metadata": agent.metadata_json,
                "statistics": {
                    "total_reports": total_reports,
                    "reports_last_24h": recent_reports,
                },
            },
            "message": "Agent retrieved successfully",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/agents/{agent_id}")
async def delete_agent(
    agent_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    删除 Agent（需要管理员权限）
    """
    try:
        result = await session.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one_or_none()

        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        await session.delete(agent)
        await session.commit()

        logger.warning(f"Agent deleted: {agent_id}")

        # 清除相关缓存
        await invalidate_cache_pattern("agents:")
        await invalidate_cache_pattern("cluster:")

        return {
            "success": True,
            "data": {"agent_id": agent_id},
            "message": "Agent deleted successfully",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting agent {agent_id}: {e}")
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


class HeartbeatRequest(BaseModel):
    """心跳请求"""

    health_status: Optional[str] = None  # healthy/warning/critical


@router.post("/agents/{agent_id}/heartbeat")
async def agent_heartbeat(
    agent_id: str,
    heartbeat: HeartbeatRequest = HeartbeatRequest(),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    接收 Agent 心跳

    Agent 应定期调用此 API 报告存活状态（建议每 1-2 分钟）。
    如果 5 分钟内未收到心跳，Monitor 将标记该 Agent 为 offline。
    """
    try:
        result = await session.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one_or_none()

        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        # 更新心跳时间和状态
        agent.last_heartbeat = datetime.utcnow()
        agent.status = "online"

        # 如果提供了健康状态，也更新
        if heartbeat.health_status:
            agent.health_status = heartbeat.health_status

        await session.commit()

        logger.debug(f"Heartbeat received from {agent_id}")

        # 清除相关缓存（heartbeat 频繁，只清除必要的缓存）
        await invalidate_cache_pattern(f"agents:detail:{agent_id}")
        await invalidate_cache_pattern("agents:list")
        await invalidate_cache_pattern("cluster:overview")

        return {
            "success": True,
            "data": {
                "agent_id": agent_id,
                "status": agent.status,
                "health_status": agent.health_status,
                "last_heartbeat": agent.last_heartbeat.isoformat(),
            },
            "message": "Heartbeat recorded",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing heartbeat from {agent_id}: {e}")
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cluster/overview")
@with_cache(ttl=30, key_prefix="cluster:overview")
async def cluster_overview(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    集群全局概览（带 30 秒缓存）
    """
    try:
        # 统计 Agent 数量
        total_agents_result = await session.execute(select(func.count(Agent.id)))
        total_agents = total_agents_result.scalar() or 0

        online_agents_result = await session.execute(
            select(func.count(Agent.id)).where(Agent.status == "online")
        )
        online_agents = online_agents_result.scalar() or 0

        # 统计健康状态分布
        healthy_result = await session.execute(
            select(func.count(Agent.id)).where(Agent.health_status == "healthy")
        )
        healthy_count = healthy_result.scalar() or 0

        warning_result = await session.execute(
            select(func.count(Agent.id)).where(Agent.health_status == "warning")
        )
        warning_count = warning_result.scalar() or 0

        critical_result = await session.execute(
            select(func.count(Agent.id)).where(Agent.health_status == "critical")
        )
        critical_count = critical_result.scalar() or 0

        # 统计最近 1 小时的报告数
        last_hour = datetime.utcnow() - timedelta(hours=1)
        recent_reports_result = await session.execute(
            select(func.count(Report.id)).where(Report.timestamp >= last_hour)
        )
        recent_reports = recent_reports_result.scalar() or 0

        return {
            "success": True,
            "data": {
                "agents": {
                    "total": total_agents,
                    "online": online_agents,
                    "offline": total_agents - online_agents,
                },
                "health": {
                    "healthy": healthy_count,
                    "warning": warning_count,
                    "critical": critical_count,
                    "unknown": total_agents - healthy_count - warning_count - critical_count,
                },
                "activity": {
                    "reports_last_hour": recent_reports,
                },
            },
            "message": "Cluster overview retrieved successfully",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting cluster overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cluster/topology")
@with_cache(ttl=60, key_prefix="cluster:topology")
async def cluster_topology(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    获取集群拓扑结构（带 60 秒缓存）

    返回所有节点的层级关系，构建完整的集群拓扑树。
    层级定义：
    - L0: 根节点（没有 upstream_monitor_url）
    - L1: 直接连接到 L0 的节点
    - L2: 连接到 L1 的节点
    - ...依此类推
    """
    try:
        # 获取所有 Agent
        result = await session.execute(select(Agent).order_by(Agent.id))
        all_agents = result.scalars().all()

        # 构建节点字典
        agents_dict = {agent.id: agent for agent in all_agents}

        # 计算每个节点的层级
        def calculate_level(agent_id: str, visited: set = None) -> int:
            """递归计算节点层级"""
            if visited is None:
                visited = set()

            if agent_id in visited:
                # 检测到循环，返回 -1 表示错误
                logger.warning(f"Circular dependency detected in cluster topology for agent: {agent_id}")
                return -1

            visited.add(agent_id)
            agent = agents_dict.get(agent_id)

            if not agent:
                return -1

            # 如果没有 parent_id，说明是根节点（L0）
            if not agent.parent_id:
                return 0

            # 递归计算父节点的层级
            parent_level = calculate_level(agent.parent_id, visited)

            if parent_level == -1:
                # 父节点有问题
                return -1

            # 当前节点层级 = 父节点层级 + 1
            return parent_level + 1

        # 构建拓扑树
        topology = {
            "nodes": [],
            "levels": {},
        }

        for agent in all_agents:
            level = calculate_level(agent.id)

            node_info = {
                "id": agent.id,
                "name": agent.name,
                "status": agent.status,
                "health_status": agent.health_status,
                "parent_id": agent.parent_id,
                "upstream_monitor_url": agent.upstream_monitor_url,
                "level": level,
                "is_root": agent.parent_id is None,
                "last_heartbeat": agent.last_heartbeat.isoformat() if agent.last_heartbeat else None,
            }

            topology["nodes"].append(node_info)

            # 按层级分组
            level_key = f"L{level}" if level >= 0 else "unknown"
            if level_key not in topology["levels"]:
                topology["levels"][level_key] = []
            topology["levels"][level_key].append(agent.id)

        return {
            "success": True,
            "data": topology,
            "message": "Cluster topology retrieved successfully",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting cluster topology: {e}")
        raise HTTPException(status_code=500, detail=str(e))
