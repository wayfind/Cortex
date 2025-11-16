#!/usr/bin/env python3
"""
手动测试集群功能

测试场景：
1. 注册 3 层节点（L0 → L1 → L2）
2. 查询集群拓扑
3. 验证层级计算正确
"""

import asyncio
import httpx


MONITOR_URL = "http://127.0.0.1:8000"
REGISTRATION_TOKEN = "test-token-for-integration"  # 从 config.yaml 中的值


async def register_agent(agent_id: str, name: str, parent_id: str = None):
    """注册一个 Agent"""
    url = f"{MONITOR_URL}/api/v1/agents"

    payload = {
        "agent_id": agent_id,
        "name": name,
        "api_key": f"key-{agent_id}",
        "registration_token": REGISTRATION_TOKEN,
        "parent_id": parent_id,
        "upstream_monitor_url": f"http://parent-url:8000" if parent_id else None,
        "metadata": {
            "test": True,
            "level": "manual_test"
        }
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
        print(f"\n注册 {agent_id}:")
        print(f"  状态码: {response.status_code}")
        print(f"  响应: {response.json()}")
        return response


async def get_topology():
    """获取集群拓扑"""
    url = f"{MONITOR_URL}/api/v1/cluster/topology"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        print(f"\n集群拓扑:")
        print(f"  状态码: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"\n  节点总数: {len(data['data']['nodes'])}")
            print(f"  层级分布: {data['data']['levels']}")

            print(f"\n  详细节点信息:")
            for node in sorted(data['data']['nodes'], key=lambda x: (x['level'], x['id'])):
                print(f"    - {node['id']}:")
                print(f"        name: {node['name']}")
                print(f"        level: L{node['level']}")
                print(f"        parent_id: {node['parent_id']}")
                print(f"        is_root: {node['is_root']}")
        else:
            print(f"  错误: {response.json()}")

        return response


async def main():
    """主测试流程"""
    print("="*60)
    print("集群模式功能测试")
    print("="*60)

    # 1. 注册 L0 节点（根节点）
    print("\n[步骤 1] 注册根节点 (L0)")
    await register_agent("monitor-root", "Root Monitor", parent_id=None)

    # 2. 注册 L1 节点
    print("\n[步骤 2] 注册 L1 节点")
    await register_agent("monitor-child-1", "Child Monitor 1", parent_id="monitor-root")
    await register_agent("monitor-child-1b", "Child Monitor 1B", parent_id="monitor-root")

    # 3. 注册 L2 节点
    print("\n[步骤 3] 注册 L2 节点")
    await register_agent("monitor-child-2", "Child Monitor 2", parent_id="monitor-child-1")
    await register_agent("monitor-child-2b", "Child Monitor 2B", parent_id="monitor-child-1b")

    # 4. 获取拓扑
    print("\n[步骤 4] 查询集群拓扑")
    await get_topology()

    # 5. 测试无效 parent_id
    print("\n[步骤 5] 测试无效 parent_id（应失败）")
    await register_agent("invalid-node", "Invalid Node", parent_id="non-existent")

    # 6. 测试错误的 token
    print("\n[步骤 6] 测试错误 token（应失败）")
    url = f"{MONITOR_URL}/api/v1/agents"
    payload = {
        "agent_id": "unauthorized-node",
        "name": "Unauthorized",
        "api_key": "key-test",
        "registration_token": "wrong-token",
        "parent_id": None,
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
        print(f"  状态码: {response.status_code}")
        print(f"  响应: {response.json()}")

    print("\n" + "="*60)
    print("测试完成")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
