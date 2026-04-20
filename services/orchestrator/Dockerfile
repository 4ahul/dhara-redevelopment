FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv

# Install dependencies only (no local package install to avoid stale code)
COPY pyproject.toml .
# If you have a requirements.txt, use that. Otherwise, install from pyproject.
RUN uv pip install --system .

# Copy packages in dependency order (for image stability)
COPY core/ ./core/
COPY db/ ./db/
COPY models/ ./models/
COPY schemas/ ./schemas/
COPY services/ ./services/
COPY agent/ ./agent/
COPY routers/ ./routers/
COPY main.py .


# Force Python to look at the local folder BEFORE system packages
ENV PYTHONPATH=/app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
