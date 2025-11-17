#!/bin/bash
#
# Cortex 集成测试脚本
# 测试 Monitor + Probe 完整工作流程
#

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置
MONITOR_HOST="127.0.0.1"
MONITOR_PORT="18000"
PROBE_HOST="127.0.0.1"
PROBE_PORT="18001"
CONFIG_FILE="config.yaml"

# PID 文件
MONITOR_PID_FILE="/tmp/cortex_monitor.pid"
PROBE_PID_FILE="/tmp/cortex_probe.pid"

# 日志文件
MONITOR_LOG="/tmp/cortex_monitor_integration.log"
PROBE_LOG="/tmp/cortex_probe_integration.log"
TEST_REPORT="/tmp/cortex_integration_report.txt"

# 清理函数
cleanup() {
    echo -e "${YELLOW}Cleaning up...${NC}"

    if [ -f "$MONITOR_PID_FILE" ]; then
        MONITOR_PID=$(cat "$MONITOR_PID_FILE")
        kill "$MONITOR_PID" 2>/dev/null || true
        rm -f "$MONITOR_PID_FILE"
    fi

    if [ -f "$PROBE_PID_FILE" ]; then
        PROBE_PID=$(cat "$PROBE_PID_FILE")
        kill "$PROBE_PID" 2>/dev/null || true
        rm -f "$PROBE_PID_FILE"
    fi

    pkill -f "cortex-monitor" 2>/dev/null || true
    pkill -f "cortex-probe" 2>/dev/null || true

    echo -e "${GREEN}Cleanup complete${NC}"
}

# 错误处理
trap cleanup EXIT ERR INT TERM

# 测试结果记录
init_report() {
    echo "=====================================" > "$TEST_REPORT"
    echo "Cortex 集成测试报告" >> "$TEST_REPORT"
    echo "测试时间: $(date)" >> "$TEST_REPORT"
    echo "=====================================" >> "$TEST_REPORT"
    echo "" >> "$TEST_REPORT"
}

log_test() {
    local test_name="$1"
    local status="$2"
    local details="$3"

    if [ "$status" == "PASS" ]; then
        echo -e "${GREEN}✓${NC} $test_name"
        echo "[PASS] $test_name" >> "$TEST_REPORT"
    else
        echo -e "${RED}✗${NC} $test_name"
        echo "[FAIL] $test_name" >> "$TEST_REPORT"
    fi

    if [ -n "$details" ]; then
        echo "  $details" >> "$TEST_REPORT"
    fi
    echo "" >> "$TEST_REPORT"
}

# 启动服务
start_monitor() {
    echo -e "${YELLOW}Starting Monitor service...${NC}"
    cortex-monitor --config "$CONFIG_FILE" --host "$MONITOR_HOST" --port "$MONITOR_PORT" > "$MONITOR_LOG" 2>&1 &
    echo $! > "$MONITOR_PID_FILE"
    sleep 3

    # 验证启动
    if curl -s "http://$MONITOR_HOST:$MONITOR_PORT/health" > /dev/null; then
        echo -e "${GREEN}Monitor started successfully${NC}"
        log_test "Monitor Service Start" "PASS" "Port: $MONITOR_PORT"
        return 0
    else
        echo -e "${RED}Monitor failed to start${NC}"
        log_test "Monitor Service Start" "FAIL" "Failed to bind to port $MONITOR_PORT"
        return 1
    fi
}

start_probe() {
    echo -e "${YELLOW}Starting Probe service...${NC}"
    cortex-probe --config "$CONFIG_FILE" --host "$PROBE_HOST" --port "$PROBE_PORT" > "$PROBE_LOG" 2>&1 &
    echo $! > "$PROBE_PID_FILE"
    sleep 3

    # 验证启动
    if curl -s "http://$PROBE_HOST:$PROBE_PORT/health" > /dev/null; then
        echo -e "${GREEN}Probe started successfully${NC}"
        log_test "Probe Service Start" "PASS" "Port: $PROBE_PORT"
        return 0
    else
        echo -e "${RED}Probe failed to start${NC}"
        log_test "Probe Service Start" "FAIL" "Failed to bind to port $PROBE_PORT"
        return 1
    fi
}

# API 测试
test_monitor_health() {
    echo -e "${YELLOW}Testing Monitor health endpoint...${NC}"
    RESPONSE=$(curl -s "http://$MONITOR_HOST:$MONITOR_PORT/health")

    if echo "$RESPONSE" | grep -q "healthy"; then
        log_test "Monitor Health Check" "PASS" "Response: $RESPONSE"
        return 0
    else
        log_test "Monitor Health Check" "FAIL" "Response: $RESPONSE"
        return 1
    fi
}

test_probe_health() {
    echo -e "${YELLOW}Testing Probe health endpoint...${NC}"
    RESPONSE=$(curl -s "http://$PROBE_HOST:$PROBE_PORT/health")

    if echo "$RESPONSE" | grep -q "healthy"; then
        log_test "Probe Health Check" "PASS" "Response: $RESPONSE"
        return 0
    else
        log_test "Probe Health Check" "FAIL" "Response: $RESPONSE"
        return 1
    fi
}

test_probe_status() {
    echo -e "${YELLOW}Testing Probe status endpoint...${NC}"
    RESPONSE=$(curl -s "http://$PROBE_HOST:$PROBE_PORT/status")

    if echo "$RESPONSE" | grep -q "agent_id"; then
        log_test "Probe Status Query" "PASS" "Agent ID found in response"
        return 0
    else
        log_test "Probe Status Query" "FAIL" "No agent_id in response"
        return 1
    fi
}

test_cluster_topology() {
    echo -e "${YELLOW}Testing cluster topology endpoint...${NC}"
    RESPONSE=$(curl -s "http://$MONITOR_HOST:$MONITOR_PORT/api/v1/cluster/topology")

    if echo "$RESPONSE" | grep -q "success"; then
        NODE_COUNT=$(echo "$RESPONSE" | grep -o "\"id\":" | wc -l)
        log_test "Cluster Topology Query" "PASS" "Found $NODE_COUNT nodes"
        return 0
    else
        log_test "Cluster Topology Query" "FAIL" "API returned error"
        return 1
    fi
}

test_node_registration() {
    echo -e "${YELLOW}Testing node registration...${NC}"

    # 注册测试节点
    RESPONSE=$(curl -s -X POST "http://$MONITOR_HOST:$MONITOR_PORT/api/v1/agents" \
        -H "Content-Type: application/json" \
        -d '{
            "agent_id": "integration-test-node",
            "name": "Integration Test Node",
            "api_key": "test-key",
            "registration_token": "test-token-for-integration",
            "parent_id": null,
            "upstream_monitor_url": null
        }')

    if echo "$RESPONSE" | grep -q "success"; then
        log_test "Node Registration" "PASS" "Node registered successfully"
        return 0
    else
        log_test "Node Registration" "FAIL" "Registration failed: $RESPONSE"
        return 1
    fi
}

test_heartbeat() {
    echo -e "${YELLOW}Testing heartbeat mechanism...${NC}"

    RESPONSE=$(curl -s -X POST "http://$MONITOR_HOST:$MONITOR_PORT/api/v1/agents/integration-test-node/heartbeat" \
        -H "Content-Type: application/json" \
        -d '{"health_status": "healthy"}')

    if echo "$RESPONSE" | grep -q "success"; then
        log_test "Heartbeat Update" "PASS" "Heartbeat recorded"
        return 0
    else
        log_test "Heartbeat Update" "FAIL" "Heartbeat failed: $RESPONSE"
        return 1
    fi
}

# 主测试流程
main() {
    echo -e "${GREEN}=====================================${NC}"
    echo -e "${GREEN}Cortex Integration Test${NC}"
    echo -e "${GREEN}=====================================${NC}"
    echo ""

    init_report

    # 1. 启动服务
    echo -e "\n${YELLOW}=== Phase 1: Service Startup ===${NC}"
    start_monitor || exit 1
    start_probe || exit 1

    # 2. 基础健康检查
    echo -e "\n${YELLOW}=== Phase 2: Health Checks ===${NC}"
    test_monitor_health
    test_probe_health
    test_probe_status

    # 3. 集群功能测试
    echo -e "\n${YELLOW}=== Phase 3: Cluster Features ===${NC}"
    test_cluster_topology
    test_node_registration
    test_heartbeat

    # 4. 生成报告
    echo -e "\n${YELLOW}=== Test Complete ===${NC}"
    echo -e "${GREEN}Test report saved to: $TEST_REPORT${NC}"
    echo -e "${GREEN}Monitor log: $MONITOR_LOG${NC}"
    echo -e "${GREEN}Probe log: $PROBE_LOG${NC}"

    # 显示报告摘要
    echo ""
    cat "$TEST_REPORT"
}

# 运行测试
main "$@"
