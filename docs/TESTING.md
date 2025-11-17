# Cortex 测试指南

本文档说明 Cortex 的测试框架和测试策略。

## 测试架构

Cortex 采用分层测试策略：

```
┌─────────────────────────────────────┐
│    E2E 测试（计划中）                 │
│  - 完整用户场景                       │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│    集成测试                           │
│  - API 端到端测试                     │
│  - 数据库集成测试                     │
│  - 集群通信测试                       │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│    单元测试                           │
│  - 模块功能测试                       │
│  - 业务逻辑测试                       │
│  - 工具函数测试                       │
└─────────────────────────────────────┘
```

## 测试工具

- **pytest**: 测试框架
- **pytest-asyncio**: 异步测试支持
- **pytest-cov**: 覆盖率报告
- **httpx**: HTTP 客户端（测试 API）
- **unittest.mock**: Mock 对象

## 运行测试

### 快速开始

```bash
# 运行所有测试
pytest

# 运行特定文件
pytest tests/common/test_cache.py

# 运行特定测试
pytest tests/common/test_cache.py::TestTTLCache::test_set_and_get

# 详细输出
pytest -v

# 显示print输出
pytest -s
```

### 覆盖率报告

```bash
# 生成覆盖率报告（终端）
pytest --cov=cortex --cov-report=term-missing

# 生成 HTML 报告
pytest --cov=cortex --cov-report=html

# 查看 HTML 报告
xdg-open htmlcov/index.html
```

### 并行测试

```bash
# 安装 pytest-xdist
pip install pytest-xdist

# 并行运行（自动检测 CPU 核心数）
pytest -n auto

# 指定进程数
pytest -n 4
```

## 测试目录结构

```
tests/
├── conftest.py              # 共享 fixtures
├── __init__.py
├── common/                  # 公共模块测试
│   ├── test_cache.py       # 缓存测试 ✅
│   ├── test_queue.py       # 队列测试
│   └── test_retry.py       # 重试测试
├── monitor/                 # Monitor 测试
│   ├── test_api.py
│   ├── test_database.py
│   ├── test_decision_engine.py
│   └── test_alert_aggregator.py
├── probe/                   # Probe 测试
│   └── test_probe_service.py
├── test_cluster_integration.py  # 集群集成测试
└── test_monitor_integration.py  # Monitor 集成测试
```

## 编写测试

### 单元测试示例

```python
# tests/common/test_example.py
import pytest
from cortex.common.example import my_function

class TestMyFunction:
    """测试 my_function 函数"""

    def test_normal_case(self):
        """测试正常情况"""
        result = my_function(10)
        assert result == 20

    def test_edge_case(self):
        """测试边界情况"""
        result = my_function(0)
        assert result == 0

    def test_error_case(self):
        """测试错误情况"""
        with pytest.raises(ValueError):
            my_function(-1)

    @pytest.mark.parametrize("input,expected", [
        (1, 2),
        (5, 10),
        (10, 20),
    ])
    def test_multiple_values(self, input, expected):
        """参数化测试"""
        assert my_function(input) == expected
```

### 异步测试示例

```python
import pytest
from cortex.common.cache import TTLCache

class TestAsyncCache:
    """测试异步缓存"""

    @pytest.mark.asyncio
    async def test_async_get_set(self):
        """测试异步获取和设置"""
        cache = TTLCache()
        await cache.set("key", "value")
        result = await cache.get("key")
        assert result == "value"

    @pytest.mark.asyncio
    async def test_async_expiration(self):
        """测试异步过期"""
        import asyncio
        cache = TTLCache(default_ttl=1)
        await cache.set("key", "value", ttl=1)
        await asyncio.sleep(1.1)
        result = await cache.get("key")
        assert result is None
```

### API 测试示例

```python
import pytest
from httpx import AsyncClient
from cortex.monitor.app import app

@pytest.mark.asyncio
async def test_health_endpoint():
    """测试健康检查端点"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

@pytest.mark.asyncio
async def test_list_agents():
    """测试列表 Agent 端点"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/agents")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
```

### 数据库测试示例

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from cortex.monitor.database import Base
from cortex.monitor.models import Agent

@pytest.fixture
async def db_session():
    """创建测试数据库会话"""
    # 使用内存数据库
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine) as session:
        yield session

    await engine.dispose()

@pytest.mark.asyncio
async def test_create_agent(db_session):
    """测试创建 Agent"""
    agent = Agent(
        id="test-001",
        name="Test Agent",
        mode="standalone"
    )
    db_session.add(agent)
    await db_session.commit()

    # 验证创建成功
    result = await db_session.get(Agent, "test-001")
    assert result is not None
    assert result.name == "Test Agent"
```

### Mock 测试示例

```python
import pytest
from unittest.mock import AsyncMock, patch
from cortex.probe.claude_executor import ClaudeExecutor

@pytest.mark.asyncio
async def test_claude_executor_with_mock():
    """使用 Mock 测试 Claude 执行器"""
    executor = ClaudeExecutor()

    # Mock subprocess 执行
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (
            b"Inspection completed successfully",
            b""
        )
        mock_process.returncode = 0
        mock_exec.return_value = mock_process

        result = await executor.execute()
        assert result["status"] == "success"
```

## Fixtures

### 共享 Fixtures (conftest.py)

```python
# tests/conftest.py
import pytest
from cortex.config import get_settings

@pytest.fixture(scope="session")
def test_settings():
    """测试配置"""
    return get_settings()

@pytest.fixture
def mock_api_key():
    """Mock API Key"""
    return "sk-ant-test-key"

@pytest.fixture
async def clean_database():
    """清理测试数据库"""
    # 测试前清理
    # ... cleanup code ...

    yield

    # 测试后清理
    # ... cleanup code ...
```

## 测试标记

使用 pytest markers 组织测试：

```python
# 标记慢速测试
@pytest.mark.slow
def test_slow_operation():
    pass

# 标记需要网络的测试
@pytest.mark.network
def test_api_call():
    pass

# 标记需要 Claude API 的测试
@pytest.mark.requires_api
def test_llm_call():
    pass

# 跳过测试
@pytest.mark.skip(reason="Not implemented yet")
def test_future_feature():
    pass

# 条件跳过
import sys
@pytest.mark.skipif(sys.platform == "win32", reason="Unix only")
def test_unix_feature():
    pass
```

运行特定标记的测试：

```bash
# 只运行快速测试
pytest -m "not slow"

# 只运行网络测试
pytest -m network

# 排除需要 API 的测试
pytest -m "not requires_api"
```

## 测试覆盖率目标

### 当前状态

```
Module                    Coverage    Target    Status
---------------------------------------------------------
cortex.common.cache       97%         >80%      ✅
cortex.monitor.database   100%        >80%      ✅
cortex.monitor.api        TBD         >80%      ⏳
cortex.probe.service      TBD         >80%      ⏳
Overall                   6%          >80%      ⏳
```

### 优先级

**P0 (关键路径)**：
- ✅ Cache 模块: 97% 覆盖率
- ✅ Database 模块: 100% 覆盖率
- ⏳ Monitor API: 目标 >80%
- ⏳ Probe Service: 目标 >80%
- ⏳ 认证模块: 目标 >90%

**P1 (重要功能)**：
- ⏳ 决策引擎: 目标 >70%
- ⏳ 告警聚合: 目标 >70%
- ⏳ WebSocket 管理: 目标 >60%

**P2 (辅助功能)**：
- ⏳ CLI 工具: 目标 >50%
- ⏳ 配置加载: 目标 >70%

## 持续集成

### GitHub Actions 配置（计划中）

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    strategy:
      matrix:
        python-version: [3.11, 3.12]

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install dependencies
      run: |
        pip install -e .
        pip install pytest pytest-cov

    - name: Run tests
      run: |
        pytest --cov=cortex --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

## 性能测试

### 基准测试

```python
# tests/benchmark/test_performance.py
import pytest
import time

def test_api_response_time():
    """测试 API 响应时间"""
    start = time.time()

    # ... make API call ...

    elapsed = time.time() - start
    assert elapsed < 0.2  # 小于 200ms
```

### 负载测试（使用 locust）

```python
# tests/load/locustfile.py
from locust import HttpUser, task, between

class CortexUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def get_agents(self):
        self.client.get("/api/v1/agents")

    @task
    def get_health(self):
        self.client.get("/health")
```

运行负载测试：

```bash
# 安装 locust
pip install locust

# 运行测试
locust -f tests/load/locustfile.py --host http://localhost:8000
```

## 最佳实践

### DO ✅

1. **一个测试一个断言**（尽可能）
   ```python
   def test_create_user():
       user = create_user("john")
       assert user.name == "john"  # 只测试一件事
   ```

2. **使用描述性的测试名称**
   ```python
   def test_user_registration_with_valid_email_succeeds():
       # 名称清楚表达测试意图
       pass
   ```

3. **使用 AAA 模式**（Arrange-Act-Assert）
   ```python
   def test_add_to_cart():
       # Arrange - 准备测试数据
       cart = Cart()
       item = Item("apple", 1.0)

       # Act - 执行操作
       cart.add(item)

       # Assert - 验证结果
       assert len(cart) == 1
   ```

4. **测试边界条件**
   ```python
   @pytest.mark.parametrize("value", [0, -1, None, "", []])
   def test_edge_cases(value):
       # 测试边界和异常情况
       pass
   ```

5. **使用 fixtures 减少重复**
   ```python
   @pytest.fixture
   def user():
       return User("john", "john@example.com")

   def test_user_name(user):
       assert user.name == "john"
   ```

### DON'T ❌

1. **避免测试间依赖**
   ```python
   # ❌ 错误：test_b 依赖 test_a
   def test_a():
       global data
       data = create_data()

   def test_b():
       assert data is not None  # 依赖 test_a
   ```

2. **避免过度 Mock**
   ```python
   # ❌ 错误：Mock 太多，测试没有意义
   with patch('module.func1'), \
        patch('module.func2'), \
        patch('module.func3'):
       # 基本上什么都没测试
       pass
   ```

3. **避免测试实现细节**
   ```python
   # ❌ 错误：测试私有方法
   def test_private_method():
       obj = MyClass()
       result = obj._private_method()  # 不应该测试私有方法
   ```

4. **避免魔法数字**
   ```python
   # ❌ 错误
   assert len(users) == 42

   # ✅ 正确
   EXPECTED_USER_COUNT = 42
   assert len(users) == EXPECTED_USER_COUNT
   ```

## 故障排查

### 测试失败

```bash
# 详细输出
pytest -v

# 显示本地变量
pytest -l

# 进入调试器
pytest --pdb

# 只运行失败的测试
pytest --lf
```

### 数据库问题

```bash
# 清理测试数据库
rm cortex_test.db cortex_intents_test.db

# 重新运行
pytest
```

### 异步测试问题

确保：
1. 使用 `@pytest.mark.asyncio`
2. 函数定义为 `async def`
3. 使用 `await` 调用异步函数

## 参考资料

- [pytest 官方文档](https://docs.pytest.org/)
- [pytest-asyncio 文档](https://pytest-asyncio.readthedocs.io/)
- [pytest-cov 文档](https://pytest-cov.readthedocs.io/)
- [Python Testing Best Practices](https://docs.python-guide.org/writing/tests/)
