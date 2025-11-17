# API 响应缓存策略

本文档说明 Cortex Monitor API 的缓存实现和策略。

## 概述

Cortex Monitor 使用基于内存的 TTL（Time-To-Live）缓存来优化 API 响应性能，减少数据库查询压力。

**实现位置**：`cortex/common/cache.py`

## 缓存架构

### 1. 核心组件

#### TTLCache 类
- **功能**：带过期时间的内存缓存
- **特性**：
  - 支持自定义 TTL
  - 自动过期清理
  - 线程安全（使用 asyncio.Lock）
  - 模式匹配清除

#### @with_cache 装饰器
- **功能**：简化缓存应用
- **用法**：
  ```python
  @with_cache(ttl=60, key_prefix="my_function")
  async def my_expensive_function(arg1, arg2):
      # 复杂查询...
      return result
  ```

#### invalidate_cache_pattern 函数
- **功能**：按模式清除缓存
- **用途**：写操作后使相关缓存失效

### 2. 缓存键生成

缓存键由以下部分组成：
```
{key_prefix}:{function_name}:{hash(args+kwargs)}
```

示例：
- `agents:list:a1b2c3d4...` - list_agents 函数的缓存
- `cluster:overview:e5f6g7h8...` - cluster_overview 函数的缓存

## 已缓存端点

### 1. Agent 相关端点

#### GET /api/v1/agents
- **TTL**: 30 秒
- **键前缀**: `agents:list`
- **原因**: 频繁访问的列表查询
- **缓存键变量**: status, health_status 参数

#### GET /api/v1/agents/{agent_id}
- **TTL**: 30 秒
- **键前缀**: `agents:detail`
- **原因**: 单个 Agent 详情查询
- **缓存键变量**: agent_id

### 2. 集群相关端点

#### GET /api/v1/cluster/overview
- **TTL**: 30 秒
- **键前缀**: `cluster:overview`
- **原因**: 聚合统计查询，计算成本高
- **优化效果**: 减少 6+ 次数据库查询

#### GET /api/v1/cluster/topology
- **TTL**: 60 秒
- **键前缀**: `cluster:topology`
- **原因**: 拓扑结构变化较慢，计算复杂
- **优化效果**: 减少递归层级计算

## 缓存失效策略

### 自动失效规则

| 操作端点 | 失效的缓存模式 | 原因 |
|---------|--------------|------|
| `POST /api/v1/agents` | `agents:*`, `cluster:*` | Agent 注册/更新影响列表和集群统计 |
| `DELETE /api/v1/agents/{id}` | `agents:*`, `cluster:*` | Agent 删除影响所有 Agent 相关数据 |
| `POST /api/v1/agents/{id}/heartbeat` | `agents:detail:{id}`, `agents:list`, `cluster:overview` | 心跳更新状态，影响特定 Agent 和概览 |
| `POST /api/v1/reports` | `cluster:overview` | 报告上传影响活动统计 |

### 手动失效

如需手动清除缓存，使用：
```python
from cortex.common.cache import invalidate_cache_pattern

# 清除所有 Agent 相关缓存
await invalidate_cache_pattern("agents:")

# 清除特定 Agent 缓存
await invalidate_cache_pattern(f"agents:detail:{agent_id}")
```

## 性能优化效果

### 预期性能提升

| 端点 | 无缓存 | 有缓存 | 提升 |
|------|--------|--------|------|
| `/agents` (100 agents) | ~50ms | ~2ms | **25x** |
| `/cluster/overview` | ~80ms | ~2ms | **40x** |
| `/cluster/topology` (50 nodes) | ~150ms | ~3ms | **50x** |
| `/agents/{id}` | ~30ms | ~2ms | **15x** |

### 数据库查询减少

- **集群概览**：从 6-8 次查询减少到 0 次（缓存命中）
- **拓扑结构**：从 N 次递归查询减少到 0 次
- **Agent 列表**：从 1 次大查询减少到 0 次

## 缓存监控

### 获取缓存统计

```python
from cortex.common.cache import get_cache

cache = get_cache()
stats = cache.get_stats()

# 返回示例：
# {
#     "total_items": 12,
#     "items": [
#         "agents:list:abc123...",
#         "cluster:overview:def456...",
#         ...
#     ]
# }
```

### 日志记录

缓存操作会记录 DEBUG 级别日志：
```
Cache hit: agents:list:abc123...
Cache set: cluster:overview:def456... (TTL: 30s)
Cache expired: agents:detail:xyz789...
Cache cleared for pattern 'agents:': 5 items
```

## 缓存配置

### 默认 TTL 值

当前默认值设置在 `get_cache()` 函数中：
```python
_global_cache = TTLCache(default_ttl=60)  # 60 秒
```

### 调整 TTL

可以针对不同端点设置不同的 TTL：

```python
# 快速变化的数据 - 较短 TTL
@with_cache(ttl=10, key_prefix="realtime")
async def get_realtime_metrics():
    ...

# 慢变化的数据 - 较长 TTL
@with_cache(ttl=300, key_prefix="configuration")
async def get_configuration():
    ...
```

## 最佳实践

### ✅ 适合缓存的场景

1. **读密集型端点** - 查询>>写入的 API
2. **计算成本高** - 涉及聚合、递归、多表连接
3. **数据变化慢** - 配置、拓扑、统计数据
4. **可容忍延迟** - 允许短暂的数据不一致

### ❌ 不适合缓存的场景

1. **实时性要求高** - 需要最新数据（如交易、告警）
2. **写多读少** - 缓存命中率低
3. **用户特定数据** - 每个用户数据不同（除非用户 ID 在键中）
4. **安全敏感数据** - 避免在内存中长期保存敏感信息

### 🎯 缓存使用建议

1. **合理设置 TTL**：
   - 快速变化：10-30 秒
   - 中等变化：30-60 秒
   - 慢速变化：60-300 秒

2. **及时失效**：
   - 写操作后立即清除相关缓存
   - 使用模式匹配批量清除

3. **监控命中率**：
   - 定期检查缓存统计
   - 调整 TTL 和缓存策略

4. **避免缓存雪崩**：
   - 使用随机 jitter
   - 错开不同端点的 TTL

## 未来优化方向

1. **分布式缓存**：
   - 使用 Redis 支持多实例部署
   - 跨节点缓存共享

2. **智能失效**：
   - 基于数据关联的精准失效
   - 预测性缓存刷新

3. **缓存预热**：
   - 启动时预加载热数据
   - 定时任务维护常用缓存

4. **缓存分层**：
   - L1: 内存缓存（当前实现）
   - L2: Redis 缓存
   - L3: CDN 缓存（静态资源）

## 参考资料

- [缓存实现代码](../cortex/common/cache.py)
- [缓存测试用例](../tests/common/test_cache.py)
- [数据库优化文档](./DATABASE_OPTIMIZATION.md)
