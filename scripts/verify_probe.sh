#!/bin/bash
#
# Probe 新架构快速验证脚本
#
# 此脚本自动测试 Probe 服务的主要功能
#

set -e  # 遇到错误立即退出

PROBE_HOST="127.0.0.1"
PROBE_PORT="8001"
BASE_URL="http://${PROBE_HOST}:${PROBE_PORT}"

# 颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 打印函数
print_header() {
    echo -e "\n${YELLOW}=== $1 ===${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "  $1"
}

# 检查依赖
check_dependencies() {
    print_header "检查依赖"

    if ! command -v curl &> /dev/null; then
        print_error "curl 未安装"
        exit 1
    fi
    print_success "curl 已安装"

    if ! command -v jq &> /dev/null; then
        print_error "jq 未安装（可选，用于 JSON 格式化）"
        JQ_AVAILABLE=false
    else
        print_success "jq 已安装"
        JQ_AVAILABLE=true
    fi
}

# 等待服务启动
wait_for_service() {
    print_header "等待服务启动"

    MAX_RETRIES=30
    RETRY_COUNT=0

    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if curl -s "${BASE_URL}/health" > /dev/null 2>&1; then
            print_success "服务已启动"
            return 0
        fi

        echo -n "."
        sleep 1
        RETRY_COUNT=$((RETRY_COUNT + 1))
    done

    print_error "服务启动超时"
    exit 1
}

# 测试健康检查
test_health() {
    print_header "测试健康检查"

    RESPONSE=$(curl -s "${BASE_URL}/health")

    if [ $JQ_AVAILABLE = true ]; then
        echo "$RESPONSE" | jq .
    else
        echo "$RESPONSE"
    fi

    if echo "$RESPONSE" | grep -q '"status"'; then
        print_success "健康检查通过"
    else
        print_error "健康检查失败"
        exit 1
    fi
}

# 测试状态查询
test_status() {
    print_header "测试状态查询"

    RESPONSE=$(curl -s "${BASE_URL}/status")

    if [ $JQ_AVAILABLE = true ]; then
        echo "$RESPONSE" | jq .
    else
        echo "$RESPONSE"
    fi

    if echo "$RESPONSE" | grep -q '"scheduler_status"'; then
        print_success "状态查询成功"
    else
        print_error "状态查询失败"
        exit 1
    fi
}

# 测试调度信息
test_schedule() {
    print_header "测试调度信息"

    RESPONSE=$(curl -s "${BASE_URL}/schedule")

    if [ $JQ_AVAILABLE = true ]; then
        echo "$RESPONSE" | jq .
    else
        echo "$RESPONSE"
    fi

    if echo "$RESPONSE" | grep -q '"scheduler_running"'; then
        print_success "调度信息查询成功"
    else
        print_error "调度信息查询失败"
        exit 1
    fi
}

# 测试报告列表
test_reports() {
    print_header "测试报告列表"

    RESPONSE=$(curl -s "${BASE_URL}/reports")

    if [ $JQ_AVAILABLE = true ]; then
        echo "$RESPONSE" | jq .
    else
        echo "$RESPONSE"
    fi

    if echo "$RESPONSE" | grep -q '"reports"'; then
        print_success "报告列表查询成功"
    else
        print_error "报告列表查询失败"
        exit 1
    fi
}

# 测试暂停和恢复
test_pause_resume() {
    print_header "测试暂停和恢复"

    # 暂停
    print_info "暂停调度..."
    RESPONSE=$(curl -s -X POST "${BASE_URL}/pause")

    if [ $JQ_AVAILABLE = true ]; then
        echo "$RESPONSE" | jq .
    else
        echo "$RESPONSE"
    fi

    if echo "$RESPONSE" | grep -q '"paused"'; then
        print_success "调度暂停成功"
    else
        print_error "调度暂停失败"
        exit 1
    fi

    sleep 1

    # 恢复
    print_info "恢复调度..."
    RESPONSE=$(curl -s -X POST "${BASE_URL}/resume")

    if [ $JQ_AVAILABLE = true ]; then
        echo "$RESPONSE" | jq .
    else
        echo "$RESPONSE"
    fi

    if echo "$RESPONSE" | grep -q '"resumed"'; then
        print_success "调度恢复成功"
    else
        print_error "调度恢复失败"
        exit 1
    fi
}

# 主函数
main() {
    echo -e "${YELLOW}"
    echo "╔═══════════════════════════════════════════╗"
    echo "║   Cortex Probe 服务验证脚本              ║"
    echo "╚═══════════════════════════════════════════╝"
    echo -e "${NC}"

    check_dependencies
    wait_for_service
    test_health
    test_status
    test_schedule
    test_reports
    test_pause_resume

    print_header "验证完成"
    print_success "所有测试通过！"
    echo ""
    echo "下一步："
    echo "  1. 手动触发巡检: curl -X POST ${BASE_URL}/execute"
    echo "  2. 连接 WebSocket: websocat ws://${PROBE_HOST}:${PROBE_PORT}/ws"
    echo "  3. 查看日志: tail -f logs/probe.log"
    echo ""
}

# 运行
main
