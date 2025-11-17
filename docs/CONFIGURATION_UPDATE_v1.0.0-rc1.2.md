# Cortex 配置简化更新 (v1.0.0-rc1.2)

**更新日期**: 2025-11-17
**类型**: 文档更新 + 配置简化
**影响**: 用户体验改进，无破坏性变更

---

## 📝 更新概述

根据用户反馈，我们简化了 Cortex 的配置方式，**推荐使用 `.env` 文件作为唯一配置方式**，以提供更简洁、统一的配置体验。

> 用户反馈: "我看到安装文档里还在让用config.yaml，配置文件留一个.env是不是就够了"

---

## ✨ 主要变更

### 1. 配置方式简化

**之前**：文档中同时介绍两种配置方式
- 环境变量配置（推荐）
- YAML 配置文件

**现在**：统一推荐使用 `.env` 文件
- ✅ 单一配置方式，降低学习成本
- ✅ 完美兼容 Docker 和传统部署
- ✅ 符合 12-Factor App 最佳实践
- ✅ 避免敏感信息误提交到 Git

### 2. YAML 配置状态

**重要说明**：
- `config.yaml` 仍然被代码支持（向后兼容）
- 但标记为 **已弃用**，未来版本可能移除
- 文档中不再主推 YAML 配置
- 建议所有用户迁移到 `.env` 配置

### 3. Python 版本要求更新

同时更新了 Python 版本要求（基于之前的 Python 3.10 兼容性修复）：

| 项目 | 之前 | 现在 |
|------|------|------|
| Python 最低版本 | 3.11+ | 3.10+ |
| 推荐版本 | 3.11 | 3.11 |

---

## 📄 更新的文档

### 主要文档
1. **README.md**
   - 移除 YAML 配置章节
   - 简化为单一 `.env` 配置说明
   - 更新 Python 版本徽章

2. **docs/QUICK_START_GUIDE.md**
   - 全面替换 `config.yaml` 引用为 `.env`
   - 更新所有配置示例
   - 简化配置步骤说明
   - 更新 Python 版本要求

3. **docs/CONFIGURATION.md**
   - 标记 YAML 配置为已弃用
   - 更新配置优先级说明
   - 添加迁移建议

---

## 🔧 配置迁移指南

### 对于新用户

直接使用 `.env` 配置：

```bash
# 1. 复制环境变量模板
cp .env.example .env

# 2. 编辑配置
nano .env

# 3. 启动服务
docker-compose up -d
# 或
python -m uvicorn cortex.monitor.app:app --host 0.0.0.0 --port 8000
```

### 对于现有用户（使用 config.yaml）

**选项 1：继续使用 YAML（临时方案）**
- 无需任何操作
- 代码仍然支持 `config.yaml`
- 但建议尽快迁移

**选项 2：迁移到 .env（推荐）**

```bash
# 1. 创建 .env 文件
cp .env.example .env

# 2. 将 config.yaml 中的配置转换为环境变量
# 转换规则：
# agent.id → CORTEX_AGENT_ID
# probe.port → CORTEX_PROBE_PORT
# claude.api_key → ANTHROPIC_API_KEY
# 等等...

# 3. 测试配置
python3 -c "from cortex.config.settings import get_settings; print(get_settings())"

# 4. 删除或重命名旧配置文件（可选）
mv config.yaml config.yaml.backup
```

### 配置转换示例

**config.yaml**:
```yaml
agent:
  id: "node-001"
  name: "My Node"
  mode: "standalone"

probe:
  port: 8001
  schedule: "0 * * * *"

claude:
  api_key: "sk-ant-xxx"
  model: "claude-sonnet-4"
```

**等价的 .env**:
```bash
# Agent 配置
CORTEX_AGENT_ID=node-001
CORTEX_AGENT_NAME=My Node
CORTEX_AGENT_MODE=standalone

# Probe 配置
CORTEX_PROBE_PORT=8001
CORTEX_PROBE_SCHEDULE=0 * * * *

# Claude API
ANTHROPIC_API_KEY=sk-ant-xxx
ANTHROPIC_MODEL=claude-sonnet-4
```

---

## 🧪 测试验证

### 验证配置加载

```bash
# 测试 1: 验证配置文件读取
python3 -c "
from cortex.config.settings import get_settings
settings = get_settings()
print(f'✅ Agent ID: {settings.agent.id}')
print(f'✅ Monitor Port: {settings.monitor.port}')
print(f'✅ Probe Port: {settings.probe.port}')
"

# 测试 2: 验证初始化脚本
python3 scripts/init_auth.py

# 测试 3: 验证服务启动
# Monitor
curl http://localhost:8000/health

# Probe
curl http://localhost:8001/health
```

### 测试结果（本地验证）

```
✅ Configuration loaded successfully
✅ Agent ID: test-node-001
✅ Monitor Port: 18000
✅ Probe Port: 18001

✅ Admin user already exists
✅ Default API Key already exists
✅ Authentication system initialized successfully!

✅ Monitor health: {"status": "healthy"}
✅ Probe health: {"status": "healthy", "scheduler_running": true}
```

---

## 📊 配置方式对比

| 特性 | YAML 配置 | .env 配置 |
|------|----------|----------|
| **易用性** | 需要学习 YAML 语法 | ✅ 简单的键值对 |
| **Docker 兼容** | 需要 volume 映射 | ✅ 原生支持 |
| **CI/CD 友好** | 需要文件管理 | ✅ 环境变量注入 |
| **敏感信息保护** | ⚠️ 容易误提交 | ✅ .gitignore 保护 |
| **12-Factor App** | 不符合 | ✅ 完全符合 |
| **配置覆盖** | 复杂 | ✅ 环境变量优先 |
| **多环境管理** | 需要多个文件 | ✅ .env.dev, .env.prod |
| **当前状态** | ⚠️ 已弃用 | ✅ 推荐方式 |

---

## 🔗 相关文档

- [完整配置参考](./CONFIGURATION.md) - 所有配置项详细说明
- [快速开始指南](./QUICK_START_GUIDE.md) - 使用 .env 的部署流程
- [Python 3.10 兼容性修复](./HOTFIX_v1.0.0-rc1.1.md) - 相关的兼容性更新
- [.env.example](../.env.example) - 配置模板文件

---

## 📝 提交记录

**Commit**: dfa9b0c
**Message**: docs: Simplify configuration to use .env only, deprecate config.yaml

**变更文件**:
- README.md
- docs/QUICK_START_GUIDE.md
- docs/CONFIGURATION.md

**变更统计**:
- 3 个文件修改
- 100 行新增
- 107 行删除

---

## 💡 最佳实践

### 1. 使用 setup_env.py 脚本

自动生成安全的 `.env` 文件：

```bash
python scripts/setup_env.py
```

该脚本会：
- 复制 `.env.example` 到 `.env`
- 自动生成安全的随机密钥
- 设置合理的默认值

### 2. 不同环境使用不同配置

```bash
# 开发环境
cp .env.example .env.development

# 生产环境
cp .env.example .env.production

# 使用特定配置启动
export $(cat .env.production | xargs) && python -m uvicorn ...
```

### 3. Docker Compose 集成

```yaml
# docker-compose.yml
services:
  cortex-monitor:
    env_file:
      - .env
    environment:
      - CORTEX_MONITOR_PORT=8000
```

### 4. 安全检查

```bash
# 确保 .env 在 .gitignore 中
grep -q "^\.env$" .gitignore && echo "✅ Safe" || echo "⚠️ Add .env to .gitignore"

# 检查是否有敏感信息
grep -i "password\|secret\|key" .env
```

---

## 🎯 总结

这次更新通过简化配置方式，为用户提供了：

1. ✅ **更简单的学习曲线** - 只需了解一种配置方式
2. ✅ **更好的安全性** - 避免敏感信息泄露
3. ✅ **更强的兼容性** - 完美支持 Docker 和 CI/CD
4. ✅ **更清晰的文档** - 减少配置相关的困惑

**推荐所有用户尽快迁移到 `.env` 配置方式！**

---

## 📞 问题反馈

如果您在配置迁移过程中遇到任何问题：

1. 查看 [配置参考文档](./CONFIGURATION.md)
2. 查看 [故障排查指南](./TROUBLESHOOTING.md)
3. 提交 Issue: https://github.com/wayfind/Cortex/issues

---

*更新日期: 2025-11-17*
*Cortex Team*
