# Cortex v1.0.0-rc1.1 Hotfix

**发布日期**: 2025-11-17
**类型**: Hotfix (兼容性修复)
**基于**: v1.0.0-rc1

---

## 🐛 修复的问题

### Python 3.10 兼容性问题

**问题描述**：
v1.0.0-rc1 使用了 `datetime.UTC`，这是 Python 3.11+ 才引入的特性，导致在 Python 3.10 环境下无法运行。

**错误信息**：
```python
ImportError: cannot import name 'UTC' from 'datetime'
```

**影响范围**：
- 所有使用 Python 3.10 的部署环境
- 无法导入 `cortex.monitor.auth` 等模块
- 无法运行 `scripts/init_auth.py`

---

## ✅ 修复内容

### 1. 替换 datetime.UTC → timezone.utc

**修改前**：
```python
from datetime import datetime, timedelta, UTC

expire = datetime.now(UTC) + timedelta(minutes=30)
```

**修改后**：
```python
from datetime import datetime, timedelta, timezone

expire = datetime.now(timezone.utc) + timedelta(minutes=30)
```

### 2. 替换 datetime.utcnow() → datetime.now(timezone.utc)

**修改前**：
```python
timestamp = datetime.utcnow()
```

**修改后**：
```python
timestamp = datetime.now(timezone.utc)
```

---

## 📊 修改统计

- **修改文件数**: 24
- **修改位置数**: 98
- **覆盖范围**: cortex/ 和 tests/

### 主要修改文件

**核心模块**：
- cortex/monitor/auth.py
- cortex/common/cache.py
- cortex/monitor/websocket_manager.py
- cortex/probe/app.py
- cortex/probe/claude_executor.py

**路由模块**：
- cortex/monitor/routers/*.py (7 个文件)

**服务模块**：
- cortex/monitor/services/*.py (2 个文件)

**测试**：
- tests/*.py (6 个文件)

---

## 🔧 修复工具

新增自动化修复脚本：`scripts/fix_python310_compat.py`

**用途**：
- 自动扫描并修复 Python 3.10 兼容性问题
- 替换 `datetime.UTC` 为 `timezone.utc`
- 替换 `datetime.utcnow()` 为 `datetime.now(timezone.utc)`

**使用方法**：
```bash
python3 scripts/fix_python310_compat.py
```

---

## 📝 文档更新

### README.md
- Python 版本要求：`3.11+` → `3.10+`
- 徽章更新：Python 3.11+ → Python 3.10+

### QUICK_START_GUIDE.md
- 最低 Python 版本：3.10

---

## 🚀 升级指南

### 对于现有 v1.0.0-rc1 用户

如果您已经使用 Python 3.11+ 部署，**无需任何操作**，系统将继续正常工作。

如果您使用 Python 3.10，请更新代码：

```bash
# 1. 拉取最新代码
git pull origin master

# 或者直接 checkout hotfix commit
git checkout 2d9b775

# 2. 重启服务
docker-compose restart
# 或
sudo systemctl restart cortex-monitor cortex-probe
```

### 对于新用户

直接使用最新代码即可，已包含此修复。

---

## ✅ 验证

### 测试导入

```bash
python3 -c "from cortex.monitor.auth import generate_api_key; print('✅ OK')"
```

### 运行初始化脚本

```bash
python3 scripts/init_auth.py
```

应该不再出现 ImportError。

---

## 🎯 支持的 Python 版本

| 版本 | 支持状态 | 说明 |
|------|---------|------|
| Python 3.9 | ❌ 不支持 | 太旧，缺少部分特性 |
| Python 3.10 | ✅ 支持 | 最低要求版本 |
| Python 3.11 | ✅ 支持 | 推荐版本 |
| Python 3.12 | ✅ 支持 | 最新稳定版 |

---

## 📞 问题反馈

如果您在升级后遇到任何问题，请：

1. 检查 Python 版本：`python3 --version`
2. 重新安装依赖：`pip install -r requirements.txt`
3. 查看日志：`docker-compose logs` 或 `journalctl -u cortex-monitor`
4. 提交 Issue：https://github.com/wayfind/Cortex/issues

---

## 📋 完整变更列表

**Commit**: 2d9b775
**Message**: fix: Python 3.10 compatibility - replace datetime.UTC with timezone.utc

**变更内容**：
- 24 个 Python 文件修复
- 98 处兼容性修改
- 1 个新增修复工具脚本
- 2 个文档更新

---

**感谢用户报告此问题！** 🙏

*Hotfix 发布: 2025-11-17*
*Cortex Team*
