FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy core application files
COPY *.py ./
COPY scripts/ scripts/
COPY data/ data/
COPY core/ core/
COPY db/ db/
COPY routers/ routers/
COPY schemas/ schemas/
COPY services/ services/

# Create necessary directories
RUN mkdir -p logs data/docs data/vectors reports

# Environment Variables (Defaults)
ENV PORT=8007
ENV HOST=0.0.0.0
ENV MILVUS_HOST=milvus
ENV MILVUS_PORT=19530

# Expose backend port
EXPOSE 8007

# Start FastAPI server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8007"]
