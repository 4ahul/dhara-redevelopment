# ─── BUILDER ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install service dependencies (dhara_shared is copied as source, not installed)
RUN uv pip install --system \
    "fastapi>=0.115.0" "uvicorn>=0.30.0" "httpx>=0.27.0" "openpyxl>=3.1.0" \
    "pydantic>=2.9.0" "pydantic-settings>=2.7.0" "reportlab>=4.0.0" \
    "PyYAML>=6.0" "python-multipart>=0.0.12" \
    "prometheus-fastapi-instrumentator>=7.0.0" "sentry-sdk[fastapi]>=2.58.0" \
    "opentelemetry-api>=1.41.1" "opentelemetry-sdk>=1.41.1" \
    "opentelemetry-instrumentation-fastapi>=0.62b1" \
    "opentelemetry-instrumentation-httpx>=0.62b1" \
    "opentelemetry-exporter-otlp>=1.41.1" \
    "tenacity>=8.5.0" "cloudinary>=1.40.0" "redis>=5.0.0"

# ─── RUNTIME ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install LibreOffice for PDF conversion
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libreoffice \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy source code (monorepo layout)
COPY services/__init__.py /app/services/
COPY services/report_generator/ /app/services/report_generator/
COPY services/report_generator/entrypoint.sh /app/entrypoint.sh
# Copy dhara_shared package source directly so PYTHONPATH=/app resolves the import
COPY dhara_shared/src/dhara_shared/ /app/dhara_shared/

RUN chmod +x /app/entrypoint.sh

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8004

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "services.report_generator.main:app", "--host", "0.0.0.0", "--port", "8004"]
