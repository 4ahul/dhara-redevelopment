# ─── BUILDER ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install build dependencies with Playwright-required libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# Copy dhara_shared and install it
COPY dhara_shared/ /build/dhara_shared/
RUN uv pip install --system /build/dhara_shared

# Install service dependencies
COPY services/dp_remarks_report/pyproject.toml /build/services/dp_remarks_report/
RUN uv pip install --system --no-sources -r /build/services/dp_remarks_report/pyproject.toml

# Install playwright browsers (cache location matters!)
RUN pip install playwright && playwright install chromium

# ─── RUNTIME ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install runtime dependencies (includes browser libs for Chromium)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    bash \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# Copy ALL installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy playwright browser cache from builder
COPY --from=builder /root/.cache/ms-playwright /root/.cache/ms-playwright

# Service code
COPY services/__init__.py /app/services/
COPY services/dp_remarks_report/ /app/services/dp_remarks_report/
COPY services/dp_remarks_report/entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8008

CMD ["uvicorn", "services.dp_remarks_report.main:app", "--host", "0.0.0.0", "--port", "8008"]