# ─── BUILDER ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dhara_shared and install it
COPY dhara_shared/ /build/dhara_shared/
RUN uv pip install --system /build/dhara_shared

# Install service dependencies
COPY services/dp_remarks_report/pyproject.toml /build/services/dp_remarks_report/
RUN uv pip install --system --no-sources -r /build/services/dp_remarks_report/pyproject.toml

# ─── RUNTIME ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy source code (monorepo layout)
COPY services/__init__.py /app/services/
COPY services/dp_remarks_report/ /app/services/dp_remarks_report/
COPY services/dp_remarks_report/entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "services.dp_remarks_report.main:app", "--host", "0.0.0.0", "--port", "8008"]
