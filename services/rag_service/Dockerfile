# ─── BUILDER ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy workspace (root + dhara_shared)
COPY pyproject.toml uv.lock ./
COPY dhara_shared/ ./dhara_shared/
COPY services/rag_service/pyproject.toml ./services/rag_service/

# uv sync → resolves workspace links, builds package, drops into site-packages
RUN uv pip install --system -r /build/pyproject.toml || uv sync --frozen

# ─── RUNTIME ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Copy ALL installed packages from builder (where uv placed them)
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Service code
COPY services/__init__.py /app/services/
COPY services/rag_service/ /app/services/rag_service/
COPY services/rag_service/entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8006

CMD ["uvicorn", "services.rag_service.main:app", "--host", "0.0.0.0", "--port", "8006"]