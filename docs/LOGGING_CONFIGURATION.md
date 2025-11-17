# 日志配置指南

本文档说明 Cortex 项目的日志配置和使用方法。

## 概述

Cortex 使用 [Loguru](https://github.com/Delgan/loguru) 作为统一的日志库，提供：

- 统一的日志格式
- 灵活的日志级别配置
- 自动日志轮转和清理
- 多种输出格式（标准/JSON/简化）
- 模块级别日志配置

## 日志级别

支持以下日志级别（按严重程度递增）：

- **DEBUG**: 详细调试信息
- **INFO**: 一般信息
- **WARNING**: 警告信息
- **ERROR**: 错误信息
- **CRITICAL**: 严重错误

## 配置方式

### 1. 通过配置文件（推荐）

在 `.env` 中配置：

```yaml
logging:
  level: "INFO"  # 全局日志级别
  format: "standard"  # 日志格式：standard/json/simple
  console: true  # 是否输出到控制台
  console_level: null  # 控制台日志级别（可选）
  file: "logs/cortex.log"  # 日志文件路径
  file_level: null  # 文件日志级别（可选）
  rotation: "10 MB"  # 轮转策略
  retention: "30 days"  # 保留时间
  compression: "zip"  # 压缩格式
  modules:  # 模块级别配置
    cortex.monitor: "DEBUG"
    cortex.probe: "INFO"
```

### 2. 通过环境变量

```bash
export CORTEX_LOG_LEVEL=DEBUG
export CORTEX_LOG_FORMAT=json
export CORTEX_LOG_FILE=logs/cortex.log
```

### 3. 通过代码

```python
from cortex.common.logging_config import LoggingConfig

# 基础配置
LoggingConfig.configure(
    level="INFO",
    console=True,
    file_path="logs/app.log",
    rotation="10 MB",
    retention="30 days"
)

# 从配置对象加载
from cortex.config import get_settings
settings = get_settings()
LoggingConfig.configure_from_settings(settings)
```

## 日志格式

### 标准格式（standard）

适合开发和调试：

```
2024-01-15 10:30:45.123 | INFO     | cortex.monitor:main:25 | Server started
```

### JSON 格式（json）

适合生产环境和日志分析：

```json
{"time": "2024-01-15 10:30:45.123", "level": "INFO", "module": "cortex.monitor", "function": "main", "line": 25, "message": "Server started"}
```

### 简化格式（simple）

适合控制台输出：

```
10:30:45 | INFO     | Server started
```

## 日志轮转策略

### 按大小轮转

```yaml
rotation: "10 MB"  # 文件达到 10MB 时轮转
rotation: "100 KB"
rotation: "1 GB"
```

### 按时间轮转

```yaml
rotation: "1 day"  # 每天轮转
rotation: "1 week"
rotation: "1 hour"
```

### 按时间点轮转

```yaml
rotation: "00:00"  # 每天午夜轮转
rotation: "12:00"  # 每天中午轮转
```

## 日志保留策略

```yaml
retention: "30 days"  # 保留 30 天
retention: "1 week"   # 保留 1 周
retention: 10         # 保留 10 个文件
```

## 模块级别配置

为不同模块设置不同的日志级别：

```yaml
logging:
  level: "INFO"  # 全局默认
  modules:
    cortex.monitor: "DEBUG"  # Monitor 模块使用 DEBUG
    cortex.probe: "INFO"  # Probe 模块使用 INFO
    cortex.common.cache: "WARNING"  # 缓存模块只记录警告以上
```

## 使用示例

### 在代码中记录日志

```python
from loguru import logger

# 基本日志
logger.info("Server started")
logger.debug("Connection details: {}", connection_info)
logger.warning("High memory usage: {}%", memory_percent)
logger.error("Failed to connect: {}", error)
logger.critical("System crash: {}", exception)

# 带上下文的日志
with logger.contextualize(request_id="req-123"):
    logger.info("Processing request")
    # request_id 会自动包含在日志中

# 结构化日志
logger.info(
    "User login",
    user_id=user.id,
    ip=request.client.host,
    success=True
)
```

### 捕获异常

```python
try:
    risky_operation()
except Exception as e:
    logger.exception("Operation failed")  # 自动记录完整堆栈
```

### 性能追踪

```python
import time
from loguru import logger

@logger.catch  # 自动捕获异常
def my_function():
    start = time.time()
    # 执行操作
    logger.info("Operation completed in {:.2f}s", time.time() - start)
```

## 生产环境推荐配置

```yaml
logging:
  level: "INFO"
  format: "json"  # JSON 格式便于日志分析
  console: true
  console_level: "WARNING"  # 控制台只显示警告以上
  file: "/var/log/cortex/cortex.log"
  rotation: "100 MB"  # 较大的轮转大小
  retention: "90 days"  # 较长的保留时间
  compression: "gz"  # 使用 gzip 压缩节省空间
  modules:
    cortex.monitor: "INFO"
    cortex.probe: "INFO"
    cortex.common.cache: "WARNING"  # 减少缓存日志
```

## 开发环境推荐配置

```yaml
logging:
  level: "DEBUG"
  format: "standard"  # 标准格式易读
  console: true
  file: "logs/dev.log"
  rotation: "10 MB"
  retention: "7 days"
  modules:
    cortex.monitor: "DEBUG"
    cortex.probe: "DEBUG"
```

## 命令行选项

### Monitor

```bash
# 使用默认配置
cortex-monitor

# 指定日志级别
cortex-monitor --log-level DEBUG

# 指定配置文件
cortex-monitor --config .env
```

### Probe

```bash
# 使用默认配置
cortex-probe

# 指定日志级别
cortex-probe --log-level DEBUG
```

## 日志文件位置

默认日志位置：

- **Monitor**: `logs/monitor.log`
- **Probe**: `logs/probe.log`
- **通用**: `logs/cortex.log`

轮转后的文件命名：

- `cortex.log` - 当前日志
- `cortex.log.2024-01-15_10-30-45.zip` - 已轮转并压缩的日志

## 常见问题

### Q: 如何查看实时日志？

```bash
tail -f logs/cortex.log
```

### Q: 如何减少日志量？

1. 提高全局日志级别：`level: "WARNING"`
2. 为特定模块降低级别：

```yaml
modules:
  cortex.common.cache: "ERROR"  # 只记录错误
```

### Q: 如何在多进程环境下使用？

Loguru 自动支持多进程，使用 `enqueue=True` 参数：

```python
LoggingConfig.configure(
    level="INFO",
    file_path="logs/app.log",
    # enqueue=True 在内部已配置
)
```

### Q: 日志文件太大怎么办？

1. 调整轮转策略：`rotation: "10 MB"`
2. 减少保留时间：`retention: "7 days"`
3. 启用压缩：`compression: "gz"`

## 最佳实践

1. **生产环境使用 JSON 格式**：便于日志分析和告警
2. **设置合理的轮转和保留策略**：避免磁盘空间问题
3. **为不同模块设置不同级别**：减少噪音日志
4. **使用结构化日志**：包含上下文信息
5. **避免敏感信息**：不要记录密码、密钥等
6. **使用异常捕获**：`@logger.catch` 装饰器
7. **定期检查日志**：及时发现和解决问题

## 参考资料

- [Loguru 官方文档](https://loguru.readthedocs.io/)
- [日志配置代码](../cortex/common/logging_config.py)
- [配置示例文件](../.env.example)
