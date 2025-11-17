# ==================== Cortex Backend Dockerfile ====================
# Multi-stage build for optimized image size

# Stage 1: Builder
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /build

# Copy dependency files
COPY requirements.txt pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash cortex

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=cortex:cortex . .

# Create necessary directories
RUN mkdir -p logs data probe_workspace/output && \
    chown -R cortex:cortex logs data probe_workspace

# Switch to non-root user
USER cortex

# Expose ports
# 8000: Monitor Web Service
# 8001: Probe Web Service
EXPOSE 8000 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default environment variables
ENV PYTHONUNBUFFERED=1 \
    CORTEX_LOG_LEVEL=INFO \
    CORTEX_LOG_FORMAT=standard

# Entry point script
COPY --chown=cortex:cortex deployment/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["monitor"]
