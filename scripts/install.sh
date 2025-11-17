#!/bin/bash
# ==================== Cortex 一键安装脚本 ====================
# 自动化部署 Cortex 到生产环境
#
# 使用方法：
#   curl -fsSL https://raw.githubusercontent.com/yourusername/cortex/main/scripts/install.sh | bash
#   或者：
#   wget -O - https://raw.githubusercontent.com/yourusername/cortex/main/scripts/install.sh | bash
#
# 注意：需要 root 权限或 sudo

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/opt/cortex"
CONFIG_DIR="/etc/cortex"
SYSTEMD_DIR="/etc/systemd/system"
CORTEX_USER="cortex"
CORTEX_GROUP="cortex"

# Print functions
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then
        print_error "Please run this script as root or with sudo"
        exit 1
    fi
}

# Detect OS
detect_os() {
    print_info "Detecting operating system..."

    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        OS_VERSION=$VERSION_ID
    else
        print_error "Cannot detect OS. /etc/os-release not found."
        exit 1
    fi

    print_info "Detected: $PRETTY_NAME"
}

# Install dependencies
install_dependencies() {
    print_header "Installing Dependencies"

    case $OS in
        ubuntu|debian)
            apt-get update
            apt-get install -y \
                python3.11 \
                python3.11-venv \
                python3-pip \
                git \
                curl \
                ca-certificates \
                gnupg \
                lsb-release
            ;;

        centos|rhel|rocky|almalinux)
            yum install -y \
                python3.11 \
                python3-pip \
                git \
                curl \
                ca-certificates
            ;;

        *)
            print_warn "Unsupported OS: $OS. Please install dependencies manually."
            ;;
    esac

    print_success "Dependencies installed"
}

# Install Docker (optional)
install_docker() {
    print_header "Docker Installation (Optional)"

    read -p "Do you want to install Docker? (y/N): " install_docker_choice

    if [[ $install_docker_choice =~ ^[Yy]$ ]]; then
        print_info "Installing Docker..."

        case $OS in
            ubuntu|debian)
                curl -fsSL https://get.docker.com -o get-docker.sh
                sh get-docker.sh
                rm get-docker.sh
                systemctl enable docker
                systemctl start docker
                ;;

            *)
                print_warn "Automatic Docker installation not supported for $OS"
                print_info "Please install Docker manually: https://docs.docker.com/engine/install/"
                ;;
        esac

        # Install Docker Compose
        if command -v docker &> /dev/null; then
            print_info "Installing Docker Compose..."
            curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
            chmod +x /usr/local/bin/docker-compose
            print_success "Docker and Docker Compose installed"
        fi
    fi
}

# Create system user
create_user() {
    print_header "Creating System User"

    if id "$CORTEX_USER" &>/dev/null; then
        print_info "User $CORTEX_USER already exists"
    else
        useradd -r -s /bin/bash -d $INSTALL_DIR -m $CORTEX_USER
        print_success "User $CORTEX_USER created"
    fi
}

# Clone repository
clone_repository() {
    print_header "Cloning Cortex Repository"

    if [ -d "$INSTALL_DIR/.git" ]; then
        print_info "Repository already exists, pulling latest changes..."
        cd $INSTALL_DIR
        sudo -u $CORTEX_USER git pull
    else
        print_info "Cloning repository to $INSTALL_DIR..."
        sudo -u $CORTEX_USER git clone https://github.com/yourusername/cortex.git $INSTALL_DIR
    fi

    print_success "Repository cloned/updated"
}

# Install Python application
install_application() {
    print_header "Installing Cortex Application"

    cd $INSTALL_DIR

    # Create virtual environment
    if [ ! -d "venv" ]; then
        print_info "Creating Python virtual environment..."
        sudo -u $CORTEX_USER python3.11 -m venv venv
    fi

    # Install dependencies
    print_info "Installing Python dependencies..."
    sudo -u $CORTEX_USER bash -c "source venv/bin/activate && pip install --upgrade pip && pip install -e ."

    print_success "Application installed"
}

# Create directories
create_directories() {
    print_header "Creating Directories"

    mkdir -p $CONFIG_DIR
    mkdir -p $INSTALL_DIR/logs
    mkdir -p $INSTALL_DIR/data
    mkdir -p $INSTALL_DIR/probe_workspace/output

    chown -R $CORTEX_USER:$CORTEX_GROUP $INSTALL_DIR
    chown -R $CORTEX_USER:$CORTEX_GROUP $CONFIG_DIR

    print_success "Directories created"
}

# Configure application
configure_application() {
    print_header "Configuring Application"

    if [ -f "$CONFIG_DIR/config.yaml" ]; then
        print_info "Configuration file already exists"
        read -p "Do you want to overwrite it? (y/N): " overwrite
        if [[ ! $overwrite =~ ^[Yy]$ ]]; then
            print_info "Skipping configuration"
            return
        fi
    fi

    # Copy example config
    cp $INSTALL_DIR/config.example.yaml $CONFIG_DIR/config.yaml

    # Interactive configuration
    print_info "Please provide configuration values:"

    read -p "Agent ID (default: agent-001): " agent_id
    agent_id=${agent_id:-agent-001}

    read -p "Agent Name (default: Cortex Agent): " agent_name
    agent_name=${agent_name:-Cortex Agent}

    read -p "Mode [standalone/cluster] (default: standalone): " mode
    mode=${mode:-standalone}

    read -p "Anthropic API Key: " api_key

    read -p "Monitor Registration Token (generate random): " reg_token
    reg_token=${reg_token:-$(openssl rand -hex 32)}

    # Update config file
    sed -i "s/node-001/$agent_id/" $CONFIG_DIR/config.yaml
    sed -i "s/Cortex Node 1/$agent_name/" $CONFIG_DIR/config.yaml
    sed -i "s/mode: \"standalone\"/mode: \"$mode\"/" $CONFIG_DIR/config.yaml
    sed -i "s/api_key:.*/api_key: \"$api_key\"/" $CONFIG_DIR/config.yaml
    sed -i "s/registration_token:.*/registration_token: \"$reg_token\"/" $CONFIG_DIR/config.yaml

    # Create environment file
    cat > $CONFIG_DIR/cortex.env <<EOF
ANTHROPIC_API_KEY=$api_key
CORTEX_CONFIG=$CONFIG_DIR/config.yaml
EOF

    chmod 600 $CONFIG_DIR/cortex.env
    chown $CORTEX_USER:$CORTEX_GROUP $CONFIG_DIR/cortex.env

    print_success "Configuration complete"
    print_info "Config file: $CONFIG_DIR/config.yaml"
    print_info "Env file: $CONFIG_DIR/cortex.env"
}

# Install systemd services
install_systemd_services() {
    print_header "Installing Systemd Services"

    print_info "Which services do you want to install?"
    read -p "1. Monitor only\n2. Probe only\n3. Both (default)\nChoice [1-3]: " service_choice
    service_choice=${service_choice:-3}

    if [ "$service_choice" = "1" ] || [ "$service_choice" = "3" ]; then
        print_info "Installing Monitor service..."
        cp $INSTALL_DIR/deployment/cortex-monitor.service $SYSTEMD_DIR/
        sed -i "s|/opt/cortex|$INSTALL_DIR|g" $SYSTEMD_DIR/cortex-monitor.service
        sed -i "s|/etc/cortex/probe.env|$CONFIG_DIR/cortex.env|g" $SYSTEMD_DIR/cortex-monitor.service
        systemctl daemon-reload
        systemctl enable cortex-monitor
        print_success "Monitor service installed"
    fi

    if [ "$service_choice" = "2" ] || [ "$service_choice" = "3" ]; then
        print_info "Installing Probe service..."
        cp $INSTALL_DIR/deployment/cortex-probe.service $SYSTEMD_DIR/
        sed -i "s|/opt/cortex|$INSTALL_DIR|g" $SYSTEMD_DIR/cortex-probe.service
        sed -i "s|/etc/cortex/probe.env|$CONFIG_DIR/cortex.env|g" $SYSTEMD_DIR/cortex-probe.service
        systemctl daemon-reload
        systemctl enable cortex-probe
        print_success "Probe service installed"
    fi
}

# Start services
start_services() {
    print_header "Starting Services"

    read -p "Do you want to start services now? (Y/n): " start_now
    start_now=${start_now:-y}

    if [[ $start_now =~ ^[Yy]$ ]]; then
        if systemctl is-enabled cortex-monitor &>/dev/null; then
            systemctl start cortex-monitor
            print_info "Monitor service started"
        fi

        if systemctl is-enabled cortex-probe &>/dev/null; then
            systemctl start cortex-probe
            print_info "Probe service started"
        fi

        sleep 3

        # Check status
        if systemctl is-active cortex-monitor &>/dev/null; then
            print_success "Monitor is running"
        fi

        if systemctl is-active cortex-probe &>/dev/null; then
            print_success "Probe is running"
        fi
    fi
}

# Print final instructions
print_final_instructions() {
    print_header "Installation Complete!"

    echo -e "Cortex has been installed successfully!\n"
    echo -e "Installation directory: $INSTALL_DIR"
    echo -e "Configuration directory: $CONFIG_DIR\n"

    echo -e "${GREEN}Useful commands:${NC}"
    echo -e "  View Monitor status:  ${BLUE}sudo systemctl status cortex-monitor${NC}"
    echo -e "  View Probe status:    ${BLUE}sudo systemctl status cortex-probe${NC}"
    echo -e "  View Monitor logs:    ${BLUE}sudo journalctl -u cortex-monitor -f${NC}"
    echo -e "  View Probe logs:      ${BLUE}sudo journalctl -u cortex-probe -f${NC}"
    echo -e "  Restart services:     ${BLUE}sudo systemctl restart cortex-{monitor,probe}${NC}"
    echo -e ""
    echo -e "  Access Monitor API:   ${BLUE}http://localhost:8000${NC}"
    echo -e "  Access Probe API:     ${BLUE}http://localhost:8001${NC}"
    echo -e "  Access Web UI:        ${BLUE}http://localhost:3000${NC} (if running frontend)"
    echo -e ""
    echo -e "${YELLOW}Next steps:${NC}"
    echo -e "1. Review configuration: ${BLUE}sudo vim $CONFIG_DIR/config.yaml${NC}"
    echo -e "2. Check service logs for any errors"
    echo -e "3. Test API endpoints: ${BLUE}curl http://localhost:8000/health${NC}"
    echo -e "4. Set up firewall rules if needed"
    echo -e "5. Configure backup strategy"
    echo -e ""
    echo -e "For Docker deployment, see: ${BLUE}$INSTALL_DIR/docker-compose.yml${NC}"
    echo -e ""
}

# Main installation flow
main() {
    print_header "Cortex Installation Script"

    check_root
    detect_os
    install_dependencies
    install_docker
    create_user
    clone_repository
    install_application
    create_directories
    configure_application
    install_systemd_services
    start_services
    print_final_instructions

    print_success "Installation complete!"
}

# Run main function
main "$@"
