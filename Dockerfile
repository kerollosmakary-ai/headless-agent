# ──────────────────────────────────────────────
# Multi-stage: Build PWA → Build Backend → Runtime
# ──────────────────────────────────────────────

# ═══════════════════════════════════════════════
# Stage 1: Build PWA (Vite + React + TS)
# ═══════════════════════════════════════════════
FROM node:20-alpine AS pwa-builder
WORKDIR /app/pwa
COPY pwa/package*.json ./
RUN npm ci
COPY pwa/ ./
RUN npm run build

# ═══════════════════════════════════════════════
# Stage 2: Python Backend Dependencies
# ═══════════════════════════════════════════════
FROM python:3.12-alpine AS backend-builder
WORKDIR /app/backend
RUN apk add --no-cache gcc musl-dev libffi-dev openssl-dev
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir --user -r requirements.txt

# ═══════════════════════════════════════════════
# Stage 3: Runtime (slim)
# ═══════════════════════════════════════════════
FROM python:3.12-slim AS runtime

# Install runtime deps + opencode
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install opencode CLI (adjust version as needed)
RUN curl -fsSL https://opencode.ai/install.sh | sh -s -- -b /usr/local/bin

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /bin/bash appuser

WORKDIR /app

# Copy Python packages from builder
COPY --from=backend-builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH

# Copy backend source
COPY --chown=appuser:appuser backend/ ./backend/

# Copy built PWA to static directory
COPY --from=pwa-builder --chown=appuser:appuser /app/pwa/dist ./static

# Create workspace directory
RUN mkdir -p /workspace && chown appuser:appuser /workspace

USER appuser
ENV PATH="/home/appuser/.local/bin:$PATH"
ENV PYTHONPATH="/app/backend:$PYTHONPATH"
ENV PYTHONUNBUFFERED=1

# Expose ports
EXPOSE 8000 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
