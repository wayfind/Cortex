# 贡献指南

感谢您对 Cortex 项目的关注！我们欢迎各种形式的贡献。

## 如何贡献

### 报告 Bug

如果您发现了 Bug，请在 [GitHub Issues](https://github.com/cortex-ops/cortex/issues) 创建一个新的 Issue，并包含以下信息：

- Bug 的详细描述
- 复现步骤
- 预期行为和实际行为
- 环境信息（操作系统、Python 版本等）
- 相关日志或截图

### 提出新功能

如果您有新功能的想法，请先在 Issues 中讨论，确保该功能符合项目方向。

### 提交代码

1. **Fork 项目**

   点击右上角的 Fork 按钮

2. **克隆到本地**

   ```bash
   git clone https://github.com/your-username/cortex.git
   cd cortex
   ```

3. **创建分支**

   ```bash
   git checkout -b feature/your-feature-name
   ```

4. **安装开发依赖**

   ```bash
   make dev-install
   ```

5. **进行修改**

   - 遵循项目的代码风格（使用 black、ruff）
   - 添加必要的测试
   - 更新相关文档

6. **运行测试**

   ```bash
   make test
   make lint
   ```

7. **提交更改**

   ```bash
   git add .
   git commit -m "描述您的更改"
   ```

   提交信息应该清晰描述更改的内容和原因。

8. **推送到 GitHub**

   ```bash
   git push origin feature/your-feature-name
   ```

9. **创建 Pull Request**

   在 GitHub 上创建 Pull Request，并详细描述您的更改。

## 代码风格

- 使用 **Black** 进行代码格式化（行长度 100）
- 使用 **Ruff** 进行代码检查
- 使用 **mypy** 进行类型检查
- 遵循 PEP 8 规范

快捷命令：

```bash
# 格式化代码
make format

# 检查代码
make lint
```

## 测试

- 所有新功能必须包含单元测试
- 测试覆盖率应保持在 80% 以上
- 使用 pytest 编写测试

```bash
# 运行测试
make test

# 查看覆盖率报告
make test-cov
```

## 文档

- 代码应包含清晰的 docstring
- 重要功能应更新 README 和相关文档
- API 变更应更新 docs/api.md

## Commit 信息规范

建议使用以下格式：

```
<类型>: <简短描述>

<详细描述>（可选）

<Footer>（可选）
```

**类型**：
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式（不影响功能）
- `refactor`: 重构
- `test`: 测试相关
- `chore`: 构建/工具相关

**示例**：

```
feat: 添加 L2 决策引擎

实现基于 LLM 的风险分析和自动决策功能。
包括决策请求处理、LLM 集成和结果回传机制。

Closes #42
```

## Pull Request 检查清单

提交 PR 前，请确保：

- [ ] 代码已通过所有测试
- [ ] 代码风格检查通过
- [ ] 添加了必要的测试
- [ ] 更新了相关文档
- [ ] Commit 信息清晰明确
- [ ] PR 描述详细说明了更改内容

## 行为准则

- 尊重他人，保持友好和专业
- 欢迎新手，提供建设性的反馈
- 关注问题本身，而非个人

## 获取帮助

如果您有任何问题，可以：

- 在 Issues 中提问
- 查看项目文档
- 参与 Discussions

再次感谢您的贡献！
