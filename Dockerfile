# ── Stage 1: Build Frontend ─────────────────────────
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

# Copy frontend assets (HTML, CSS, JS, etc.)
COPY . /app/frontend/
# We don't have package.json for frontend as it's vanilla JS
# But we copy it to a specific directory so we can serve it later

# ── Stage 2: Backend + Final Image ──────────────────
FROM python:3.11-slim

# System dependencies for OpenCV, FFmpeg, and Python
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps (leverage Docker cache)
COPY backend/requirements-core.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements-core.txt

# Copy backend code
COPY backend/ ./backend/

# Copy frontend code from stage 1
COPY --from=frontend-builder /app/frontend ./frontend

# Create directories for temp files and local DB
RUN mkdir -p /tmp/clips /app/models /app/backend/storage /app/backend/data
ENV DATABASE_URL="sqlite+aiosqlite:////app/backend/data/clipforge.db"

# Expose port
EXPOSE 8000

# Start script
COPY start.sh /app/
RUN chmod +x /app/start.sh

CMD ["/app/start.sh"]
