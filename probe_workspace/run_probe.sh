#!/bin/bash
#
# Cortex Probe Runner
#
# 基于 claude -p 的文档驱动巡检执行器
#

set -e  # 遇到错误时退出
set -u  # 使用未定义变量时报错

# 脚本所在目录（probe_workspace）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 配置
PROBE_WORKSPACE="${PROBE_WORKSPACE:-$SCRIPT_DIR}"
OUTPUT_DIR="${PROBE_WORKSPACE}/output"
REPORT_FILE="${OUTPUT_DIR}/report.json"
LOG_FILE="${OUTPUT_DIR}/probe.log"

# 调试模式
DEBUG="${CORTEX_DEBUG:-0}"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log() {
    echo -e "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*" | tee -a "$LOG_FILE"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" | tee -a "$LOG_FILE"
}

# 检查依赖
check_dependencies() {
    log_info "Checking dependencies..."

    if ! command -v claude &> /dev/null; then
        log_error "claude command not found. Please install Claude Code."
        log_error "Visit: https://code.claude.com"
        exit 1
    fi

    if ! command -v python3 &> /dev/null; then
        log_error "python3 not found. Please install Python 3."
        exit 1
    fi

    log_info "Dependencies OK"
}

# 准备工作目录
prepare_workspace() {
    log_info "Preparing workspace..."

    # 创建输出目录
    mkdir -p "$OUTPUT_DIR"

    # 清理旧的输出文件
    rm -f "${OUTPUT_DIR}"/*.json
    rm -f "${OUTPUT_DIR}"/*.log

    log_info "Workspace ready: $PROBE_WORKSPACE"
}

# 执行 Probe 巡检
run_probe() {
    log_info "Starting Probe inspection..."

    # 切换到 probe workspace
    cd "$PROBE_WORKSPACE"

    # 构建 Claude 的提示词
    # 这个提示词会让 Claude 作为 Probe Agent 执行巡检
    PROMPT="Execute a full system inspection as a Cortex Probe Agent.

Follow these steps:

1. Read CLAUDE.md to understand your role and workflow
2. List all inspection requirements in inspections/*.md
3. For each inspection:
   - Run the corresponding tool in tools/
   - Analyze the results
   - Determine if there are any issues (L1/L2/L3)
   - For L1 issues, execute fixes using available tools
   - Collect all results
4. Use tools/report_builder.py to generate the final report
5. Use tools/report_to_monitor.py to upload the report

Important:
- Work systematically through each inspection
- Record all findings and actions
- Generate a complete JSON report at output/report.json
- If any step fails, log the error and continue with other inspections
- At the end, print a summary of the inspection results

Begin the inspection now."

    # 调用 claude -p
    log_info "Invoking Claude Code in prompt mode..."

    # 使用 --dangerously-skip-permissions 以便自动化执行（适合 cron）
    # 仅在受信任的服务器环境中使用
    if [ "$DEBUG" = "1" ]; then
        log_info "Debug mode: Full output"
        claude -p --dangerously-skip-permissions "$PROMPT" 2>&1 | tee -a "$LOG_FILE"
    else
        claude -p --dangerously-skip-permissions "$PROMPT" >> "$LOG_FILE" 2>&1
    fi

    CLAUDE_EXIT_CODE=$?

    if [ $CLAUDE_EXIT_CODE -ne 0 ]; then
        log_error "Claude execution failed with exit code $CLAUDE_EXIT_CODE"
        return 1
    fi

    log_info "Claude execution completed"
    return 0
}

# 验证报告
validate_report() {
    log_info "Validating report..."

    if [ ! -f "$REPORT_FILE" ]; then
        log_error "Report file not found: $REPORT_FILE"
        return 1
    fi

    # 验证 JSON 格式
    if ! python3 -m json.tool "$REPORT_FILE" > /dev/null 2>&1; then
        log_error "Invalid JSON in report file"
        return 1
    fi

    log_info "Report validation passed"
    return 0
}

# 打印报告摘要
print_summary() {
    if [ ! -f "$REPORT_FILE" ]; then
        log_warn "No report file to summarize"
        return
    fi

    log_info "=== Inspection Summary ==="

    # 使用 Python 解析 JSON 并打印摘要
    python3 << EOF
import json
import sys

try:
    with open("$REPORT_FILE", "r") as f:
        report = json.load(f)

    print(f"Agent ID: {report.get('agent_id', 'unknown')}")
    print(f"Status: {report.get('status', 'unknown')}")
    print(f"Timestamp: {report.get('timestamp', 'unknown')}")

    metrics = report.get('metrics', {})
    if metrics:
        print("\nMetrics:")
        for key, value in metrics.items():
            print(f"  - {key}: {value}")

    issues = report.get('issues', [])
    print(f"\nIssues found: {len(issues)}")
    for issue in issues:
        print(f"  - [{issue.get('level', 'unknown')}] {issue.get('type', 'unknown')}: {issue.get('description', 'no description')}")

    actions = report.get('actions_taken', [])
    print(f"\nActions taken: {len(actions)}")
    for action in actions:
        print(f"  - [{action.get('level', 'unknown')}] {action.get('action', 'unknown')}: {action.get('result', 'unknown')}")

except Exception as e:
    print(f"Error parsing report: {e}", file=sys.stderr)
    sys.exit(1)
EOF
}

# 主函数
main() {
    log_info "========================================="
    log_info "Cortex Probe - Document-Driven Mode"
    log_info "========================================="

    # 检查依赖
    check_dependencies

    # 准备工作空间
    prepare_workspace

    # 执行巡检
    if ! run_probe; then
        log_error "Probe execution failed"
        exit 1
    fi

    # 验证报告
    if ! validate_report; then
        log_error "Report validation failed"
        exit 1
    fi

    # 打印摘要
    print_summary

    log_info "========================================="
    log_info "Probe execution completed successfully"
    log_info "Report: $REPORT_FILE"
    log_info "Log: $LOG_FILE"
    log_info "========================================="

    exit 0
}

# 运行主函数
main "$@"
