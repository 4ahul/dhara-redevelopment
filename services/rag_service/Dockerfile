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

# Copy pyproject.toml for dependency resolution
COPY pyproject.toml .

# Install dependencies without package setup
ENV UV_HTTP_TIMEOUT=300
RUN uv pip install --system \
    fastapi \
    uvicorn \
    pydantic \
    pydantic-settings \
    python-multipart \
    requests \
    bcrypt \
    pyjwt \
    psycopg2-binary \
    pymilvus \
    pypdf \
    reportlab \
    langchain-ollama \
    langchain-core \
    langgraph \
    easyocr \
    python-dotenv \
    opencv-python \
    torch \
    torchvision \
    torchaudio \
    langchain-openai \
    langchain-text-splitters \
    sqlalchemy \
    httpx \
    openai \
    google-cloud-discoveryengine \
    starlette \
    itsdangerous \
    beautifulsoup4 \
    redis \
    serpapi

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
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8006"]
