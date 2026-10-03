# ── Stage 1: builder ──────────────────────────────────────────────────────────
# Install dependencies into an isolated venv so the final image
# only copies what's needed (no pip cache, no build tools).
FROM python:3.12-slim AS builder

WORKDIR /build

# Install dependencies first (layer-cached unless requirements.txt changes)
COPY requirements-render.txt requirements.txt
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip --quiet \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt --quiet

# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Pull in the pre-built venv from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application source
COPY app/ ./app/

# Make venv the default Python
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENABLE_AI_WORKERS=false

USER appuser

EXPOSE 8000

# Bind to 0.0.0.0 so the port is reachable from outside the container.
# Workers=1: the WebSocket broadcast manager is per-process. PORT is injected
# by hosts such as Render/Railway; falls back to 8000.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --log-level info"]
