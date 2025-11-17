# Cortex Probe 部署指南

本文档说明如何将 Cortex Probe 部署为 systemd 服务。

## 前置要求

- Python 3.11+
- Claude Code CLI (`claude` 命令可用)
- systemd (Linux 系统)

## 部署步骤

### 1. 创建系统用户

```bash
sudo useradd -r -s /bin/false -d /opt/cortex cortex
```

### 2. 安装应用

```bash
# 创建安装目录
sudo mkdir -p /opt/cortex
sudo chown cortex:cortex /opt/cortex

# 切换到 cortex 用户
sudo -u cortex bash

# 克隆代码
cd /opt/cortex
git clone https://github.com/yourusername/cortex.git .

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -e .
```

### 3. 配置

```bash
# 创建配置目录
sudo mkdir -p /etc/cortex

# 复制配置文件
sudo cp config.yaml.example /etc/cortex/config.yaml

# 编辑配置
sudo vim /etc/cortex/config.yaml
```

配置示例：

```yaml
agent:
  id: "probe-01"
  name: "Production Probe 01"
  mode: "cluster"
  upstream_monitor_url: "http://monitor.example.com:8000"

probe:
  host: "0.0.0.0"
  port: 8001
  schedule: "0 * * * *"  # 每小时执行一次
  timeout_seconds: 300
  workspace: "/opt/cortex/probe_workspace"
  report_retention_days: 30

monitor:
  host: "0.0.0.0"
  port: 8000
  database_url: "sqlite:////opt/cortex/data/cortex.db"
  registration_token: "your-secret-token-here"

claude:
  api_key: "${ANTHROPIC_API_KEY}"
  model: "claude-sonnet-4"
  max_tokens: 2000

telegram:
  enabled: false
  bot_token: null
  chat_id: null

logging:
  level: "INFO"
  format: "text"
  file: "/opt/cortex/logs/cortex.log"
```

### 4. 创建必要目录

```bash
sudo -u cortex mkdir -p /opt/cortex/logs
sudo -u cortex mkdir -p /opt/cortex/data
sudo -u cortex mkdir -p /opt/cortex/probe_workspace/output
```

### 5. 设置环境变量

```bash
# 创建环境文件
sudo mkdir -p /etc/cortex
sudo vim /etc/cortex/probe.env
```

内容：

```bash
ANTHROPIC_API_KEY=your-api-key-here
CORTEX_CONFIG=/etc/cortex/config.yaml
```

更新 systemd 服务文件以加载环境变量：

```ini
[Service]
EnvironmentFile=/etc/cortex/probe.env
```

### 6. 安装 systemd 服务

```bash
# 复制服务文件
sudo cp deployment/cortex-probe.service /etc/systemd/system/

# 重新加载 systemd
sudo systemctl daemon-reload

# 启用服务（开机自启）
sudo systemctl enable cortex-probe

# 启动服务
sudo systemctl start cortex-probe
```

### 7. 验证部署

```bash
# 查看服务状态
sudo systemctl status cortex-probe

# 查看日志
sudo journalctl -u cortex-probe -f

# 测试 API
curl http://localhost:8001/health
curl http://localhost:8001/status
```

## 服务管理

### 启动服务

```bash
sudo systemctl start cortex-probe
```

### 停止服务

```bash
sudo systemctl stop cortex-probe
```

### 重启服务

```bash
sudo systemctl restart cortex-probe
```

### 查看状态

```bash
sudo systemctl status cortex-probe
```

### 查看日志

```bash
# 实时日志
sudo journalctl -u cortex-probe -f

# 最近 100 行
sudo journalctl -u cortex-probe -n 100

# 今天的日志
sudo journalctl -u cortex-probe --since today
```

## 更新应用

```bash
# 停止服务
sudo systemctl stop cortex-probe

# 更新代码
sudo -u cortex bash
cd /opt/cortex
git pull
source venv/bin/activate
pip install -e .
exit

# 重启服务
sudo systemctl start cortex-probe
```

## 故障排查

### 服务无法启动

1. 检查日志：`sudo journalctl -u cortex-probe -n 50`
2. 检查配置文件：`sudo vim /etc/cortex/config.yaml`
3. 检查文件权限：`ls -la /opt/cortex`
4. 手动测试：`sudo -u cortex /opt/cortex/venv/bin/cortex-probe --config /etc/cortex/config.yaml`

### Claude 命令无法找到

确保 `claude` 命令在 PATH 中：

```bash
sudo -u cortex which claude
```

如果找不到，需要为 cortex 用户安装 Claude Code CLI。

### 权限问题

确保所有目录的所有者是 cortex：

```bash
sudo chown -R cortex:cortex /opt/cortex
```

## 监控和告警

### Prometheus Metrics

Probe 服务可以暴露 Prometheus 指标（如果启用）：

```bash
curl http://localhost:8001/metrics
```

### 健康检查

```bash
# 简单健康检查
curl http://localhost:8001/health

# 详细状态
curl http://localhost:8001/status
```

## 安全建议

1. **限制网络访问**：使用防火墙限制对 Probe 端口的访问
2. **使用 TLS**：在生产环境中使用反向代理 (nginx/caddy) 提供 HTTPS
3. **定期更新**：保持系统和依赖包更新
4. **审计日志**：定期检查日志文件
5. **环境变量**：不要在配置文件中明文存储敏感信息

## 备份

定期备份以下内容：

1. 配置文件：`/etc/cortex/config.yaml`
2. 数据库：`/opt/cortex/data/`
3. 日志：`/opt/cortex/logs/`（可选）
4. Workspace 输出：`/opt/cortex/probe_workspace/output/`

```bash
# 备份脚本示例
#!/bin/bash
BACKUP_DIR="/backup/cortex-$(date +%Y%m%d)"
mkdir -p $BACKUP_DIR
cp /etc/cortex/config.yaml $BACKUP_DIR/
cp -r /opt/cortex/data $BACKUP_DIR/
tar -czf $BACKUP_DIR.tar.gz $BACKUP_DIR
rm -rf $BACKUP_DIR
```
