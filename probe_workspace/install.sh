#!/bin/bash
#
# Cortex Probe Installer
#
# 安装 Probe 到系统
#

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
INSTALL_DIR="${CORTEX_INSTALL_DIR:-/opt/cortex/probe}"
CONFIG_DIR="/etc/cortex"
CONFIG_FILE="${CONFIG_DIR}/config.yaml"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 日志函数
info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

success() {
    echo -e "${BLUE}✓${NC} $*"
}

# 检查权限
check_root() {
    if [ "$EUID" -ne 0 ]; then
        error "This script must be run as root"
        echo "Usage: sudo $0"
        exit 1
    fi
}

# 检查依赖
check_dependencies() {
    info "Checking dependencies..."

    local missing_deps=()

    # 检查 Python
    if ! command -v python3 &> /dev/null; then
        missing_deps+=("python3")
    fi

    # 检查 pip
    if ! command -v pip3 &> /dev/null; then
        missing_deps+=("python3-pip")
    fi

    # 检查 Claude Code
    if ! command -v claude &> /dev/null; then
        warn "Claude Code not found. Please install it from https://code.claude.com"
        warn "Installation will continue, but Probe will not work without Claude Code."
    fi

    # 报告缺失的依赖
    if [ ${#missing_deps[@]} -gt 0 ]; then
        error "Missing dependencies: ${missing_deps[*]}"
        echo ""
        echo "Please install them first:"
        echo "  Ubuntu/Debian: sudo apt-get install ${missing_deps[*]}"
        echo "  RHEL/CentOS:   sudo yum install ${missing_deps[*]}"
        exit 1
    fi

    success "Dependencies OK"
}

# 创建安装目录
create_install_dir() {
    info "Creating installation directory: $INSTALL_DIR"

    mkdir -p "$INSTALL_DIR"
    mkdir -p "${INSTALL_DIR}/output"
    mkdir -p "${INSTALL_DIR}/tools"
    mkdir -p "${INSTALL_DIR}/inspections"
    mkdir -p "${INSTALL_DIR}/mcp"

    success "Installation directory created"
}

# 复制文件
copy_files() {
    info "Copying Probe files..."

    # 复制主要文件
    cp -r "${SCRIPT_DIR}/CLAUDE.md" "$INSTALL_DIR/"
    cp -r "${SCRIPT_DIR}/run_probe.sh" "$INSTALL_DIR/"
    cp -r "${SCRIPT_DIR}/tools/"* "${INSTALL_DIR}/tools/"
    cp -r "${SCRIPT_DIR}/inspections/"* "${INSTALL_DIR}/inspections/"

    # 复制 MCP 配置（如果存在）
    if [ -d "${SCRIPT_DIR}/mcp" ]; then
        cp -r "${SCRIPT_DIR}/mcp/"* "${INSTALL_DIR}/mcp/" 2>/dev/null || true
    fi

    # 设置权限
    chmod +x "${INSTALL_DIR}/run_probe.sh"
    chmod +x "${INSTALL_DIR}/tools/"*.py

    success "Files copied"
}

# 安装 Python 依赖
install_python_deps() {
    info "Installing Python dependencies..."

    # 创建 requirements.txt
    cat > "${INSTALL_DIR}/requirements.txt" << 'EOF'
# Cortex Probe Python Dependencies
httpx>=0.24.0
pyyaml>=6.0
loguru>=0.7.0
EOF

    # 安装依赖
    pip3 install -r "${INSTALL_DIR}/requirements.txt" --quiet

    success "Python dependencies installed"
}

# 创建配置文件
create_config() {
    info "Creating configuration..."

    mkdir -p "$CONFIG_DIR"

    if [ -f "$CONFIG_FILE" ]; then
        warn "Configuration file already exists: $CONFIG_FILE"
        warn "Skipping configuration creation. Please update it manually if needed."
        return
    fi

    # 生成默认配置
    cat > "$CONFIG_FILE" << 'EOF'
# Cortex Agent Configuration

agent:
  # 节点唯一标识（请修改为实际的 ID）
  id: "agent-default-001"

  # 节点名称
  name: "Cortex Agent"

  # 上游 Monitor URL（独立模式下留空）
  # 格式：http://monitor.example.com:8000
  upstream_monitor_url: ""

  # Monitor API 密钥（如果需要）
  monitor_api_key: ""

probe:
  # Cron 调度表达式（默认：每小时）
  schedule: "0 * * * *"

  # 阈值配置
  threshold_disk_percent: 80
  threshold_memory_percent: 80
  threshold_cpu_percent: 70

  # 关键服务列表
  critical_services:
    - nginx
    - mysql
    - redis

monitor:
  # Monitor 监听地址
  host: "0.0.0.0"
  port: 8000

  # 数据库配置
  database_url: "sqlite:///var/lib/cortex/monitor.db"

  # Telegram 通知（可选）
  telegram:
    enabled: false
    bot_token: ""
    chat_id: ""
EOF

    chmod 600 "$CONFIG_FILE"
    success "Configuration file created: $CONFIG_FILE"
    warn "Please edit $CONFIG_FILE and update the agent.id and other settings"
}

# 设置 Cron 定时任务
setup_cron() {
    info "Setting up cron job..."

    # 询问是否设置 cron
    read -p "Do you want to set up automatic cron job? (y/N): " -n 1 -r
    echo

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        warn "Skipping cron setup. You can manually add it later:"
        echo "  0 * * * * ${INSTALL_DIR}/run_probe.sh >> /var/log/cortex-probe.log 2>&1"
        return
    fi

    # 检查是否已经存在 cron 任务
    if crontab -l 2>/dev/null | grep -q "run_probe.sh"; then
        warn "Cron job already exists. Skipping."
        return
    fi

    # 添加 cron 任务（每小时执行一次）
    (crontab -l 2>/dev/null; echo "0 * * * * ${INSTALL_DIR}/run_probe.sh >> /var/log/cortex-probe.log 2>&1") | crontab -

    success "Cron job added (runs every hour)"
}

# 创建日志目录
setup_logging() {
    info "Setting up logging..."

    touch /var/log/cortex-probe.log
    chmod 644 /var/log/cortex-probe.log

    success "Log file created: /var/log/cortex-probe.log"
}

# 打印安装摘要
print_summary() {
    echo ""
    echo "========================================="
    echo "  Cortex Probe Installation Complete"
    echo "========================================="
    echo ""
    echo "Installation directory: $INSTALL_DIR"
    echo "Configuration file:     $CONFIG_FILE"
    echo "Log file:              /var/log/cortex-probe.log"
    echo ""
    echo "Next steps:"
    echo "  1. Edit configuration: nano $CONFIG_FILE"
    echo "  2. Update agent.id and upstream_monitor_url"
    echo "  3. Test the probe:     ${INSTALL_DIR}/run_probe.sh"
    echo "  4. Check the logs:     tail -f /var/log/cortex-probe.log"
    echo ""
    echo "For manual cron setup (if skipped):"
    echo "  0 * * * * ${INSTALL_DIR}/run_probe.sh >> /var/log/cortex-probe.log 2>&1"
    echo ""
    echo "========================================="
}

# 主函数
main() {
    echo "========================================="
    echo "  Cortex Probe Installer"
    echo "========================================="
    echo ""

    # 检查权限
    check_root

    # 检查依赖
    check_dependencies

    # 创建安装目录
    create_install_dir

    # 复制文件
    copy_files

    # 安装 Python 依赖
    install_python_deps

    # 创建配置
    create_config

    # 设置日志
    setup_logging

    # 设置 Cron
    setup_cron

    # 打印摘要
    print_summary
}

# 运行主函数
main "$@"
