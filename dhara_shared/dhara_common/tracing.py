import os
import logging
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.sdk.resources import RESOURCE_ATTRIBUTES, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

logger = logging.getLogger(__name__)

def setup_tracing(app: FastAPI, service_name: str):
    """Setup OpenTelemetry tracing for a FastAPI service."""
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4318")
    
    # 1. Initialize Resource and Provider
    resource = Resource.create(attributes={
        RESOURCE_ATTRIBUTES.SERVICE_NAME: service_name
    })
    
    provider = TracerProvider(resource=resource)
    
    # 2. Add OTLP Exporter (connects to Jaeger/Grafana)
    try:
        exporter = OTLPSpanExporter(endpoint=f"{otlp_endpoint}/v1/traces")
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
        
        # 3. Instrument FastAPI
        FastAPIInstrumentor.instrument_app(app)
        
        # 4. Instrument HTTPX (outgoing calls)
        HTTPXClientInstrumentor().instrument()
        
        logger.info(f"OpenTelemetry Tracing enabled for {service_name} -> {otlp_endpoint}")
    except Exception as e:
        logger.warning(f"Failed to initialize tracing: {e}")

def get_tracer(name: str):
    return trace.get_tracer(name)
