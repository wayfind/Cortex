#!/bin/bash
#
# Probe 端到端测试脚本
#
# 这个脚本验证 Probe 的各个组件是否正常工作
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

success() {
    echo -e "${GREEN}✓${NC} $*"
}

error() {
    echo -e "${RED}✗${NC} $*"
}

info() {
    echo -e "${YELLOW}→${NC} $*"
}

echo "========================================="
echo "  Cortex Probe - End-to-End Test"
echo "========================================="
echo ""

# 测试 1: 检查文件结构
info "Test 1: Checking file structure..."
FILES=(
    "CLAUDE.md"
    "README.md"
    "run_probe.sh"
    "install.sh"
    "inspections/TEMPLATE.md"
    "inspections/disk_space.md"
    "inspections/memory.md"
    "inspections/cpu.md"
    "inspections/services.md"
    "tools/check_disk.py"
    "tools/check_memory.py"
    "tools/check_cpu.py"
    "tools/check_services.py"
    "tools/cleanup_disk.py"
    "tools/report_builder.py"
    "tools/report_to_monitor.py"
)

for file in "${FILES[@]}"; do
    if [ ! -f "$file" ]; then
        error "Missing file: $file"
        exit 1
    fi
done
success "All required files present"

# 测试 2: 检查执行权限
info "Test 2: Checking executable permissions..."
EXECUTABLES=(
    "run_probe.sh"
    "install.sh"
    "tools/check_disk.py"
    "tools/check_memory.py"
    "tools/check_cpu.py"
    "tools/check_services.py"
    "tools/cleanup_disk.py"
    "tools/report_builder.py"
    "tools/report_to_monitor.py"
)

for exe in "${EXECUTABLES[@]}"; do
    if [ ! -x "$exe" ]; then
        error "Not executable: $exe"
        exit 1
    fi
done
success "All scripts are executable"

# 测试 3: 测试检查工具
info "Test 3: Testing check tools..."

# 测试磁盘检查
if ! python3 tools/check_disk.py > /tmp/test_disk.json 2>&1; then
    error "Disk check failed"
    exit 1
fi
if ! python3 -m json.tool /tmp/test_disk.json > /dev/null 2>&1; then
    error "Disk check output is not valid JSON"
    exit 1
fi
success "Disk check tool works"

# 测试 CPU 检查
if ! python3 tools/check_cpu.py > /tmp/test_cpu.json 2>&1; then
    error "CPU check failed"
    cat /tmp/test_cpu.json
    exit 1
fi
if ! python3 -m json.tool /tmp/test_cpu.json > /dev/null 2>&1; then
    error "CPU check output is not valid JSON"
    exit 1
fi
success "CPU check tool works"

# 测试 4: 测试报告构建器
info "Test 4: Testing report builder..."

mkdir -p output

if ! python3 tools/report_builder.py \
    --disk /tmp/test_disk.json \
    --cpu /tmp/test_cpu.json \
    -o output/test_report.json > /dev/null 2>&1; then
    error "Report builder failed"
    exit 1
fi

if [ ! -f output/test_report.json ]; then
    error "Report file not created"
    exit 1
fi

if ! python3 -m json.tool output/test_report.json > /dev/null 2>&1; then
    error "Report is not valid JSON"
    exit 1
fi
success "Report builder works"

# 测试 5: 验证报告内容
info "Test 5: Validating report content..."

REQUIRED_FIELDS=("agent_id" "timestamp" "status" "metrics" "issues" "actions_taken")
for field in "${REQUIRED_FIELDS[@]}"; do
    if ! grep -q "\"$field\"" output/test_report.json; then
        error "Missing required field: $field"
        exit 1
    fi
done
success "Report has all required fields"

# 测试 6: 测试 dry-run 上报
info "Test 6: Testing report upload (dry-run)..."

if ! python3 tools/report_to_monitor.py output/test_report.json --dry-run > /dev/null 2>&1; then
    error "Report upload dry-run failed"
    exit 1
fi
success "Report upload tool works (dry-run)"

# 测试 7: 测试磁盘清理（dry-run）
info "Test 7: Testing disk cleanup (dry-run)..."

if ! python3 tools/cleanup_disk.py --safe --dry-run -o output/cleanup_result.json > /dev/null 2>&1; then
    error "Disk cleanup dry-run failed"
    exit 1
fi

if ! python3 -m json.tool output/cleanup_result.json > /dev/null 2>&1; then
    error "Cleanup result is not valid JSON"
    exit 1
fi
success "Disk cleanup tool works (dry-run)"

# 清理测试文件
rm -f /tmp/test_*.json

echo ""
echo "========================================="
echo -e "${GREEN}  All Tests Passed!${NC}"
echo "========================================="
echo ""
echo "Next steps:"
echo "  1. Review the test report: cat output/test_report.json"
echo "  2. Install to system:      sudo ./install.sh"
echo "  3. Configure agent:        sudo nano /etc/cortex/config.yaml"
echo "  4. Run first inspection:   sudo /opt/cortex/probe/run_probe.sh"
echo ""
