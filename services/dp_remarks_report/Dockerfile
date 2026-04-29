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
COPY services/dp_remarks_report/pyproject.toml /build/services/dp_remarks_report/
RUN uv pip install --system -r /build/services/dp_remarks_report/pyproject.toml
# Reinstall dhara_shared non-editable to override any editable workspace install
RUN uv pip install --system /build/dhara_shared

# ─── RUNTIME ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    # Chromium/Playwright system deps
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 \
    libpango-1.0-0 libcairo2 libxshmfence1 libx11-6 libxext6 libxcb1 \
    fonts-liberation wget \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
# Ensure dhara_shared package directory exists (belt-and-suspenders)
COPY dhara_shared/src/dhara_shared/ /usr/local/lib/python3.12/site-packages/dhara_shared/

# Copy source code (monorepo layout)
COPY services/__init__.py /app/services/
COPY services/dp_remarks_report/ /app/services/dp_remarks_report/
COPY services/dp_remarks_report/entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh

# Install Playwright browsers
RUN playwright install chromium

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 10000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "services.dp_remarks_report.main:app", "--host", "0.0.0.0", "--port", "10000"]
