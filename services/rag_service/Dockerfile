FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install dhara_shared
COPY dhara_shared/ /tmp/dhara_shared/
RUN pip install /tmp/dhara_shared && rm -rf /tmp/dhara_shared

# Install dependencies
COPY services/rag_service/pyproject.toml ./services/rag_service/
RUN pip install ./services/rag_service/

# Copy packages preserving path
COPY services/rag_service/ ./services/rag_service/
COPY services/rag_service/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PYTHONPATH=/app

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "services.rag_service.main:app", "--host", "0.0.0.0", "--port", "8006"]
