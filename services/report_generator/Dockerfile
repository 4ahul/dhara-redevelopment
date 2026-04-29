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
COPY services/report_generator/pyproject.toml ./services/report_generator/

# Install dependencies - includes dhara_shared from local workspace via editable install
RUN uv pip install --system -r /build/pyproject.toml && \
    uv pip install --system /build/dhara_shared

# ─── RUNTIME ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libreoffice \
    && rm -rf /var/lib/apt/lists/*

# Copy ALL installed packages from builder (where uv placed them)
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
# Belt-and-suspenders: ensure dhara_shared is available (uv workspace may not copy editable properly)
COPY dhara_shared/src/dhara_shared/ /usr/local/lib/python3.12/site-packages/dhara_shared/

# Service code
COPY services/__init__.py /app/services/
COPY services/report_generator/ /app/services/report_generator/
COPY services/report_generator/entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh

ENV PYTHONPATH=/app:/usr/local/lib/python3.12/site-packages
ENV PYTHONUNBUFFERED=1

EXPOSE 8004

CMD ["uvicorn", "services.report_generator.main:app", "--host", "0.0.0.0", "--port", "8004"]