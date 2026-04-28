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
COPY services/pr_card_scraper/pyproject.toml /build/services/pr_card_scraper/
RUN uv pip install --system -r /build/services/pr_card_scraper/pyproject.toml

# ─── RUNTIME ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install system dependencies for Tesseract, OpenCV, and Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 libxshmfence1 fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Ensure runtime has critical third-party deps used by dhara_shared
RUN pip install --no-cache-dir redis==5.3.1

# Belt-and-suspenders: include local dhara_shared in runtime image
COPY dhara_shared/src/dhara_shared/ /usr/local/lib/python3.12/site-packages/dhara_shared/

# Install Playwright browsers
RUN playwright install chromium

# Copy source code (monorepo layout)
COPY services/__init__.py /app/services/
COPY services/pr_card_scraper/ /app/services/pr_card_scraper/
COPY services/pr_card_scraper/entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "services.pr_card_scraper.main:app", "--host", "0.0.0.0", "--port", "8005"]
