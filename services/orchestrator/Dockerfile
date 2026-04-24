FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install dhara_shared first
COPY dhara_shared/ /tmp/dhara_shared/
RUN pip install /tmp/dhara_shared && rm -rf /tmp/dhara_shared

# Install service dependencies
COPY services/orchestrator/pyproject.toml ./services/orchestrator/
RUN pip install ./services/orchestrator

# Copy entire service directory to preserve path for absolute imports
COPY services/orchestrator/ ./services/orchestrator/

# Fix Entrypoint path
COPY services/orchestrator/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PYTHONPATH=/app

ENTRYPOINT ["/app/entrypoint.sh"]
# Start using the standardized monorepo path
CMD ["uvicorn", "services.orchestrator.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
