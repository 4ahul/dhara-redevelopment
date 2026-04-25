FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install dhara_shared
COPY dhara_shared/ /tmp/dhara_shared/
RUN pip install /tmp/dhara_shared && rm -rf /tmp/dhara_shared

# Install dependencies
COPY services/aviation_height/pyproject.toml ./services/aviation_height/
RUN pip install ./services/aviation_height/

# Copy packages preserving path
COPY services/__init__.py ./services/
COPY services/aviation_height/ ./services/aviation_height/
COPY services/aviation_height/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PYTHONPATH=/app

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "services.aviation_height.main:app", "--host", "0.0.0.0", "--port", "8002"]
