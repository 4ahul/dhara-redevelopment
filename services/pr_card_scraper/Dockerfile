FROM python:3.11-slim

WORKDIR /app

# Copy pyproject.toml first so it's available for installation
COPY pyproject.toml .

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    gnupg \
    tesseract-ocr \
    tesseract-ocr-eng \
    libpq-dev \
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
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /etc/apt/trusted.gpg.d/google.gpg \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv playwright

# Install dependencies from pyproject.toml
RUN uv pip install --system .

ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install chromium

COPY core/ ./core/
COPY schemas/ ./schemas/
COPY services/ ./services/
COPY routers/ ./routers/
COPY main.py .
COPY mock_scraper.py .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8006"]
