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
COPY services/ocr_service/pyproject.toml ./services/ocr_service/

# uv sync → resolves workspace links, builds package, drops into site-packages
RUN uv pip install --system -r services/ocr_service/pyproject.toml
RUN uv pip install --system ./dhara_shared

# ─── RUNTIME ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    bash \
    tesseract-ocr \
    libtesseract-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy ALL installed packages from builder (where uv placed them)
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY dhara_shared/src/dhara_shared/ /usr/local/lib/python3.12/site-packages/dhara_shared/

# Service code
COPY services/__init__.py /app/services/
COPY services/ocr_service/ /app/services/ocr_service/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8009

CMD ["python", "-m", "uvicorn", "services.ocr_service.main:app", "--host", "0.0.0.0", "--port", "8009"]