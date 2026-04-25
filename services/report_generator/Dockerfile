FROM python:3.11-slim

WORKDIR /app

# Install LibreOffice for PDF conversion
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libreoffice \
    && rm -rf /var/lib/apt/lists/*

# Install dhara_shared
COPY dhara_shared/ /tmp/dhara_shared/
RUN pip install /tmp/dhara_shared && rm -rf /tmp/dhara_shared

# Install dependencies
COPY services/report_generator/pyproject.toml ./services/report_generator/
RUN pip install ./services/report_generator/

# Copy packages preserving path
COPY services/__init__.py ./services/
COPY services/report_generator/ ./services/report_generator/
COPY services/report_generator/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PYTHONPATH=/app

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "services.report_generator.main:app", "--host", "0.0.0.0", "--port", "8004"]
