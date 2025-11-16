# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

**Cortex** 是一个去中心化、分级自治的智能运维网络。每个节点都是一个独立的 Agent，但可以动态组合成强大的、具备集体智能的运维集群。

## 核心架构概念

### 统一组件：Cortex Agent

每个 Cortex Agent 都从同一份代码库部署，包含两个核心功能模块：

1. **探测功能 (Probe Function)**
   - 由 cron 定时触发
   - 使用无头 LLM (`claude -p`) 执行本地巡检
   - 执行 L1 级自主修复
   - 将 L2/L3 级问题上报给决策方（自身的 Monitor 或上级 Monitor）

2. **监控功能 (Monitor Function)**
   - 作为常驻 Web 服务进程运行
   - **数据聚合中心**：接收来自多个源的数据
     - 自身 Probe 功能的上报
     - 所有已配置的下级 Cortex Agent 的健康数据、事件日志和决策请求
   - **集群指挥官**：
     - 通过 LLM 分析下级 Agent 的 L2 决策请求
     - 将指令（批准/拒绝）回传给源 Agent
     - 聚合所有下级节点的 L3 告警，统一向人类发送通知
   - **Web UI**：多层级信息展示
     - 全局仪表盘：展示所有下级节点状态（集群视图）
     - 下钻分析：查看单个节点详细信息
     - 自身状态页面

### 运行模式

- **独立模式 (Standalone Mode)**：未配置 `upstream_monitor` 的 Agent。作为自治的根节点，直接向人类汇报。
- **集群模式 (Cluster Mode)**：`upstream_monitor_url` 指向另一个 Agent 的 Monitor。形成"一主多从"的运维集群。可以嵌套形成更复杂的网络拓扑。

### 问题分级

- **L1**：Probe 可本地自动修复的问题
- **L2**：需要 Monitor 决策批准的问题（需要风险分析）
- **L3**：严重/未知错误，需要人类介入

## 意图驱动的操作

所有重要操作都必须被封装为"意图"，由 `Intent-Engine` 进行全生命周期跟踪。这确保了：
- 所有决策和操作的完整可追溯性
- 能够审计和重放操作
- 跨 Agent 重启的上下文保存

## 核心设计原则

1. **混合智能 (Hybrid Intelligence)**：每个 Agent 都内置了执行单元 (Probe) 和决策单元 (Monitor)
2. **动态层级与集群 (Dynamic Hierarchy & Clustering)**：节点通过配置形成指挥链；上级 Monitor 聚合并指挥多个下级 Agent
3. **自主闭环 (Autonomous Loop)**：每个 Agent 在权责范围内完成"发现-分析-决策-执行-验证"的完整闭环
4. **意图可追溯 (Intent-Driven)**：Intent-Engine 跟踪所有操作的生命周期

## 开发状态

本仓库目前处于规格设计阶段。spec01.md 文档定义了完整的系统架构和工作流模式。
