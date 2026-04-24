FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install dhara_shared
COPY dhara_shared/ /tmp/dhara_shared/
RUN pip install /tmp/dhara_shared && rm -rf /tmp/dhara_shared

# Install dependencies
COPY services/dp_remarks_report/pyproject.toml ./services/dp_remarks_report/
RUN pip install ./services/dp_remarks_report/

# Copy packages preserving path
COPY services/dp_remarks_report/ ./services/dp_remarks_report/
COPY services/dp_remarks_report/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PYTHONPATH=/app

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "services.dp_remarks_report.main:app", "--host", "0.0.0.0", "--port", "8008"]
