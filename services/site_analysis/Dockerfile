# ─── BUILDER ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy workspace root for uv and workspace member
COPY pyproject.toml /build/pyproject.toml
COPY uv.lock /build/uv.lock
COPY dhara_shared/ /build/dhara_shared/
# Install dhara_shared as a non-editable package to avoid editable .pth
RUN uv pip install --system /build/dhara_shared

# Install service dependencies via uv workspace mapping
COPY services/site_analysis/pyproject.toml /build/services/site_analysis/
RUN uv pip install --system -r /build/services/site_analysis/pyproject.toml
## Ensure dhara_shared is non-editable (override any editable mapping)
RUN uv pip install --system /build/dhara_shared

# ─── RUNTIME ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
# Ensure dhara_shared package directory exists (belt-and-suspenders)
COPY dhara_shared/src/dhara_shared/ /usr/local/lib/python3.12/site-packages/dhara_shared/

# Copy source code (monorepo layout)
COPY services/__init__.py /app/services/
COPY services/site_analysis/ /app/services/site_analysis/
COPY services/site_analysis/entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8001

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "services.site_analysis.main:app", "--host", "0.0.0.0", "--port", "8001"]
