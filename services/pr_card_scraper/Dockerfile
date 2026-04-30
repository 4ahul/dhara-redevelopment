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
COPY services/pr_card_scraper/pyproject.toml /build/services/pr_card_scraper/
RUN uv pip install --system --no-sources -r /build/services/pr_card_scraper/pyproject.toml

# ─── RUNTIME ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install system dependencies for Tesseract and OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy source code (monorepo layout)
COPY services/__init__.py /app/services/
COPY services/pr_card_scraper/ /app/services/pr_card_scraper/
COPY services/pr_card_scraper/entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "services.pr_card_scraper.main:app", "--host", "0.0.0.0", "--port", "8005"]
