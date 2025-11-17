# Cortex Frontend UI Test Suite

**目的**: 每次修改前端代码后，运行此测试套件验证所有功能正常工作

## 前置条件

1. **启动后端服务**:
   - Monitor API 运行在 http://localhost:18000
   - Probe API 运行在 http://localhost:18001

2. **启动前端开发服务器**:
   ```bash
   cd frontend
   npm run dev
   ```

3. **使用 Playwright 进行测试**

## 测试用例

### 1. Dashboard 页面测试

**URL**: http://localhost:5173/

**测试步骤**:
1. 导航到 Dashboard
2. 验证页面标题显示 "Cluster Dashboard"
3. 验证四个统计卡片:
   - Total Nodes: 应显示实际节点数量（非 0）
   - Online: 显示在线节点数
   - Offline: 显示离线节点数
   - Degraded: 显示降级节点数
4. 验证 "Recent Alerts" 表格加载（可能显示 "No data"）
5. 验证 "Cluster Topology" 卡片显示:
   - Total nodes: 应显示实际数量
   - Hierarchy levels: 应显示层级数

**预期结果**: 所有统计数字正确反映实际数据

---

### 2. Nodes 页面测试

**URL**: http://localhost:5173/nodes

**测试步骤**:
1. 点击侧边栏 "Nodes" 菜单
2. 验证页面标题显示 "Cluster Nodes"
3. 验证节点列表表格显示:
   - ID 列
   - Name 列
   - Status 列（带颜色标签）
   - Parent ID 列
   - Last Heartbeat 列
   - Actions 列（View Details 链接）
4. 点击任意节点的 "View Details" 链接
5. 验证跳转到节点详情页

**预期结果**: 节点列表正确显示所有注册节点

---

### 3. Node Details 页面测试

**URL**: http://localhost:5173/nodes/{node_id}

**测试步骤**:
1. 从 Nodes 页面点击任意节点
2. 验证 "Basic Information" 表格显示:
   - ID
   - Name
   - Status (带颜色标签)
   - Health Status
   - Parent ID
   - Upstream Monitor
   - Last Heartbeat
   - Created At
3. 验证三个标签页:
   - Alerts (0) - 点击验证显示 "No alerts for this node"
   - Inspection Reports - 点击验证显示 "Coming soon..."
   - Metrics - 点击验证显示 "Coming soon..."
4. 点击 "Back to Nodes" 按钮
5. 验证返回到 Nodes 列表页

**预期结果**: 节点详情正确显示，标签页切换正常

---

### 4. Alerts 页面测试

**URL**: http://localhost:5173/alerts

**测试步骤**:
1. 点击侧边栏 "Alerts" 菜单
2. 验证页面标题显示 "Alert Center"
3. 验证两个筛选器:
   - Filter by Level: 下拉菜单（All, L1, L2, L3）
   - Filter by Status: 下拉菜单（All, new, acknowledged, resolved）
4. 验证告警表格显示列:
   - Level
   - Title
   - Description
   - Agent
   - Status
   - Created
   - Updated
5. 验证表格显示 "No data" 或实际告警数据

**预期结果**: 告警页面加载正常，筛选器可用

---

### 5. Settings 页面测试

**URL**: http://localhost:5173/settings

**测试步骤**:
1. 点击侧边栏 "Settings" 菜单
2. 验证页面标题显示 "Settings"
3. 验证 "API Configuration" 部分显示:
   - Monitor API URL: http://localhost:18000
   - Probe API URL: http://localhost:18001
4. 验证 "Application Info" 部分显示:
   - Version: 0.1.0 (Phase 3 - Web UI)
   - Build: Development
5. 验证 "About" 部分显示项目描述

**预期结果**: 设置页面正确显示配置信息

---

### 6. 导航测试

**测试步骤**:
1. 从 Dashboard 点击 "Nodes" → 验证 URL 变为 `/nodes`
2. 从 Nodes 点击 "Alerts" → 验证 URL 变为 `/alerts`
3. 从 Alerts 点击 "Settings" → 验证 URL 变为 `/settings`
4. 从 Settings 点击 "Dashboard" → 验证 URL 变为 `/`
5. 验证侧边栏高亮当前激活菜单项

**预期结果**: 所有导航链接工作正常

---

### 7. 浏览器控制台检查

**测试步骤**:
1. 打开浏览器开发者工具 (F12)
2. 切换到 Console 标签
3. 导航所有页面
4. 检查是否有 JavaScript 错误

**预期结果**:
- ✅ 允许: React Router 未来标志警告（橙色）
- ✅ 允许: React DevTools 提示（蓝色）
- ❌ 不允许: 任何红色错误信息

---

## Playwright 自动化测试脚本示例

```typescript
import { test, expect } from '@playwright/test';

test.describe('Cortex Frontend UI Tests', () => {
  test.beforeEach(async ({ page }) => {
    // 导航到主页
    await page.goto('http://localhost:5173/');
  });

  test('Dashboard shows correct statistics', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Cluster Dashboard' })).toBeVisible();

    // 验证统计数字不为 0
    const totalNodes = page.getByText('Total Nodes').locator('..').getByText(/\d+/);
    await expect(totalNodes).not.toHaveText('0');
  });

  test('Navigation works correctly', async ({ page }) => {
    // 测试导航到 Nodes
    await page.getByRole('link', { name: 'Nodes' }).click();
    await expect(page).toHaveURL(/.*\/nodes/);
    await expect(page.getByRole('heading', { name: 'Cluster Nodes' })).toBeVisible();

    // 测试导航到 Alerts
    await page.getByRole('link', { name: 'Alerts' }).click();
    await expect(page).toHaveURL(/.*\/alerts/);
    await expect(page.getByRole('heading', { name: 'Alert Center' })).toBeVisible();

    // 测试导航到 Settings
    await page.getByRole('link', { name: 'Settings' }).click();
    await expect(page).toHaveURL(/.*\/settings/);
    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();

    // 返回 Dashboard
    await page.getByRole('link', { name: 'Dashboard' }).click();
    await expect(page).toHaveURL('http://localhost:5173/');
  });

  test('Node details page loads', async ({ page }) => {
    await page.getByRole('link', { name: 'Nodes' }).click();

    // 点击第一个节点的链接
    await page.locator('table tbody tr').first().getByRole('link').first().click();

    // 验证节点详情页加载
    await expect(page.getByRole('heading', { name: 'Node Details' })).toBeVisible();
    await expect(page.getByText('Basic Information')).toBeVisible();

    // 测试标签页切换
    await page.getByRole('tab', { name: 'Inspection Reports' }).click();
    await expect(page.getByText('Coming soon...')).toBeVisible();

    await page.getByRole('tab', { name: 'Metrics' }).click();
    await expect(page.getByText('Coming soon...')).toBeVisible();
  });

  test('No console errors', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    // 访问所有页面
    await page.goto('http://localhost:5173/');
    await page.getByRole('link', { name: 'Nodes' }).click();
    await page.getByRole('link', { name: 'Alerts' }).click();
    await page.getByRole('link', { name: 'Settings' }).click();

    // 验证没有错误
    expect(errors).toHaveLength(0);
  });
});
```

## 测试报告模板

```markdown
## UI 测试报告 - {日期}

### 测试环境
- Frontend: http://localhost:5173/
- Monitor API: http://localhost:18000
- Probe API: http://localhost:18001
- Browser: Chrome/Firefox
- Tester: {姓名}

### 测试结果

| 测试用例 | 状态 | 备注 |
|---------|------|------|
| Dashboard 页面 | ✅ PASS | 统计数据正确显示 |
| Nodes 页面 | ✅ PASS | 显示 7 个节点 |
| Node Details 页面 | ✅ PASS | 详情加载正常 |
| Alerts 页面 | ✅ PASS | 筛选器工作正常 |
| Settings 页面 | ✅ PASS | 配置显示正确 |
| 导航测试 | ✅ PASS | 所有链接正常 |
| 控制台检查 | ✅ PASS | 无错误 |

### 发现的问题
- 无

### 截图
- dashboard.png
- nodes.png
- alerts.png
- settings.png
```

## 回归测试清单

每次修改后，按此顺序快速回归:

1. ✅ 启动所有服务
2. ✅ 访问 Dashboard - 验证统计数据
3. ✅ 访问 Nodes - 验证列表显示
4. ✅ 打开一个节点详情 - 验证详情页
5. ✅ 访问 Alerts - 验证页面加载
6. ✅ 访问 Settings - 验证配置显示
7. ✅ 检查浏览器控制台 - 无红色错误

**预计时间**: 2-3 分钟
