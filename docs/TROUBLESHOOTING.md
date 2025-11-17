# Cortex 故障排查指南

本文档提供常见问题的诊断和解决方法。

## 快速诊断清单

遇到问题时，按以下顺序检查：

1. ✅ **检查服务状态**：服务是否正常运行？
2. ✅ **检查日志**：最近的错误信息是什么？
3. ✅ **检查配置**：配置是否正确？
4. ✅ **检查网络**：服务间是否可以通信？
5. ✅ **检查资源**：CPU/内存/磁盘是否充足？

## 服务启动问题

### 问题：Monitor 无法启动

#### 症状
```bash
$ docker-compose up cortex-monitor
# 或
$ sudo systemctl start cortex-monitor
# 服务立即退出或报错
```

#### 诊断步骤

**1. 查看日志**
```bash
# Docker
docker-compose logs cortex-monitor

# systemd
sudo journalctl -u cortex-monitor -n 50

# 直接运行查看详细错误
python -m cortex.monitor.cli --log-level DEBUG
```

**2. 常见原因和解决方法**

##### 原因A: 端口被占用
```bash
# 检查端口占用
sudo netstat -tuln | grep 8000
# 或
sudo lsof -i :8000
```

**解决方法**：
- 停止占用端口的进程
- 或修改配置使用其他端口：
  ```yaml
  monitor:
    port: 8080  # 改用其他端口
  ```

##### 原因B: 数据库文件权限错误
```bash
# 检查数据库文件权限
ls -la cortex.db
```

**解决方法**：
```bash
# 修复权限
chmod 644 cortex.db
chown cortex:cortex cortex.db  # 如果使用 systemd

# Docker 环境
docker exec cortex-monitor chown cortex:cortex /app/data/cortex.db
```

##### 原因C: 配置文件错误
```bash
# 验证 .env 文件是否存在
ls -la .env

# 测试配置加载
python3 -c "from cortex.config.settings import get_settings; print(get_settings())"
```

**解决方法**：
- 确保 `.env` 文件存在（复制 `.env.example`）
- 检查环境变量格式（KEY=VALUE，无空格）
- 确保必需字段已配置（ANTHROPIC_API_KEY 等）
- 参考 [配置文档](./CONFIGURATION.md)

##### 原因D: Python 依赖缺失
```bash
# 检查依赖
pip list | grep -E "fastapi|uvicorn|sqlalchemy"
```

**解决方法**：
```bash
# 重新安装依赖
pip install -e .
# 或
pip install -r requirements.txt
```

### 问题：Probe 无法启动

#### 症状
Probe 服务启动失败或反复重启

#### 诊断步骤

**1. 查看错误信息**
```bash
docker-compose logs cortex-probe
# 或
sudo journalctl -u cortex-probe -n 50
```

**2. 常见原因和解决方法**

##### 原因A: Claude API Key 无效
```
Error: Invalid API key
```

**解决方法**：
```bash
# 验证 API Key
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-sonnet-4",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "Hello"}]
  }'

# 更新 API Key
export ANTHROPIC_API_KEY=sk-ant-your-valid-key
# 或在 .env 中更新
```

##### 原因B: Workspace 目录不存在
```
Error: No such file or directory: './probe_workspace'
```

**解决方法**：
```bash
# 创建 workspace 目录
mkdir -p probe_workspace/output

# Docker 环境检查卷挂载
docker-compose config | grep -A 5 volumes
```

##### 原因C: Claude Code CLI 未安装
```
Error: claude command not found
```

**解决方法**：
```bash
# 检查 claude 命令
which claude
claude --version

# 如果未安装，参考：https://claude.com/code
```

## 集群通信问题

### 问题：Probe 无法注册到 Monitor

#### 症状
```
Error: Failed to register with upstream monitor
```

#### 诊断步骤

**1. 检查 Monitor 是否可访问**
```bash
# 从 Probe 所在主机测试
curl http://monitor.example.com:8000/health

# Docker 环境测试容器间网络
docker exec cortex-probe curl http://cortex-monitor:8000/health
```

**2. 检查配置**
```bash
# 验证 upstream_monitor_url
echo $CORTEX_AGENT_UPSTREAM_MONITOR_URL

# 验证 registration_token 是否匹配
# Probe 和 Monitor 的 token 必须一致
```

**3. 常见原因和解决方法**

##### 原因A: URL 配置错误
```yaml
# ❌ 错误
upstream_monitor_url: "monitor:8000"  # 缺少协议

# ✅ 正确
upstream_monitor_url: "http://monitor:8000"
```

##### 原因B: Token 不匹配
```bash
# Monitor 配置
CORTEX_MONITOR_REGISTRATION_TOKEN=token-abc123

# Probe 配置（必须相同）
CORTEX_MONITOR_REGISTRATION_TOKEN=token-abc123
```

##### 原因C: 防火墙阻止
```bash
# 检查防火墙规则
sudo iptables -L -n | grep 8000

# 临时允许（测试用）
sudo iptables -I INPUT -p tcp --dport 8000 -j ACCEPT

# 永久配置（Ubuntu/Debian）
sudo ufw allow 8000/tcp
```

##### 原因D: Docker 网络隔离
```bash
# 检查容器网络
docker network inspect cortex-network

# 确保 Probe 和 Monitor 在同一网络
docker-compose ps
```

**解决方法**：
```yaml
# 确保所有服务在同一网络
networks:
  cortex-network:
    driver: bridge
```

### 问题：心跳超时，节点离线

#### 症状
Monitor UI 显示 Probe 状态为 "Offline" 或 "Unknown"

#### 诊断步骤

**1. 检查 Probe 是否运行**
```bash
# Docker
docker-compose ps cortex-probe

# systemd
sudo systemctl status cortex-probe
```

**2. 检查心跳发送**
```bash
# 查看 Probe 日志中的心跳记录
docker-compose logs cortex-probe | grep -i heartbeat
```

**3. 检查网络延迟**
```bash
# 测试往返延迟
ping -c 5 monitor.example.com

# 测试 HTTP 延迟
time curl -s http://monitor.example.com:8000/health
```

**4. 解决方法**

如果网络延迟过高，调整心跳超时时间（需要修改代码）：
```python
# cortex/monitor/models.py
HEARTBEAT_TIMEOUT = timedelta(minutes=10)  # 增加到 10 分钟
```

## 巡检问题

### 问题：巡检任务不执行

#### 症状
Probe 正常运行，但从不执行巡检

#### 诊断步骤

**1. 检查调度配置**
```bash
# 查看当前调度设置
curl http://localhost:8001/schedule

# 输出示例：
# {"schedule": "0 * * * *", "enabled": true, "next_run": "2024-01-01 15:00:00"}
```

**2. 检查 Cron 表达式**
```bash
# 验证 Cron 表达式（使用在线工具）
# https://crontab.guru/#0_*_*_*_*
```

**3. 常见原因和解决方法**

##### 原因A: 调度器未启动
```bash
# 查看日志
docker-compose logs cortex-probe | grep -i scheduler
```

**解决方法**：重启 Probe 服务

##### 原因B: Cron 表达式错误
```yaml
# ❌ 错误：6 字段 Cron（不支持）
schedule: "0 0 * * * *"

# ✅ 正确：5 字段 Cron
schedule: "0 * * * *"
```

##### 原因C: 时区问题
```bash
# 检查容器时区
docker exec cortex-probe date
docker exec cortex-probe cat /etc/timezone

# 设置时区环境变量
environment:
  - TZ=Asia/Shanghai
```

### 问题：巡检执行超时

#### 症状
```
Error: Inspection execution timed out after 300 seconds
```

#### 解决方法

增加超时时间：
```yaml
probe:
  timeout_seconds: 600  # 增加到 10 分钟
```

或优化巡检脚本，减少执行时间。

### 问题：巡检报告解析失败

#### 症状
```
Error: Failed to parse inspection report
```

#### 诊断步骤

**1. 查看原始输出**
```bash
# 查看 workspace/output 目录
ls -la probe_workspace/output/

# 查看最新报告
cat probe_workspace/output/report-*.json
```

**2. 手动执行测试**
```bash
# 进入容器手动执行
docker exec -it cortex-probe bash
cd /app/probe_workspace
claude -p
```

**3. 解决方法**

- 检查 Claude API 响应
- 验证输出 JSON 格式
- 查看 Claude 输出日志

## 数据库问题

### 问题：SQLite 数据库损坏

#### 症状
```
Error: database disk image is malformed
```

#### 解决方法

**1. 备份当前数据库**
```bash
cp cortex.db cortex.db.backup
```

**2. 尝试修复**
```bash
# 使用 SQLite 命令修复
sqlite3 cortex.db "PRAGMA integrity_check;"

# 如果损坏严重，导出再导入
sqlite3 cortex.db .dump > backup.sql
rm cortex.db
sqlite3 cortex.db < backup.sql
```

**3. 如果无法修复，重建数据库**
```bash
# ⚠️ 警告：会丢失所有数据
rm cortex.db
# 重启服务会自动创建新数据库
docker-compose restart cortex-monitor
```

### 问题：PostgreSQL 连接失败

#### 症状
```
Error: could not connect to server: Connection refused
```

#### 诊断步骤

**1. 检查 PostgreSQL 是否运行**
```bash
# Docker
docker-compose ps postgres

# systemd
sudo systemctl status postgresql
```

**2. 检查连接字符串**
```bash
echo $CORTEX_MONITOR_DATABASE_URL
# 应该类似：postgresql://user:pass@host:5432/dbname
```

**3. 测试连接**
```bash
psql "postgresql://cortex:password@localhost:5432/cortex" -c "SELECT 1;"
```

**4. 解决方法**

- 确保 PostgreSQL 运行
- 验证用户名、密码、数据库名
- 检查防火墙规则
- 确保 pg_hba.conf 允许连接

## API 问题

### 问题：API 返回 401 Unauthorized

#### 症状
```bash
$ curl http://localhost:8000/api/v1/agents
{"detail": "Not authenticated"}
```

#### 解决方法

**1. 获取 Access Token**
```bash
# 登录获取 token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}'

# 响应：
# {"access_token": "eyJ...", "token_type": "bearer"}
```

**2. 使用 Token 访问 API**
```bash
TOKEN="eyJ..."
curl http://localhost:8000/api/v1/agents \
  -H "Authorization: Bearer $TOKEN"
```

### 问题：API 返回 500 Internal Server Error

#### 诊断步骤

**1. 查看详细错误**
```bash
# 查看 Monitor 日志
docker-compose logs cortex-monitor | tail -50
```

**2. 常见原因**

- 数据库连接失败
- Python 代码异常
- 配置错误

**3. 调试模式**
```bash
# 启用 DEBUG 日志
export CORTEX_LOG_LEVEL=DEBUG
docker-compose restart cortex-monitor
```

## 性能问题

### 问题：API 响应慢

#### 诊断步骤

**1. 测试响应时间**
```bash
# 测试 API 延迟
time curl -s http://localhost:8000/api/v1/agents > /dev/null
```

**2. 查看慢查询**
```bash
# 启用查询日志（如使用 PostgreSQL）
# 在 postgresql.conf 中：
log_min_duration_statement = 100  # 记录超过 100ms 的查询
```

**3. 解决方法**

##### 数据库优化
```sql
-- 添加索引
CREATE INDEX idx_reports_agent_id ON reports(agent_id);
CREATE INDEX idx_reports_created_at ON reports(created_at);
```

##### 启用缓存
```yaml
# 使用 Redis 缓存（未来功能）
performance:
  cache:
    enabled: true
    backend: "redis"
    redis_url: "redis://localhost:6379/0"
```

##### 清理旧数据
```bash
# 删除旧报告
curl -X DELETE http://localhost:8000/api/v1/reports?older_than=90days
```

### 问题：内存使用过高

#### 诊断步骤

**1. 检查内存使用**
```bash
# Docker 环境
docker stats cortex-monitor cortex-probe

# 系统环境
top -p $(pgrep -f cortex)
```

**2. 解决方法**

##### 限制容器内存
```yaml
services:
  cortex-monitor:
    deploy:
      resources:
        limits:
          memory: 2G
```

##### 调整 Python 垃圾回收
```bash
# 添加环境变量
environment:
  - PYTHONMALLOC=malloc
  - PYTHONASYNCIODEBUG=1
```

## Web UI 问题

### 问题：前端无法连接后端

#### 症状
浏览器控制台显示：
```
Failed to fetch: ERR_CONNECTION_REFUSED
```

#### 诊断步骤

**1. 检查 API 地址配置**
```javascript
// frontend/.env
VITE_API_BASE_URL=http://localhost:8000
```

**2. 检查 CORS 配置**
```python
# cortex/monitor/app.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境允许所有源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**3. 测试 API 可访问性**
```bash
curl http://localhost:8000/health
```

### 问题：WebSocket 连接失败

#### 症状
```
WebSocket connection failed: Error during WebSocket handshake
```

#### 解决方法

**1. 检查 WebSocket 路径**
```javascript
// 确保使用正确的 WebSocket URL
const ws = new WebSocket('ws://localhost:8000/ws');
```

**2. 如果使用 nginx 反向代理**
```nginx
location /ws {
    proxy_pass http://backend;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "Upgrade";
}
```

## 日志问题

### 问题：日志文件过大

#### 解决方法

**1. 调整轮转策略**
```yaml
logging:
  rotation: "10 MB"  # 减小文件大小
  retention: "7 days"  # 减少保留时间
```

**2. 手动清理**
```bash
# 清理旧日志
find logs/ -name "*.log.*" -mtime +7 -delete
```

### 问题：找不到日志

#### 诊断步骤

**1. 检查日志配置**
```yaml
logging:
  file: "logs/cortex.log"  # 确认路径
```

**2. 检查目录权限**
```bash
ls -la logs/
# 应该对 cortex 用户可写
```

**3. 查看 stderr**
```bash
# Docker
docker-compose logs cortex-monitor

# systemd
sudo journalctl -u cortex-monitor
```

## 获取帮助

### 收集诊断信息

在报告问题时，请提供：

```bash
# 1. 版本信息
docker --version
docker-compose --version
python --version

# 2. 服务状态
docker-compose ps

# 3. 最近日志
docker-compose logs --tail=100 > logs.txt

# 4. 配置信息（移除敏感信息）
cat .env | grep -v -E "API_KEY|TOKEN|PASSWORD|SECRET" > env-sanitized.txt

# 5. 系统信息
uname -a
df -h
free -h
```

### 联系方式

- 🐛 GitHub Issues: https://github.com/yourusername/cortex/issues
- 💬 Discussions: https://github.com/yourusername/cortex/discussions
- 📧 Email: support@example.com

### 相关文档

- [安装指南](./INSTALLATION.md)
- [配置参考](./CONFIGURATION.md)
- [Docker 部署](./DOCKER_DEPLOYMENT.md)
- [API 文档](http://localhost:8000/docs)
