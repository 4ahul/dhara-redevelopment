FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install dhara_shared
COPY dhara_shared/ /tmp/dhara_shared/
RUN pip install /tmp/dhara_shared && rm -rf /tmp/dhara_shared

# Install dependencies
COPY services/ready_reckoner/pyproject.toml ./services/ready_reckoner/
RUN pip install ./services/ready_reckoner/

# Copy packages preserving path
COPY services/__init__.py ./services/
COPY services/ready_reckoner/ ./services/ready_reckoner/
COPY services/ready_reckoner/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PYTHONPATH=/app

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "services.ready_reckoner.main:app", "--host", "0.0.0.0", "--port", "8003"]
