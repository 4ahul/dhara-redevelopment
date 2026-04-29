# ─── BUILDER ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Clone muniscan (no setup.py — copy the package directory directly)
RUN git clone --depth 1 https://github.com/ashish-yadav-911/ocr.git /build/ocr_repo

# Copy workspace root for uv and workspace member
COPY pyproject.toml /build/pyproject.toml
COPY uv.lock /build/uv.lock
COPY dhara_shared/ /build/dhara_shared/
# Install dhara_shared as a non-editable package to avoid editable .pth
RUN uv pip install --system /build/dhara_shared

# Install service dependencies via uv workspace mapping
COPY services/ocr_service/pyproject.toml /build/services/ocr_service/
RUN uv pip install --system -r /build/services/ocr_service/pyproject.toml

# ─── RUNTIME ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgl1 \
    libglib2.0-0 \
    tesseract-ocr \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy muniscan package from cloned repo
COPY --from=builder /build/ocr_repo/muniscan /app/muniscan

# Copy service source
COPY services/__init__.py /app/services/
COPY services/ocr_service/ /app/services/ocr_service/

# Ensure dhara_shared is available in runtime image (imported by OCR service)
COPY dhara_shared/src/dhara_shared/ /usr/local/lib/python3.12/site-packages/dhara_shared/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 10000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:10000/health || exit 1

CMD ["uvicorn", "services.ocr_service.main:app", "--host", "0.0.0.0", "--port", "10000"]
