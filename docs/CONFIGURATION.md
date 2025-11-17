# Cortex 配置参考

本文档提供 Cortex 所有配置项的详细说明。

## 配置方式

Cortex 支持三种配置方式（优先级从高到低）：

1. **环境变量**：适合 Docker 部署和 CI/CD
2. **YAML 配置文件**：适合传统部署和复杂配置
3. **默认值**：内置的合理默认值

### 环境变量优先级

```bash
# 显式环境变量 > .env 文件 > config.yaml > 默认值
export CORTEX_LOG_LEVEL=DEBUG  # 最高优先级
```

## 配置文件结构

### 完整配置示例

```yaml
# ==================== Agent 配置 ====================
agent:
  id: "agent-001"               # 节点唯一标识（必需）
  name: "Cortex Agent"          # 节点名称（必需）
  mode: "standalone"            # 运行模式: standalone | cluster
  upstream_monitor_url: null    # 上级 Monitor URL（cluster 模式必需）

# ==================== Probe 配置 ====================
probe:
  # Web 服务配置
  host: "0.0.0.0"               # 监听地址
  port: 8001                    # 监听端口

  # 调度配置
  schedule: "0 * * * *"         # Cron 表达式
  timeout_seconds: 300          # 巡检超时时间（秒）

  # 工作区配置
  workspace: "./probe_workspace"  # workspace 目录路径

  # 报告配置
  report_retention_days: 30     # 报告保留天数

  # 巡检项目开关（旧版兼容）
  check_system_health: true     # 系统健康检查
  check_service_status: true    # 服务状态检查
  check_log_analysis: true      # 日志分析
  check_network: true           # 网络连通性检查

  # 阈值配置
  threshold_cpu_percent: 80.0   # CPU 使用率告警阈值
  threshold_memory_percent: 85.0  # 内存使用率告警阈值
  threshold_disk_percent: 90.0  # 磁盘使用率告警阈值

# ==================== Monitor 配置 ====================
monitor:
  host: "0.0.0.0"               # 监听地址
  port: 8000                    # 监听端口
  database_url: "sqlite:///./cortex.db"  # 数据库 URL
  registration_token: "your-secret-token"  # 节点注册密钥（必需）

# ==================== Claude API 配置 ====================
claude:
  api_key: "sk-ant-your-key"    # Claude API Key（必需）
  model: "claude-sonnet-4"      # 模型名称
  max_tokens: 2000              # 最大 token 数
  timeout: 30                   # 请求超时时间（秒）
  temperature: 1.0              # 生成温度（0.0-1.0）

# ==================== Telegram 配置 ====================
telegram:
  enabled: false                # 是否启用
  bot_token: null               # Bot Token
  chat_id: null                 # Chat ID

# ==================== Intent Engine 配置 ====================
intent_engine:
  enabled: true                 # 是否启用意图记录
  database_url: "sqlite:///./cortex_intents.db"  # Intent 数据库 URL

# ==================== 日志配置 ====================
logging:
  level: "INFO"                 # 日志级别
  format: "standard"            # 日志格式
  console: true                 # 是否输出到控制台
  console_level: null           # 控制台日志级别（可选）
  file: "logs/cortex.log"       # 日志文件路径
  file_level: null              # 文件日志级别（可选）
  rotation: "10 MB"             # 日志轮转策略
  retention: "30 days"          # 日志保留时间
  compression: "zip"            # 压缩格式
  modules:                      # 模块级别配置
    cortex.monitor: "DEBUG"
    cortex.probe: "INFO"

# ==================== 认证配置 ====================
auth:
  secret_key: "your-secret-key"  # JWT 密钥（必需，≥32字符）
  algorithm: "HS256"            # JWT 算法
  access_token_expire_minutes: 30  # Token 过期时间（分钟）
```

## Agent 配置

### agent.id

- **类型**: String
- **必需**: ✅
- **环境变量**: `CORTEX_AGENT_ID`
- **默认值**: 无
- **描述**: 节点的唯一标识符，在集群中必须唯一
- **示例**:
  ```yaml
  id: "monitor-main-01"
  id: "probe-web-01"
  id: "probe-db-beijing-01"
  ```

### agent.name

- **类型**: String
- **必需**: ✅
- **环境变量**: `CORTEX_AGENT_NAME`
- **默认值**: 无
- **描述**: 节点的显示名称，用于 UI 展示
- **示例**:
  ```yaml
  name: "Production Monitor"
  name: "Beijing Web Probe"
  ```

### agent.mode

- **类型**: Enum
- **必需**: ✅
- **环境变量**: `CORTEX_AGENT_MODE`
- **默认值**: `"standalone"`
- **可选值**:
  - `standalone`: 独立模式，作为根节点
  - `cluster`: 集群模式，向上级 Monitor 上报
- **描述**: 节点运行模式

### agent.upstream_monitor_url

- **类型**: String (URL)
- **必需**: cluster 模式时必需
- **环境变量**: `CORTEX_AGENT_UPSTREAM_MONITOR_URL`
- **默认值**: `null`
- **描述**: 上级 Monitor 的 URL
- **格式**: `http(s)://host:port`
- **示例**:
  ```yaml
  upstream_monitor_url: "http://monitor.example.com:8000"
  upstream_monitor_url: "https://10.0.1.100:8000"
  ```

## Probe 配置

### probe.host

- **类型**: String (IP)
- **必需**: ❌
- **环境变量**: `CORTEX_PROBE_HOST`
- **默认值**: `"0.0.0.0"`
- **描述**: Probe Web 服务监听地址
- **建议**:
  - 开发环境: `127.0.0.1` (仅本地访问)
  - 生产环境: `0.0.0.0` (允许外部访问)

### probe.port

- **类型**: Integer
- **必需**: ❌
- **环境变量**: `CORTEX_PROBE_PORT`
- **默认值**: `8001`
- **范围**: 1-65535
- **描述**: Probe Web 服务监听端口

### probe.schedule

- **类型**: String (Cron)
- **必需**: ❌
- **环境变量**: `CORTEX_PROBE_SCHEDULE`
- **默认值**: `"0 * * * *"`
- **格式**: 标准 Cron 表达式 (5 字段)
- **描述**: 巡检执行计划
- **示例**:
  ```yaml
  schedule: "*/15 * * * *"  # 每 15 分钟
  schedule: "0 */2 * * *"   # 每 2 小时
  schedule: "0 9 * * *"     # 每天 9:00
  schedule: "0 0 * * 0"     # 每周日 00:00
  ```
- **参考**: https://crontab.guru/

### probe.timeout_seconds

- **类型**: Integer
- **必需**: ❌
- **环境变量**: `CORTEX_PROBE_TIMEOUT_SECONDS`
- **默认值**: `300`
- **范围**: 60-3600
- **描述**: 巡检任务的最大执行时间（秒）
- **建议**:
  - 简单巡检: 300 (5分钟)
  - 复杂巡检: 600-900 (10-15分钟)
  - 安全审计: 1800-3600 (30-60分钟)

### probe.workspace

- **类型**: String (Path)
- **必需**: ❌
- **环境变量**: `CORTEX_PROBE_WORKSPACE`
- **默认值**: `"./probe_workspace"`
- **描述**: Probe workspace 目录路径，包含巡检文档
- **注意**: 确保目录存在且可写

### probe.report_retention_days

- **类型**: Integer
- **必需**: ❌
- **环境变量**: `CORTEX_PROBE_REPORT_RETENTION_DAYS`
- **默认值**: `30`
- **范围**: 1-365
- **描述**: 巡检报告的保留天数，超期自动清理

### probe.threshold_cpu_percent

- **类型**: Float
- **必需**: ❌
- **环境变量**: `CORTEX_PROBE_THRESHOLD_CPU_PERCENT`
- **默认值**: `80.0`
- **范围**: 0.0-100.0
- **描述**: CPU 使用率告警阈值（百分比）

### probe.threshold_memory_percent

- **类型**: Float
- **必需**: ❌
- **环境变量**: `CORTEX_PROBE_THRESHOLD_MEMORY_PERCENT`
- **默认值**: `85.0`
- **范围**: 0.0-100.0
- **描述**: 内存使用率告警阈值（百分比）

### probe.threshold_disk_percent

- **类型**: Float
- **必需**: ❌
- **环境变量**: `CORTEX_PROBE_THRESHOLD_DISK_PERCENT`
- **默认值**: `90.0`
- **范围**: 0.0-100.0
- **描述**: 磁盘使用率告警阈值（百分比）

## Monitor 配置

### monitor.host

- **类型**: String (IP)
- **必需**: ❌
- **环境变量**: `CORTEX_MONITOR_HOST`
- **默认值**: `"0.0.0.0"`
- **描述**: Monitor Web 服务监听地址

### monitor.port

- **类型**: Integer
- **必需**: ❌
- **环境变量**: `CORTEX_MONITOR_PORT`
- **默认值**: `8000`
- **范围**: 1-65535
- **描述**: Monitor Web 服务监听端口

### monitor.database_url

- **类型**: String (URL)
- **必需**: ❌
- **环境变量**: `CORTEX_MONITOR_DATABASE_URL`
- **默认值**: `"sqlite:///./cortex.db"`
- **格式**: SQLAlchemy 数据库 URL
- **支持的数据库**:
  - SQLite (开发/小规模): `sqlite:///path/to/db.db`
  - PostgreSQL (生产): `postgresql://user:pass@host:5432/dbname`
  - MySQL (生产): `mysql+pymysql://user:pass@host:3306/dbname`
- **示例**:
  ```yaml
  # SQLite（相对路径）
  database_url: "sqlite:///./cortex.db"

  # SQLite（绝对路径）
  database_url: "sqlite:////opt/cortex/data/cortex.db"

  # PostgreSQL
  database_url: "postgresql://cortex:password@localhost:5432/cortex"
  ```

### monitor.registration_token

- **类型**: String
- **必需**: ✅
- **环境变量**: `CORTEX_MONITOR_REGISTRATION_TOKEN`
- **默认值**: 无
- **描述**: 节点注册时的认证密钥
- **建议**: 使用强随机字符串
- **生成方式**:
  ```bash
  openssl rand -hex 32
  ```

## Claude API 配置

### claude.api_key

- **类型**: String
- **必需**: ✅
- **环境变量**: `ANTHROPIC_API_KEY`
- **默认值**: 无
- **格式**: `sk-ant-...`
- **描述**: Anthropic Claude API Key
- **获取**: https://console.anthropic.com/

### claude.model

- **类型**: String
- **必需**: ❌
- **环境变量**: `ANTHROPIC_MODEL`
- **默认值**: `"claude-sonnet-4"`
- **可选值**:
  - `claude-sonnet-4`: 推荐，平衡性能和成本
  - `claude-opus-4`: 最强性能，成本高
  - `claude-haiku-4`: 快速响应，成本低
- **描述**: 使用的 Claude 模型

### claude.max_tokens

- **类型**: Integer
- **必需**: ❌
- **环境变量**: `ANTHROPIC_MAX_TOKENS`
- **默认值**: `2000`
- **范围**: 1-4096
- **描述**: 单次请求的最大 token 数

### claude.timeout

- **类型**: Integer
- **必需**: ❌
- **环境变量**: `ANTHROPIC_TIMEOUT`
- **默认值**: `30`
- **范围**: 5-300
- **描述**: API 请求超时时间（秒）

### claude.temperature

- **类型**: Float
- **必需**: ❌
- **环境变量**: `ANTHROPIC_TEMPERATURE`
- **默认值**: `1.0`
- **范围**: 0.0-1.0
- **描述**: 生成温度，越高越随机
- **建议**:
  - 分析任务: 0.3-0.5 (更确定)
  - 决策任务: 0.7-1.0 (更灵活)

## Telegram 配置

### telegram.enabled

- **类型**: Boolean
- **必需**: ❌
- **环境变量**: `TELEGRAM_ENABLED`
- **默认值**: `false`
- **描述**: 是否启用 Telegram 通知

### telegram.bot_token

- **类型**: String
- **必需**: 启用时必需
- **环境变量**: `TELEGRAM_BOT_TOKEN`
- **默认值**: `null`
- **格式**: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`
- **描述**: Telegram Bot Token
- **获取**: 通过 [@BotFather](https://t.me/BotFather) 创建 Bot

### telegram.chat_id

- **类型**: String
- **必需**: 启用时必需
- **环境变量**: `TELEGRAM_CHAT_ID`
- **默认值**: `null`
- **格式**: 数字或 `@channel_name`
- **描述**: 接收通知的 Chat ID
- **获取**: 通过 [@userinfobot](https://t.me/userinfobot) 获取

## Intent Engine 配置

### intent_engine.enabled

- **类型**: Boolean
- **必需**: ❌
- **环境变量**: `CORTEX_INTENT_ENABLED`
- **默认值**: `true`
- **描述**: 是否启用意图追踪功能

### intent_engine.database_url

- **类型**: String (URL)
- **必需**: ❌
- **环境变量**: `CORTEX_INTENT_DATABASE_URL`
- **默认值**: `"sqlite:///./cortex_intents.db"`
- **描述**: Intent Engine 数据库 URL

## 日志配置

### logging.level

- **类型**: Enum
- **必需**: ❌
- **环境变量**: `CORTEX_LOG_LEVEL`
- **默认值**: `"INFO"`
- **可选值**: `DEBUG` | `INFO` | `WARNING` | `ERROR` | `CRITICAL`
- **描述**: 全局日志级别

### logging.format

- **类型**: Enum
- **必需**: ❌
- **环境变量**: `CORTEX_LOG_FORMAT`
- **默认值**: `"standard"`
- **可选值**:
  - `standard`: 标准格式（易读）
  - `json`: JSON 格式（易解析）
  - `simple`: 简化格式（控制台）
- **描述**: 日志输出格式

### logging.console

- **类型**: Boolean
- **必需**: ❌
- **默认值**: `true`
- **描述**: 是否输出日志到控制台

### logging.file

- **类型**: String (Path)
- **必需**: ❌
- **环境变量**: `CORTEX_LOG_FILE`
- **默认值**: `"logs/cortex.log"`
- **描述**: 日志文件路径

### logging.rotation

- **类型**: String
- **必需**: ❌
- **环境变量**: `CORTEX_LOG_ROTATION`
- **默认值**: `"10 MB"`
- **格式**:
  - 按大小: `"10 MB"`, `"100 KB"`, `"1 GB"`
  - 按时间: `"1 day"`, `"1 week"`, `"1 hour"`
  - 按时间点: `"00:00"`, `"12:00"`
- **描述**: 日志轮转策略

### logging.retention

- **类型**: String
- **必需**: ❌
- **环境变量**: `CORTEX_LOG_RETENTION`
- **默认值**: `"30 days"`
- **格式**:
  - 时间: `"30 days"`, `"1 week"`
  - 文件数: `10` (保留 10 个文件)
- **描述**: 日志保留策略

### logging.compression

- **类型**: Enum
- **必需**: ❌
- **环境变量**: `CORTEX_LOG_COMPRESSION`
- **默认值**: `"zip"`
- **可选值**: `zip` | `gz`
- **描述**: 日志压缩格式

### logging.modules

- **类型**: Dict[String, String]
- **必需**: ❌
- **描述**: 模块级别日志配置
- **示例**:
  ```yaml
  modules:
    cortex.monitor: "DEBUG"
    cortex.probe: "INFO"
    cortex.common.cache: "WARNING"
  ```

## 认证配置

### auth.secret_key

- **类型**: String
- **必需**: ✅
- **环境变量**: `CORTEX_AUTH_SECRET_KEY`
- **默认值**: 无
- **最小长度**: 32 字符
- **描述**: JWT 签名密钥
- **建议**: 使用强随机字符串
- **生成方式**:
  ```bash
  openssl rand -base64 32
  ```

### auth.algorithm

- **类型**: String
- **必需**: ❌
- **环境变量**: `CORTEX_AUTH_ALGORITHM`
- **默认值**: `"HS256"`
- **可选值**: `HS256` | `HS384` | `HS512`
- **描述**: JWT 签名算法

### auth.access_token_expire_minutes

- **类型**: Integer
- **必需**: ❌
- **环境变量**: `CORTEX_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES`
- **默认值**: `30`
- **范围**: 5-1440 (5分钟-24小时)
- **描述**: Access Token 过期时间（分钟）

## 配置验证

### 验证工具

```bash
# 验证配置文件语法
python -c "import yaml; yaml.safe_load(open('config.yaml'))"

# 验证配置有效性
python -m cortex.config.validate

# 查看当前配置
python -m cortex.config.show
```

### 常见配置错误

#### 1. YAML 语法错误

```yaml
# ❌ 错误：缩进不一致
agent:
  id: "test"
name: "Test"  # 应该缩进

# ✅ 正确
agent:
  id: "test"
  name: "Test"
```

#### 2. 类型错误

```yaml
# ❌ 错误：端口应该是数字
monitor:
  port: "8000"  # 字符串

# ✅ 正确
monitor:
  port: 8000  # 数字
```

#### 3. 必需字段缺失

```yaml
# ❌ 错误：缺少 api_key
claude:
  model: "claude-sonnet-4"

# ✅ 正确
claude:
  api_key: "sk-ant-..."
  model: "claude-sonnet-4"
```

## 环境特定配置

### 开发环境

```yaml
agent:
  mode: "standalone"

probe:
  schedule: "*/5 * * * *"  # 频繁执行

logging:
  level: "DEBUG"
  console: true
  file: null  # 不写文件
```

### 生产环境

```yaml
agent:
  mode: "cluster"
  upstream_monitor_url: "https://monitor.prod.example.com"

probe:
  schedule: "0 * * * *"  # 每小时
  timeout_seconds: 600

monitor:
  database_url: "postgresql://user:pass@postgres:5432/cortex"

logging:
  level: "INFO"
  format: "json"
  rotation: "100 MB"
  retention: "90 days"
  compression: "gz"

telegram:
  enabled: true
  bot_token: "${TELEGRAM_BOT_TOKEN}"
  chat_id: "${TELEGRAM_CHAT_ID}"
```

## 参考资料

- [安装指南](./INSTALLATION.md)
- [Docker 部署](./DOCKER_DEPLOYMENT.md)
- [多 Probe 配置](./MULTI_PROBE_SETUP.md)
- [环境变量示例](./.env.example)
- [配置文件示例](../config.example.yaml)
