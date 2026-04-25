FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install dhara_shared
COPY dhara_shared/ /tmp/dhara_shared/
RUN pip install /tmp/dhara_shared && rm -rf /tmp/dhara_shared

# Install dependencies
COPY services/mcgm_property_lookup/pyproject.toml ./services/mcgm_property_lookup/
RUN pip install ./services/mcgm_property_lookup/

# Copy packages preserving path
COPY services/__init__.py ./services/
COPY services/mcgm_property_lookup/ ./services/mcgm_property_lookup/
COPY services/mcgm_property_lookup/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PYTHONPATH=/app

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "services.mcgm_property_lookup.main:app", "--host", "0.0.0.0", "--port", "8007"]
