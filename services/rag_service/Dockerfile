FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
RUN pip install uv

WORKDIR /app

# Copy dependency files first for caching
COPY pyproject.toml .

# Install dependencies
ENV UV_HTTP_TIMEOUT=300
RUN uv pip install --system .
RUN pip install pydantic-settings itsdangerous

# Copy the rest of the application
COPY . .

# Create necessary directories
RUN mkdir -p logs data/docs data/vectors reports data/uploads data/workflows data/projects data/templates

# Environment Variables (Defaults)
ENV PORT=8006
ENV HOST=0.0.0.0
ENV PYTHONPATH=/app

# Expose backend port
EXPOSE 8006

# Start FastAPI server
CMD ["uvicorn", "main.py:app", "--host", "0.0.0.0", "--port", "8006"]
