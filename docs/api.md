# Cortex API 接口文档

## 概述

本文档定义 Cortex 系统的所有 HTTP API 接口规范，包括：

- **Probe → Monitor**：节点上报接口
- **Monitor API**：集群管理、决策、告警接口
- **Web UI API**：前端数据查询接口
- **认证接口**：用户登录和权限管理

**基础信息**：
- **协议**：HTTP/HTTPS
- **数据格式**：JSON
- **字符编码**：UTF-8
- **API 版本**：v1
- **Base URL**：`http(s)://{monitor_host}:{port}/api/v1`

---

## 目录

1. [认证机制](#认证机制)
2. [统一响应格式](#统一响应格式)
3. [错误代码](#错误代码)
4. [数据上报接口](#数据上报接口)
5. [决策管理接口](#决策管理接口)
6. [集群管理接口](#集群管理接口)
7. [告警管理接口](#告警管理接口)
8. [意图查询接口](#意图查询接口)
9. [认证授权接口](#认证授权接口)
10. [WebSocket 实时通信](#websocket-实时通信)

---

## 认证机制

### Agent 认证（API Key）

**用于**：Probe → Monitor 通信

**方式**：HTTP Header

```http
X-API-Key: your-api-key-here
```

**获取方式**：节点注册时由 Monitor 生成并返回

### Web UI 认证（JWT Token）

**用于**：Web UI → Monitor 通信

**方式**：HTTP Header

```http
Authorization: Bearer {jwt_token}
```

**获取方式**：用户登录后获取

---

## 统一响应格式

### 成功响应

```json
{
  "success": true,
  "data": { ... },
  "message": "操作成功",
  "timestamp": "2025-11-16T10:00:00Z"
}
```

### 错误响应

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "错误描述",
    "details": { ... }
  },
  "timestamp": "2025-11-16T10:00:00Z"
}
```

---

## 错误代码

| 错误代码 | HTTP 状态码 | 说明 |
|---------|-----------|------|
| `INVALID_REQUEST` | 400 | 请求参数无效 |
| `UNAUTHORIZED` | 401 | 未认证或认证失败 |
| `FORBIDDEN` | 403 | 无权限访问 |
| `NOT_FOUND` | 404 | 资源不存在 |
| `CONFLICT` | 409 | 资源冲突 |
| `INTERNAL_ERROR` | 500 | 服务器内部错误 |
| `SERVICE_UNAVAILABLE` | 503 | 服务暂时不可用 |

---

## 数据上报接口

### 1. 上报节点数据

**端点**：`POST /reports`

**用途**：Probe 向 Monitor 上报巡检数据

**认证**：API Key

**请求体**：

```json
{
  "agent_id": "node-prod-001",
  "timestamp": "2025-11-16T10:00:00Z",
  "status": "warning",
  "metrics": {
    "cpu_percent": 45.2,
    "memory_percent": 62.1,
    "disk_percent": 92.5,
    "load_average": [1.2, 1.5, 1.8],
    "uptime_seconds": 864000,
    "process_count": 156,
    "disk_io": {
      "read_bytes": 1024000,
      "write_bytes": 512000
    },
    "network_io": {
      "bytes_sent": 2048000,
      "bytes_recv": 4096000
    }
  },
  "issues": [
    {
      "level": "L1",
      "type": "disk_space_low",
      "description": "磁盘使用率 92.5%，接近告警阈值",
      "severity": "medium",
      "details": {
        "partition": "/",
        "used_gb": 185,
        "total_gb": 200
      },
      "timestamp": "2025-11-16T10:00:05Z"
    },
    {
      "level": "L2",
      "type": "service_down",
      "description": "nginx 服务意外停止",
      "severity": "high",
      "proposed_fix": "systemctl restart nginx",
      "risk_assessment": "中风险：重启 nginx 会短暂中断 Web 服务（约 2-3 秒），但可恢复服务。建议批准。",
      "details": {
        "service": "nginx",
        "last_active": "2025-11-16T09:45:00Z",
        "exit_code": 1
      },
      "timestamp": "2025-11-16T10:00:10Z"
    }
  ],
  "actions_taken": [
    {
      "level": "L1",
      "action": "cleaned_disk_space",
      "result": "success",
      "details": "Cleaned /tmp and old logs, freed 5.2GB",
      "timestamp": "2025-11-16T10:00:15Z",
      "intent_id": 1234
    }
  ],
  "metadata": {
    "probe_version": "1.0.0",
    "execution_time_seconds": 18.5,
    "llm_model": "claude-sonnet-4"
  }
}
```

**响应**：

```json
{
  "success": true,
  "data": {
    "report_id": 12345,
    "l2_decisions": [
      {
        "decision_id": 678,
        "issue_type": "service_down",
        "status": "approved",
        "reason": "低风险，批准执行"
      }
    ],
    "l3_alerts_triggered": 0
  },
  "message": "报告已接收并处理",
  "timestamp": "2025-11-16T10:00:20Z"
}
```

---

### 2. 发送心跳

**端点**：`POST /heartbeat`

**用途**：节点发送轻量级心跳，更新在线状态

**认证**：API Key

**请求体**：

```json
{
  "agent_id": "node-prod-001",
  "timestamp": "2025-11-16T10:00:00Z",
  "status": "healthy"
}
```

**响应**：

```json
{
  "success": true,
  "data": {
    "received_at": "2025-11-16T10:00:00Z"
  },
  "message": "心跳已接收",
  "timestamp": "2025-11-16T10:00:00Z"
}
```

---

## 决策管理接口

### 3. 请求 L2 决策

**端点**：`POST /decisions/request`

**用途**：下级节点请求上级 Monitor 进行 L2 决策

**认证**：API Key

**请求体**：

```json
{
  "agent_id": "node-prod-001",
  "issue": {
    "type": "service_down",
    "description": "nginx 服务意外停止",
    "severity": "high",
    "proposed_fix": "systemctl restart nginx",
    "risk_assessment": "中风险：重启 nginx 会短暂中断 Web 服务",
    "details": {
      "service": "nginx",
      "last_active": "2025-11-16T09:45:00Z"
    }
  },
  "context": {
    "recent_events": ["上次重启：3天前", "最近无异常日志"],
    "current_load": "低负载"
  }
}
```

**响应**：

```json
{
  "success": true,
  "data": {
    "decision_id": 678,
    "status": "approved",
    "reason": "风险评估：低风险。nginx 重启通常安全，建议批准。",
    "llm_analysis": "根据系统当前状态和历史记录，nginx 服务重启风险较低。上次重启在 3 天前且成功，最近无异常日志。建议批准此操作。",
    "created_at": "2025-11-16T10:00:25Z"
  },
  "message": "决策已完成",
  "timestamp": "2025-11-16T10:00:25Z"
}
```

**可能的 status 值**：
- `approved`：批准执行
- `rejected`：拒绝执行

---

### 4. 查询决策结果

**端点**：`GET /decisions/{decision_id}`

**用途**：查询指定决策的详细信息

**认证**：API Key 或 JWT

**响应**：

```json
{
  "success": true,
  "data": {
    "decision_id": 678,
    "agent_id": "node-prod-001",
    "issue_type": "service_down",
    "issue_description": "nginx 服务意外停止",
    "proposed_action": "systemctl restart nginx",
    "llm_analysis": "风险评估：低风险...",
    "status": "approved",
    "reason": "低风险，批准执行",
    "created_at": "2025-11-16T10:00:25Z",
    "executed_at": "2025-11-16T10:00:30Z",
    "execution_result": "success"
  },
  "timestamp": "2025-11-16T10:01:00Z"
}
```

---

### 5. 查询决策历史

**端点**：`GET /decisions`

**用途**：查询决策历史列表（支持筛选）

**认证**：JWT

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `agent_id` | string | 否 | 按节点 ID 筛选 |
| `status` | string | 否 | 按状态筛选（approved/rejected） |
| `limit` | integer | 否 | 返回数量限制（默认 50） |
| `offset` | integer | 否 | 分页偏移量（默认 0） |

**示例**：`GET /decisions?agent_id=node-prod-001&limit=20`

**响应**：

```json
{
  "success": true,
  "data": {
    "total": 156,
    "limit": 20,
    "offset": 0,
    "decisions": [
      {
        "decision_id": 678,
        "agent_id": "node-prod-001",
        "issue_type": "service_down",
        "status": "approved",
        "created_at": "2025-11-16T10:00:25Z"
      }
    ]
  },
  "timestamp": "2025-11-16T10:01:00Z"
}
```

---

## 集群管理接口

### 6. 节点注册

**端点**：`POST /cluster/register`

**用途**：下级节点向上级 Monitor 注册

**认证**：初始注册密钥（配置文件中设置）

**请求体**：

```json
{
  "agent_id": "node-prod-001",
  "name": "Production Server 1",
  "metadata": {
    "hostname": "prod-server-1.example.com",
    "ip_address": "192.168.1.100",
    "os": "Ubuntu 22.04",
    "cpu_cores": 8,
    "memory_gb": 32
  },
  "registration_token": "secret-registration-token"
}
```

**响应**：

```json
{
  "success": true,
  "data": {
    "agent_id": "node-prod-001",
    "api_key": "cortex_ak_abc123def456...",
    "upstream_monitor_url": "https://monitor.example.com",
    "registered_at": "2025-11-16T09:00:00Z"
  },
  "message": "节点注册成功",
  "timestamp": "2025-11-16T09:00:00Z"
}
```

---

### 7. 获取集群节点列表

**端点**：`GET /cluster/nodes`

**用途**：获取所有下级节点的状态信息

**认证**：JWT

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `status` | string | 否 | 按状态筛选（online/offline） |
| `health` | string | 否 | 按健康状态筛选（healthy/warning/critical） |

**响应**：

```json
{
  "success": true,
  "data": {
    "total": 15,
    "online": 12,
    "offline": 3,
    "nodes": [
      {
        "agent_id": "node-prod-001",
        "name": "Production Server 1",
        "status": "online",
        "health_status": "warning",
        "last_heartbeat": "2025-11-16T10:00:00Z",
        "issues_count": {
          "L1": 1,
          "L2": 1,
          "L3": 0
        },
        "metrics": {
          "cpu_percent": 45.2,
          "memory_percent": 62.1,
          "disk_percent": 92.5
        }
      }
    ]
  },
  "timestamp": "2025-11-16T10:01:00Z"
}
```

---

### 8. 获取节点详情

**端点**：`GET /cluster/nodes/{agent_id}`

**用途**：获取单个节点的详细信息（下钻分析）

**认证**：JWT

**响应**：

```json
{
  "success": true,
  "data": {
    "agent": {
      "agent_id": "node-prod-001",
      "name": "Production Server 1",
      "status": "online",
      "health_status": "warning",
      "last_heartbeat": "2025-11-16T10:00:00Z",
      "metadata": {
        "hostname": "prod-server-1.example.com",
        "ip_address": "192.168.1.100"
      }
    },
    "recent_reports": [
      {
        "report_id": 12345,
        "timestamp": "2025-11-16T10:00:00Z",
        "status": "warning",
        "metrics": { ... }
      }
    ],
    "events": [
      {
        "event_id": 567,
        "type": "decision",
        "description": "L2 决策：批准重启 nginx",
        "timestamp": "2025-11-16T10:00:25Z"
      }
    ],
    "decisions": [
      {
        "decision_id": 678,
        "issue_type": "service_down",
        "status": "approved",
        "created_at": "2025-11-16T10:00:25Z"
      }
    ],
    "alerts": [
      {
        "alert_id": 89,
        "level": "L3",
        "type": "database_crash",
        "status": "new",
        "created_at": "2025-11-16T09:30:00Z"
      }
    ],
    "metrics_summary": {
      "avg_cpu": 45.2,
      "avg_memory": 62.1,
      "avg_disk": 85.3,
      "uptime_percentage": 99.95
    }
  },
  "timestamp": "2025-11-16T10:01:00Z"
}
```

---

### 9. 获取集群拓扑

**端点**：`GET /cluster/topology`

**用途**：获取集群的树形拓扑结构

**认证**：JWT

**响应**：

```json
{
  "success": true,
  "data": {
    "root": {
      "agent_id": "monitor-root",
      "name": "Root Monitor",
      "level": 0,
      "children": [
        {
          "agent_id": "monitor-region-a",
          "name": "Region A Monitor",
          "level": 1,
          "children": [
            {
              "agent_id": "node-prod-001",
              "name": "Production Server 1",
              "level": 2,
              "status": "online",
              "children": []
            },
            {
              "agent_id": "node-prod-002",
              "name": "Production Server 2",
              "level": 2,
              "status": "online",
              "children": []
            }
          ]
        },
        {
          "agent_id": "monitor-region-b",
          "name": "Region B Monitor",
          "level": 1,
          "children": [ ... ]
        }
      ]
    },
    "total_nodes": 25,
    "max_depth": 3
  },
  "timestamp": "2025-11-16T10:01:00Z"
}
```

---

## 告警管理接口

### 10. 获取告警列表

**端点**：`GET /alerts`

**用途**：查询告警列表（支持筛选）

**认证**：JWT

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `status` | string | 否 | 状态筛选（new/acknowledged/resolved） |
| `level` | string | 否 | 级别筛选（L1/L2/L3） |
| `agent_id` | string | 否 | 节点筛选 |
| `severity` | string | 否 | 严重程度筛选（low/medium/high/critical） |
| `limit` | integer | 否 | 返回数量限制（默认 100） |
| `offset` | integer | 否 | 分页偏移量（默认 0） |

**示例**：`GET /alerts?status=new&level=L3&limit=20`

**响应**：

```json
{
  "success": true,
  "data": {
    "total": 45,
    "limit": 20,
    "offset": 0,
    "alerts": [
      {
        "alert_id": 89,
        "agent_id": "node-prod-001",
        "agent_name": "Production Server 1",
        "level": "L3",
        "type": "database_crash",
        "description": "PostgreSQL 数据库崩溃",
        "severity": "critical",
        "status": "new",
        "details": {
          "error_message": "FATAL: could not access file...",
          "last_successful_query": "2025-11-16T09:25:00Z"
        },
        "created_at": "2025-11-16T09:30:00Z",
        "acknowledged_at": null,
        "resolved_at": null
      }
    ]
  },
  "timestamp": "2025-11-16T10:01:00Z"
}
```

---

### 11. 获取告警详情

**端点**：`GET /alerts/{alert_id}`

**用途**：查询单个告警的详细信息

**认证**：JWT

**响应**：

```json
{
  "success": true,
  "data": {
    "alert_id": 89,
    "agent_id": "node-prod-001",
    "agent_name": "Production Server 1",
    "level": "L3",
    "type": "database_crash",
    "description": "PostgreSQL 数据库崩溃",
    "severity": "critical",
    "status": "new",
    "details": {
      "error_message": "FATAL: could not access file...",
      "last_successful_query": "2025-11-16T09:25:00Z",
      "related_logs": [ ... ]
    },
    "created_at": "2025-11-16T09:30:00Z",
    "acknowledged_at": null,
    "acknowledged_by": null,
    "resolved_at": null,
    "notes": null
  },
  "timestamp": "2025-11-16T10:01:00Z"
}
```

---

### 12. 确认告警

**端点**：`POST /alerts/{alert_id}/ack`

**用途**：确认告警（表示已知晓）

**认证**：JWT

**请求体**：

```json
{
  "user": "admin",
  "notes": "已知晓，正在处理中"
}
```

**响应**：

```json
{
  "success": true,
  "data": {
    "alert_id": 89,
    "status": "acknowledged",
    "acknowledged_at": "2025-11-16T10:05:00Z",
    "acknowledged_by": "admin"
  },
  "message": "告警已确认",
  "timestamp": "2025-11-16T10:05:00Z"
}
```

---

### 13. 关闭告警

**端点**：`POST /alerts/{alert_id}/resolve`

**用途**：关闭告警（标记为已解决）

**认证**：JWT

**请求体**：

```json
{
  "user": "admin",
  "notes": "数据库已恢复，问题已解决"
}
```

**响应**：

```json
{
  "success": true,
  "data": {
    "alert_id": 89,
    "status": "resolved",
    "resolved_at": "2025-11-16T10:30:00Z"
  },
  "message": "告警已关闭",
  "timestamp": "2025-11-16T10:30:00Z"
}
```

---

## 意图查询接口

### 14. 查询意图列表

**端点**：`GET /intents`

**用途**：查询 Intent-Engine 记录的意图历史

**认证**：JWT

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | integer | 否 | 按任务 ID 筛选 |
| `type` | string | 否 | 按类型筛选（decision/blocker/milestone/note） |
| `since` | string | 否 | 时间范围（如 7d, 24h） |
| `limit` | integer | 否 | 返回数量限制（默认 50） |

**示例**：`GET /intents?type=decision&since=7d&limit=20`

**响应**：

```json
{
  "success": true,
  "data": {
    "total": 234,
    "limit": 20,
    "offset": 0,
    "intents": [
      {
        "event_id": 567,
        "task_id": 123,
        "type": "decision",
        "data": "L2 Decision for node-prod-001: approved - service_down",
        "created_at": "2025-11-16T10:00:25Z"
      }
    ]
  },
  "timestamp": "2025-11-16T10:01:00Z"
}
```

---

## 认证授权接口

### 15. 用户登录

**端点**：`POST /auth/login`

**用途**：用户登录，获取 JWT Token

**认证**：无（公开接口）

**请求体**：

```json
{
  "username": "admin",
  "password": "your-password-here"
}
```

**响应**：

```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 1800,
    "user": {
      "username": "admin",
      "email": "admin@example.com",
      "role": "admin"
    }
  },
  "message": "登录成功",
  "timestamp": "2025-11-16T10:00:00Z"
}
```

---

### 16. 刷新 Token

**端点**：`POST /auth/refresh`

**用途**：刷新 JWT Token

**认证**：JWT（当前 Token）

**响应**：

```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 1800
  },
  "message": "Token 已刷新",
  "timestamp": "2025-11-16T10:30:00Z"
}
```

---

### 17. 获取当前用户信息

**端点**：`GET /auth/me`

**用途**：获取当前登录用户信息

**认证**：JWT

**响应**：

```json
{
  "success": true,
  "data": {
    "user_id": 1,
    "username": "admin",
    "email": "admin@example.com",
    "role": "admin",
    "created_at": "2025-11-01T00:00:00Z",
    "last_login": "2025-11-16T10:00:00Z"
  },
  "timestamp": "2025-11-16T10:01:00Z"
}
```

---

### 18. 生成 API Key

**端点**：`POST /auth/api-keys`

**用途**：为节点生成新的 API Key

**认证**：JWT（需要 admin 角色）

**请求体**：

```json
{
  "agent_id": "node-prod-002",
  "name": "Production Server 2 API Key",
  "expires_at": "2026-11-16T00:00:00Z"
}
```

**响应**：

```json
{
  "success": true,
  "data": {
    "api_key_id": 5,
    "agent_id": "node-prod-002",
    "api_key": "cortex_ak_xyz789...",
    "name": "Production Server 2 API Key",
    "created_at": "2025-11-16T10:00:00Z",
    "expires_at": "2026-11-16T00:00:00Z"
  },
  "message": "API Key 已生成",
  "timestamp": "2025-11-16T10:00:00Z"
}
```

---

### 19. 撤销 API Key

**端点**：`DELETE /auth/api-keys/{api_key_id}`

**用途**：撤销指定的 API Key

**认证**：JWT（需要 admin 角色）

**响应**：

```json
{
  "success": true,
  "message": "API Key 已撤销",
  "timestamp": "2025-11-16T10:00:00Z"
}
```

---

## WebSocket 实时通信

### 连接端点

**URL**：`ws(s)://{monitor_host}:{port}/ws`

**认证**：通过查询参数传递 JWT Token

**示例**：`wss://monitor.example.com/ws?token={jwt_token}`

### 连接流程

1. 客户端建立 WebSocket 连接
2. 服务器验证 Token
3. 连接成功，开始接收实时消息

### 消息格式

服务器推送的消息格式：

```json
{
  "type": "event_type",
  "data": { ... },
  "timestamp": "2025-11-16T10:00:00Z"
}
```

### 事件类型

#### 1. 节点上报事件

```json
{
  "type": "report_received",
  "data": {
    "agent_id": "node-prod-001",
    "status": "warning",
    "timestamp": "2025-11-16T10:00:00Z"
  },
  "timestamp": "2025-11-16T10:00:05Z"
}
```

#### 2. 节点状态变化

```json
{
  "type": "node_status_changed",
  "data": {
    "agent_id": "node-prod-001",
    "old_status": "online",
    "new_status": "offline",
    "reason": "heartbeat_timeout"
  },
  "timestamp": "2025-11-16T10:05:00Z"
}
```

#### 3. 新告警

```json
{
  "type": "new_alert",
  "data": {
    "alert_id": 90,
    "agent_id": "node-prod-001",
    "level": "L3",
    "type": "database_crash",
    "severity": "critical",
    "description": "PostgreSQL 数据库崩溃"
  },
  "timestamp": "2025-11-16T10:00:00Z"
}
```

#### 4. 决策完成

```json
{
  "type": "decision_completed",
  "data": {
    "decision_id": 678,
    "agent_id": "node-prod-001",
    "status": "approved",
    "issue_type": "service_down"
  },
  "timestamp": "2025-11-16T10:00:25Z"
}
```

### 客户端发送消息

客户端可以发送 ping 消息保持连接：

```json
{
  "type": "ping"
}
```

服务器响应：

```json
{
  "type": "pong",
  "timestamp": "2025-11-16T10:00:00Z"
}
```

---

## 数据模型

### Agent（节点）

```typescript
interface Agent {
  id: string;                    // 节点 ID
  name: string;                  // 节点名称
  upstream_monitor_url: string | null;  // 上级 Monitor URL
  api_key: string;               // API Key（加密存储）
  status: 'online' | 'offline';  // 状态
  health_status: 'healthy' | 'warning' | 'critical' | 'unknown';
  last_heartbeat: string;        // 最后心跳时间（ISO 8601）
  created_at: string;            // 创建时间
  updated_at: string;            // 更新时间
  metadata: object;              // 元数据
}
```

### Report（上报数据）

```typescript
interface Report {
  id: number;                    // 报告 ID
  agent_id: string;              // 节点 ID
  timestamp: string;             // 时间戳
  status: 'healthy' | 'warning' | 'critical';
  metrics: SystemMetrics;        // 系统指标
  issues: IssueReport[];         // 问题列表
  actions_taken: ActionReport[]; // 已执行操作
  metadata: object;              // 元数据
  created_at: string;            // 接收时间
}

interface SystemMetrics {
  cpu_percent: number;
  memory_percent: number;
  disk_percent: number;
  load_average: [number, number, number];
  uptime_seconds: number;
  process_count?: number;
  disk_io?: object;
  network_io?: object;
}

interface IssueReport {
  level: 'L1' | 'L2' | 'L3';
  type: string;
  description: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  proposed_fix?: string;
  risk_assessment?: string;
  details: object;
  timestamp: string;
}

interface ActionReport {
  level: 'L1' | 'L2';
  action: string;
  result: 'success' | 'failed' | 'partial';
  details: string;
  timestamp: string;
  intent_id?: number;
}
```

### Decision（决策）

```typescript
interface Decision {
  id: number;                    // 决策 ID
  agent_id: string;              // 节点 ID
  issue_type: string;            // 问题类型
  issue_description: string;     // 问题描述
  proposed_action: string;       // 提议操作
  llm_analysis: string;          // LLM 分析结果
  status: 'approved' | 'rejected';
  reason: string;                // 决策理由
  created_at: string;            // 决策时间
  executed_at?: string;          // 执行时间
  execution_result?: string;     // 执行结果
}
```

### Alert（告警）

```typescript
interface Alert {
  id: number;                    // 告警 ID
  agent_id: string;              // 节点 ID
  level: 'L1' | 'L2' | 'L3';
  type: string;                  // 告警类型
  description: string;           // 描述
  severity: 'low' | 'medium' | 'high' | 'critical';
  status: 'new' | 'acknowledged' | 'resolved';
  details: object;               // 详细信息
  created_at: string;            // 创建时间
  acknowledged_at?: string;      // 确认时间
  acknowledged_by?: string;      // 确认人
  resolved_at?: string;          // 解决时间
  notes?: string;                // 备注
}
```

---

## 请求示例

### cURL 示例

#### 1. 上报数据

```bash
curl -X POST https://monitor.example.com/api/v1/reports \
  -H "Content-Type: application/json" \
  -H "X-API-Key: cortex_ak_abc123..." \
  -d '{
    "agent_id": "node-prod-001",
    "timestamp": "2025-11-16T10:00:00Z",
    "status": "healthy",
    "metrics": {
      "cpu_percent": 45.2,
      "memory_percent": 62.1,
      "disk_percent": 85.0,
      "load_average": [1.2, 1.5, 1.8],
      "uptime_seconds": 864000
    },
    "issues": [],
    "actions_taken": []
  }'
```

#### 2. 用户登录

```bash
curl -X POST https://monitor.example.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "your-password"
  }'
```

#### 3. 查询节点列表

```bash
curl -X GET https://monitor.example.com/api/v1/cluster/nodes \
  -H "Authorization: Bearer {jwt_token}"
```

### Python 示例

```python
import httpx

# 配置
MONITOR_URL = "https://monitor.example.com/api/v1"
API_KEY = "cortex_ak_abc123..."

# 上报数据
async def send_report(report_data):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{MONITOR_URL}/reports",
            headers={"X-API-Key": API_KEY},
            json=report_data,
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()

# 请求 L2 决策
async def request_decision(issue_data):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{MONITOR_URL}/decisions/request",
            headers={"X-API-Key": API_KEY},
            json={
                "agent_id": "node-prod-001",
                "issue": issue_data
            },
            timeout=30.0
        )
        response.raise_for_status()
        result = response.json()
        return result["data"]["status"]  # 'approved' or 'rejected'
```

### TypeScript/JavaScript 示例

```typescript
import axios from 'axios';

const MONITOR_URL = 'https://monitor.example.com/api/v1';
const JWT_TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...';

// 获取集群节点列表
async function getClusterNodes() {
  const response = await axios.get(`${MONITOR_URL}/cluster/nodes`, {
    headers: {
      'Authorization': `Bearer ${JWT_TOKEN}`
    }
  });

  return response.data.data;
}

// 确认告警
async function acknowledgeAlert(alertId: number, notes: string) {
  const response = await axios.post(
    `${MONITOR_URL}/alerts/${alertId}/ack`,
    {
      user: 'admin',
      notes: notes
    },
    {
      headers: {
        'Authorization': `Bearer ${JWT_TOKEN}`
      }
    }
  );

  return response.data;
}

// WebSocket 连接
const ws = new WebSocket(`wss://monitor.example.com/ws?token=${JWT_TOKEN}`);

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);

  switch (message.type) {
    case 'new_alert':
      console.log('新告警:', message.data);
      break;
    case 'node_status_changed':
      console.log('节点状态变化:', message.data);
      break;
  }
};
```

---

## 速率限制

为防止滥用，API 实施速率限制：

| 端点类型 | 限制 |
|---------|------|
| 上报接口 | 100 次/分钟/节点 |
| 查询接口 | 1000 次/分钟/用户 |
| 认证接口 | 10 次/分钟/IP |

超出限制时返回 `429 Too Many Requests`。

响应头包含速率限制信息：

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1700136000
```

---

## 版本控制

API 版本通过 URL 路径指定：`/api/v1/...`

当引入不兼容的变更时，会发布新版本（如 v2）。旧版本将在至少 6 个月内保持支持。

---

## 安全最佳实践

1. **始终使用 HTTPS**：生产环境必须启用 TLS/SSL
2. **妥善保管 API Key**：不要在代码中硬编码，使用环境变量
3. **定期轮换密钥**：建议每 90 天轮换一次 API Key
4. **最小权限原则**：为用户分配最低必要的角色权限
5. **监控异常访问**：关注 401/403 错误率和异常 IP

---

## 附录

### A. HTTP 状态码说明

| 状态码 | 说明 |
|-------|------|
| 200 | 请求成功 |
| 201 | 资源创建成功 |
| 400 | 请求参数错误 |
| 401 | 未认证 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 409 | 资源冲突 |
| 429 | 请求过于频繁 |
| 500 | 服务器内部错误 |
| 503 | 服务不可用 |

### B. 时间格式

所有时间字段使用 **ISO 8601** 格式：

- 完整格式：`2025-11-16T10:00:00Z`（UTC 时间）
- 带时区：`2025-11-16T10:00:00+08:00`（东八区）

### C. 分页参数

支持分页的接口统一使用：

- `limit`: 每页数量（默认 50，最大 1000）
- `offset`: 偏移量（默认 0）

响应包含分页元数据：

```json
{
  "total": 1234,
  "limit": 50,
  "offset": 0,
  "items": [ ... ]
}
```

---

**文档版本**：v1.0.0
**最后更新**：2025-11-16
**维护者**：Cortex 开发团队
