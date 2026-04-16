FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv

COPY pyproject.toml .
RUN uv pip install --system .

COPY core/ ./core/
COPY schemas/ ./schemas/
COPY services/ ./services/
COPY routers/ ./routers/
COPY templates/ ./templates/
COPY main.py .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8005"]
