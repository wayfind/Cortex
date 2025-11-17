# ==================== Cortex Frontend Dockerfile ====================
# Multi-stage build for optimized production image

# Stage 1: Builder
FROM node:18-alpine as builder

WORKDIR /build

# Copy package files
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci --legacy-peer-deps

# Copy source code
COPY . .

# Build for production
ENV NODE_ENV=production
RUN npm run build

# Stage 2: Production with nginx
FROM nginx:1.25-alpine

# Copy built files from builder
COPY --from=builder /build/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Create nginx user
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chmod -R 755 /usr/share/nginx/html

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost/ || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
