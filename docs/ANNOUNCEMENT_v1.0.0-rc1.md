# 📢 Cortex v1.0.0-rc1 发布公告

## 🎉 正式发布

我们很高兴地宣布 **Cortex v1.0.0-rc1** 正式发布！

Cortex 是一个创新的智能运维系统，通过 AI 驱动实现自主决策和自动修复，让运维工作更智能、更高效。

### 🔗 立即体验

**GitHub Release**: https://github.com/wayfind/Cortex/releases/tag/v1.0.0-rc1

```bash
# 快速开始
git clone https://github.com/wayfind/Cortex.git
cd Cortex
git checkout v1.0.0-rc1
docker-compose up -d
```

---

## ✨ 核心特性

### 🤖 AI 驱动的智能运维
- **L1 自主修复**: 无需批准自动处理常见问题
- **L2 智能决策**: Claude AI 分析风险并批准操作
- **L3 智能告警**: 聚合、去重和关联分析

### 🌐 灵活的集群架构
- **多层嵌套**: 支持无限层级的集群拓扑
- **自动注册**: 节点自动加入集群
- **心跳检测**: 5分钟超时自动故障转移

### 📊 完整的操作追溯
- **Intent-Engine**: 记录每个决策和操作
- **完整审计**: 从创建到完成的全生命周期
- **统计分析**: 按类型、级别、时间查询

### 🎨 现代化 Web 界面
- React + TypeScript 构建
- 实时 WebSocket 更新
- 响应式设计，支持深色模式

---

## 📊 质量保证

- ✅ **196 个测试全部通过**
- ✅ **61% 代码覆盖率** (核心模块 >80%)
- ✅ **10 个 E2E 集成测试场景**
- ✅ **完整文档套件** (15 个文档)

---

## 🚀 部署方式

### Docker 一键部署（推荐）
```bash
docker-compose up -d
```

### 传统安装
```bash
pip install -r requirements.txt
python -m cortex.monitor.app
```

### systemd 服务
```bash
sudo systemctl start cortex-monitor
sudo systemctl start cortex-probe
```

---

## 📚 文档资源

- **快速开始**: [QUICK_START_GUIDE.md](./QUICK_START_GUIDE.md)
- **发布说明**: [RELEASE_NOTES.md](../RELEASE_NOTES.md)
- **架构设计**: [ARCHITECTURE_UPDATE.md](./ARCHITECTURE_UPDATE.md)
- **Docker 部署**: [DOCKER_DEPLOYMENT.md](./DOCKER_DEPLOYMENT.md)
- **故障排查**: [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)

---

## 🎯 使用场景

Cortex 适用于以下场景：

1. **中小型团队**: 减少运维人力投入
2. **混合云环境**: 统一管理多个数据中心
3. **边缘计算**: 分布式节点自主管理
4. **DevOps 自动化**: AI 增强的 CI/CD 流程

---

## 🔮 v1.1.0 预告

下一版本 (2025-12-15) 将带来：

- 🧪 **更高测试覆盖率** (75%+)
- 📊 **Prometheus + Grafana 集成**
- 🔐 **增强的认证授权测试**
- ⚡ **性能优化和代码质量提升**

---

## 💬 社区支持

- **GitHub Issues**: https://github.com/wayfind/Cortex/issues
- **文档**: https://github.com/wayfind/Cortex/tree/master/docs
- **API 文档**: http://localhost:8000/docs (部署后)

---

## 🙏 致谢

感谢所有为 Cortex 做出贡献的开发者、测试者和早期用户！

特别感谢：
- Anthropic 提供的 Claude API
- FastAPI、React、SQLAlchemy 社区
- 所有提供反馈的用户

---

## 📝 关于 Cortex

Cortex 是一个开源的去中心化智能运维平台，旨在通过 AI 技术让运维工作更智能、更高效。每个节点都是独立的 Agent，可以组合成强大的集群网络。

**项目地址**: https://github.com/wayfind/Cortex
**许可证**: MIT
**版本**: v1.0.0-rc1 (Release Candidate)

---

**立即开始你的 AI 运维之旅！** 🚀

*2025-11-17 | Cortex Team*
