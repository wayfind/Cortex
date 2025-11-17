#!/bin/bash
# ==================== Cortex Docker Entrypoint ====================
# This script handles the initialization and startup of Cortex services

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Print with color
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Initialize environment
print_info "Starting Cortex service..."

# Validate required environment variables
if [ -z "$ANTHROPIC_API_KEY" ] && [ "$1" = "probe" ]; then
    print_warn "ANTHROPIC_API_KEY not set - Probe will not function properly"
fi

# Create necessary directories
mkdir -p logs data probe_workspace/output

# Wait for database (if using external database)
if [ -n "$CORTEX_MONITOR_DATABASE_URL" ] && [[ "$CORTEX_MONITOR_DATABASE_URL" == postgres* ]]; then
    print_info "Waiting for PostgreSQL..."
    until pg_isready -h $(echo $CORTEX_MONITOR_DATABASE_URL | sed -n 's/.*@\(.*\):.*/\1/p') 2>/dev/null; do
        sleep 1
    done
    print_info "PostgreSQL is ready"
fi

# Run database migrations (if Monitor service)
if [ "$1" = "monitor" ]; then
    print_info "Running database migrations..."
    # Add alembic migration command here when ready
    # alembic upgrade head
fi

# Determine which service to start
case "$1" in
    monitor)
        print_info "Starting Cortex Monitor on port ${CORTEX_MONITOR_PORT:-8000}..."
        exec uvicorn cortex.monitor.app:app \
            --host ${CORTEX_MONITOR_HOST:-0.0.0.0} \
            --port ${CORTEX_MONITOR_PORT:-8000} \
            --log-level ${CORTEX_LOG_LEVEL:-info}
        ;;

    probe)
        print_info "Starting Cortex Probe on port ${CORTEX_PROBE_PORT:-8001}..."
        exec uvicorn cortex.probe.app:app \
            --host ${CORTEX_PROBE_HOST:-0.0.0.0} \
            --port ${CORTEX_PROBE_PORT:-8001} \
            --log-level ${CORTEX_LOG_LEVEL:-info}
        ;;

    *)
        print_error "Unknown service: $1"
        print_info "Usage: $0 {monitor|probe}"
        exit 1
        ;;
esac
