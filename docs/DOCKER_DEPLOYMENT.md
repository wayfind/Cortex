# Cortex Docker 部署指南

本文档说明如何使用 Docker 和 Docker Compose 部署 Cortex。

## 快速开始

### 前置要求

- Docker 20.10+
- Docker Compose 2.0+
- 至少 2GB RAM
- 至少 10GB 可用磁盘空间

### 1. 克隆仓库

```bash
git clone https://github.com/yourusername/cortex.git
cd cortex
```

### 2. 配置环境变量

```bash
# 复制示例环境文件
cp .env.example .env

# 编辑 .env 文件，至少配置以下必需项：
vim .env
```

**必需配置**：
- `ANTHROPIC_API_KEY`: 你的 Claude API Key
- `CORTEX_MONITOR_REGISTRATION_TOKEN`: 节点注册密钥（生成随机字符串）
- `CORTEX_AUTH_SECRET_KEY`: JWT 密钥（至少 32 字符）

### 3. 启动服务

```bash
# 构建并启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 检查服务状态
docker-compose ps
```

### 4. 访问服务

- **Web UI**: http://localhost:3000
- **Monitor API**: http://localhost:8000
- **Probe API**: http://localhost:8001
- **API 文档**: http://localhost:8000/docs

### 5. 验证部署

```bash
# 检查 Monitor 健康状态
curl http://localhost:8000/health

# 检查 Probe 健康状态
curl http://localhost:8001/health

# 查看 Monitor 状态
curl http://localhost:8000/api/v1/status
```

## 服务管理

### 查看服务状态

```bash
docker-compose ps
```

### 查看服务日志

```bash
# 所有服务
docker-compose logs -f

# 特定服务
docker-compose logs -f cortex-monitor
docker-compose logs -f cortex-probe
docker-compose logs -f cortex-frontend
```

### 重启服务

```bash
# 重启所有服务
docker-compose restart

# 重启特定服务
docker-compose restart cortex-monitor
```

### 停止服务

```bash
# 停止所有服务
docker-compose down

# 停止并删除卷（⚠️ 会删除数据）
docker-compose down -v
```

### 更新服务

```bash
# 拉取最新代码
git pull

# 重新构建并启动
docker-compose up -d --build
```

## 配置说明

### 环境变量

Docker Compose 从以下来源读取配置（优先级从高到低）：

1. `.env` 文件中的环境变量
2. `docker-compose.yml` 中的 `environment` 配置
3. 默认值

### 常用配置项

```bash
# Agent 配置
CORTEX_AGENT_ID=agent-001
CORTEX_AGENT_NAME=Cortex Agent
CORTEX_AGENT_MODE=standalone  # or cluster

# 端口配置
CORTEX_MONITOR_PORT=8000
CORTEX_PROBE_PORT=8001
CORTEX_FRONTEND_PORT=3000

# Claude API
ANTHROPIC_API_KEY=sk-ant-your-key-here
ANTHROPIC_MODEL=claude-sonnet-4

# 安全配置
CORTEX_MONITOR_REGISTRATION_TOKEN=your-secret-token
CORTEX_AUTH_SECRET_KEY=your-jwt-secret-min-32-chars

# 日志配置
CORTEX_LOG_LEVEL=INFO  # DEBUG | INFO | WARNING | ERROR | CRITICAL
CORTEX_LOG_FORMAT=standard  # standard | json | simple

# Telegram 通知（可选）
TELEGRAM_ENABLED=false
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
```

## 持久化数据

### 卷说明

```yaml
volumes:
  cortex-data:          # 数据库文件
  cortex-logs:          # 日志文件
  cortex-probe-workspace:  # Probe 工作区
```

### 备份数据

```bash
# 备份所有卷
docker run --rm -v cortex-data:/data -v $(pwd):/backup ubuntu tar czf /backup/cortex-data-$(date +%Y%m%d).tar.gz -C /data .
docker run --rm -v cortex-logs:/logs -v $(pwd):/backup ubuntu tar czf /backup/cortex-logs-$(date +%Y%m%d).tar.gz -C /logs .

# 或使用 Docker Compose
docker-compose exec cortex-monitor tar czf /tmp/backup.tar.gz /app/data
docker cp cortex-monitor:/tmp/backup.tar.gz ./cortex-backup-$(date +%Y%m%d).tar.gz
```

### 恢复数据

```bash
# 停止服务
docker-compose down

# 恢复数据
docker run --rm -v cortex-data:/data -v $(pwd):/backup ubuntu tar xzf /backup/cortex-data-YYYYMMDD.tar.gz -C /data

# 重启服务
docker-compose up -d
```

## 网络配置

### 默认网络

所有服务运行在 `cortex-network` 桥接网络中。

### 自定义网络

如需使用外部网络或自定义网络配置，修改 `docker-compose.yml`：

```yaml
networks:
  cortex-network:
    external: true
    name: my-custom-network
```

### 端口映射

默认端口映射：
- `3000:80` - Frontend
- `8000:8000` - Monitor
- `8001:8001` - Probe

修改端口：
```bash
# 在 .env 文件中
CORTEX_MONITOR_PORT=9000
CORTEX_PROBE_PORT=9001
CORTEX_FRONTEND_PORT=8080
```

## 集群模式部署

### 一主多从架构

**Monitor 节点（主）**：
```yaml
# .env
CORTEX_AGENT_ID=monitor-main
CORTEX_AGENT_MODE=standalone
```

**Probe 节点（从）**：
```yaml
# .env
CORTEX_AGENT_ID=probe-node-01
CORTEX_AGENT_MODE=cluster
CORTEX_AGENT_UPSTREAM_MONITOR_URL=http://monitor-main:8000
```

### 多节点部署

在不同主机上部署 Probe 节点，配置 `CORTEX_AGENT_UPSTREAM_MONITOR_URL` 指向主 Monitor。

## 生产环境优化

### 1. 使用外部数据库

将 SQLite 替换为 PostgreSQL：

```yaml
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: cortex
      POSTGRES_USER: cortex
      POSTGRES_PASSWORD: changeme
    volumes:
      - postgres-data:/var/lib/postgresql/data

  cortex-monitor:
    environment:
      - CORTEX_MONITOR_DATABASE_URL=postgresql://cortex:changeme@postgres:5432/cortex
    depends_on:
      - postgres
```

### 2. 使用 Redis 缓存（未来）

```yaml
services:
  redis:
    image: redis:7-alpine
    volumes:
      - redis-data:/data

  cortex-monitor:
    environment:
      - CORTEX_CACHE_BACKEND=redis
      - CORTEX_CACHE_REDIS_URL=redis://redis:6379/0
```

### 3. 启用 HTTPS

使用 Traefik 或 Nginx 作为反向代理：

```yaml
services:
  traefik:
    image: traefik:v2.10
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./traefik.yml:/traefik.yml
      - ./acme.json:/acme.json
```

### 4. 资源限制

```yaml
services:
  cortex-monitor:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
```

### 5. 日志管理

```yaml
services:
  cortex-monitor:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

## 故障排查

### 服务无法启动

```bash
# 查看详细日志
docker-compose logs cortex-monitor

# 检查容器状态
docker-compose ps

# 进入容器调试
docker-compose exec cortex-monitor bash
```

### 数据库连接失败

```bash
# 检查数据库文件权限
docker-compose exec cortex-monitor ls -la /app/data/

# 手动创建数据库
docker-compose exec cortex-monitor python -c "from cortex.monitor.database import init_db; init_db()"
```

### 网络问题

```bash
# 检查网络
docker network ls
docker network inspect cortex-network

# 测试容器间连接
docker-compose exec cortex-probe curl http://cortex-monitor:8000/health
```

### 端口冲突

```bash
# 检查端口占用
netstat -tuln | grep -E ':(8000|8001|3000)'

# 修改端口（在 .env 中）
CORTEX_MONITOR_PORT=9000
```

## 监控和告警

### Prometheus 监控（未来功能）

```yaml
services:
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana
    ports:
      - "3001:3000"
```

### 健康检查

```bash
# 检查所有服务健康状态
docker-compose exec cortex-monitor curl http://localhost:8000/health
docker-compose exec cortex-probe curl http://localhost:8001/health
docker-compose exec cortex-frontend wget -qO- http://localhost/health
```

## 安全建议

1. **更改默认密钥**：
   - `CORTEX_MONITOR_REGISTRATION_TOKEN`
   - `CORTEX_AUTH_SECRET_KEY`

2. **限制网络访问**：
   ```yaml
   services:
     cortex-monitor:
       ports:
         - "127.0.0.1:8000:8000"  # 只监听本地
   ```

3. **使用密钥管理**：
   - 使用 Docker Secrets
   - 使用环境变量注入
   - 避免在 git 中提交敏感信息

4. **定期更新**：
   ```bash
   docker-compose pull
   docker-compose up -d
   ```

5. **最小权限原则**：
   - 容器以非 root 用户运行
   - 只暴露必要的端口
   - 使用只读卷挂载

## 参考资料

- [Docker 官方文档](https://docs.docker.com/)
- [Docker Compose 文档](https://docs.docker.com/compose/)
- [Cortex 配置参考](./CONFIGURATION.md)
- [Cortex API 文档](http://localhost:8000/docs)
