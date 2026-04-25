FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Tesseract and OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install dhara_shared
COPY dhara_shared/ /tmp/dhara_shared/
RUN pip install /tmp/dhara_shared && rm -rf /tmp/dhara_shared

# Install dependencies
COPY services/pr_card_scraper/pyproject.toml ./services/pr_card_scraper/
RUN pip install ./services/pr_card_scraper/

# Copy packages preserving path
COPY services/__init__.py ./services/
COPY services/pr_card_scraper/ ./services/pr_card_scraper/
COPY services/pr_card_scraper/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PYTHONPATH=/app

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "services.pr_card_scraper.main:app", "--host", "0.0.0.0", "--port", "8005"]
