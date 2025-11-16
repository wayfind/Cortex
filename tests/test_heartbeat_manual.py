#!/usr/bin/env python3
"""
手动测试心跳检测功能

测试场景：
1. 注册 3 个 Agent
2. 只为其中 2 个发送心跳
3. 等待 6 分钟后检查状态
4. 验证未发送心跳的 Agent 被标记为 offline
"""

import asyncio
import httpx
from datetime import datetime


MONITOR_URL = "http://127.0.0.1:8000"
REGISTRATION_TOKEN = "test-token-for-integration"


async def register_agent(agent_id: str, name: str):
    """注册一个 Agent"""
    url = f"{MONITOR_URL}/api/v1/agents"

    payload = {
        "agent_id": agent_id,
        "name": name,
        "api_key": f"key-{agent_id}",
        "registration_token": REGISTRATION_TOKEN,
        "parent_id": None,
        "metadata": {"test": True},
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
        print(f"注册 {agent_id}: {response.status_code}")
        return response


async def send_heartbeat(agent_id: str, health_status: str = None):
    """发送心跳"""
    url = f"{MONITOR_URL}/api/v1/agents/{agent_id}/heartbeat"

    payload = {}
    if health_status:
        payload["health_status"] = health_status

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
        if response.status_code == 200:
            data = response.json()
            print(f"  ✓ 心跳已记录: {data['data']['last_heartbeat']}")
        else:
            print(f"  ✗ 心跳失败: {response.status_code} - {response.text}")
        return response


async def list_agents():
    """列出所有 Agent"""
    url = f"{MONITOR_URL}/api/v1/agents"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        if response.status_code == 200:
            data = response.json()
            print(f"\n当前 Agent 状态:")
            for agent in data["data"]["agents"]:
                print(f"  - {agent['id']}:")
                print(f"      状态: {agent['status']}")
                print(f"      健康: {agent['health_status']}")
                print(f"      心跳: {agent['last_heartbeat']}")
        return response


async def main():
    """主测试流程"""
    print("=" * 60)
    print("心跳检测功能测试")
    print("=" * 60)

    # 1. 注册 3 个 Agent
    print("\n[步骤 1] 注册 3 个 Agent")
    await register_agent("heartbeat-test-1", "Test Agent 1")
    await register_agent("heartbeat-test-2", "Test Agent 2")
    await register_agent("heartbeat-test-3", "Test Agent 3")

    # 2. 为前 2 个 Agent 发送心跳
    print("\n[步骤 2] 为 Agent 1 和 2 发送心跳")
    print("Agent 1:")
    await send_heartbeat("heartbeat-test-1", "healthy")
    print("Agent 2:")
    await send_heartbeat("heartbeat-test-2", "healthy")
    print("Agent 3: (不发送心跳)")

    # 3. 立即检查状态
    await list_agents()

    # 4. 持续发送心跳（Agent 1 和 2）
    print("\n[步骤 3] 持续为 Agent 1 和 2 发送心跳（每 30 秒），持续 2 分钟")
    print("Agent 3 不发送心跳，应在 5 分钟后被标记为 offline")

    for i in range(4):  # 4 次 × 30 秒 = 2 分钟
        await asyncio.sleep(30)
        print(f"\n--- {(i+1)*30} 秒后 ---")
        print("Agent 1:")
        await send_heartbeat("heartbeat-test-1")
        print("Agent 2:")
        await send_heartbeat("heartbeat-test-2")
        await list_agents()

    # 5. 等待额外 4 分钟让 Agent 3 超时
    print("\n[步骤 4] 停止发送心跳，等待 4 分钟...")
    print("(Agent 3 注册后已经 6 分钟，应被标记为 offline)")

    for i in range(4):  # 4 次 × 60 秒 = 4 分钟
        await asyncio.sleep(60)
        print(f"\n--- 已等待 {i+1} 分钟 ---")
        await list_agents()

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
    print("\n预期结果:")
    print("  - Agent 1 和 2: status = 'offline' (6 分钟没发送心跳)")
    print("  - Agent 3: status = 'offline' (从未发送心跳)")


async def quick_test():
    """快速测试（用于验证 API 可用性）"""
    print("=" * 60)
    print("快速测试 - 验证心跳 API")
    print("=" * 60)

    # 注册 Agent
    print("\n[1] 注册 Agent")
    await register_agent("quick-test-1", "Quick Test Agent")

    # 发送心跳
    print("\n[2] 发送心跳")
    await send_heartbeat("quick-test-1", "healthy")

    # 检查状态
    print("\n[3] 检查状态")
    await list_agents()

    print("\n快速测试完成!")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "quick":
        asyncio.run(quick_test())
    else:
        asyncio.run(main())
