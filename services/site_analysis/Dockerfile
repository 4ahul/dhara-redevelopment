FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install dhara_shared
COPY dhara_shared/ /tmp/dhara_shared/
RUN pip install /tmp/dhara_shared && rm -rf /tmp/dhara_shared

# Install dependencies
COPY services/site_analysis/pyproject.toml ./services/site_analysis/
RUN pip install ./services/site_analysis/

# Copy packages preserving path
COPY services/__init__.py ./services/
COPY services/site_analysis/ ./services/site_analysis/
COPY services/site_analysis/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PYTHONPATH=/app

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "services.site_analysis.main:app", "--host", "0.0.0.0", "--port", "8001"]
