#!/bin/bash
# DCPR RAG + Property Card Analysis System Startup Script

set -e

echo "================================================"
echo "DCPR RAG + Property Card Analysis System"
echo "================================================"

cd /home/ubuntu/rag_system

# Check if Docker is running
echo ""
echo "Checking Docker..."
if ! docker info > /dev/null 2>&1; then
    echo "Docker not running. Starting Docker daemon..."
    sudo dockerd > /tmp/dockerd.log 2>&1 &
    sleep 5
fi

# Check if Milvus stack is running
echo ""
echo "Checking Milvus stack..."
if ! docker ps | grep -q milvus 2>/dev/null; then
    echo "Starting Milvus stack (etcd + minio + milvus)..."
    sudo docker-compose -f docker-compose.milvus.yml up -d
    echo "Waiting for services to start..."
    sleep 30
else
    echo "Milvus stack already running"
fi

# Check if Milvus is ready
echo ""
echo "Checking Milvus readiness..."
for i in {1..15}; do
    if nc -z localhost 19530 2>/dev/null; then
        echo "Milvus is ready on port 19530!"
        break
    fi
    echo "  Waiting... ($i/15)"
    sleep 2
done

# Activate virtual environment
echo ""
echo "Activating Python environment..."
source .venv/bin/activate

# Verify Milvus connection
echo ""
echo "Verifying Milvus connection..."
python3 -c "
from pymilvus import connections
connections.connect('default', host='localhost', port='19530')
print('Milvus connection successful!')
connections.disconnect('default')
" || echo "Warning: Could not connect to Milvus"

# Check indexed documents
echo ""
echo "Checking indexed documents..."
python3 -c "
from pymilvus import connections, utility, Collection
connections.connect('default', host='localhost', port='19530')
if utility.has_collection('documents'):
    c = Collection('documents')
    print(f'DCPR indexed: {c.num_entities} chunks')
else:
    print('No documents indexed - run: python3 cli.py index --rebuild')
connections.disconnect('default')
"

# Check Ollama
echo ""
echo "Checking Ollama..."
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "Ollama is running"
else
    echo "Warning: Ollama not running. Start with: ollama serve"
fi

echo ""
echo "================================================"
echo "System Ready!"
echo "================================================"
echo ""
echo "Available commands:"
echo ""
echo "  Query DCPR:     python3 cli.py query \"What is FSI for residential?\""
echo "  Analyze:        python3 cli.py analyze --survey-no 123P --area 2200 --road-width 12"
echo "  Compare:        python3 cli.py compare --area 2200"
echo "  Stats:         python3 cli.py stats"
echo "  Interactive:   python3 cli.py interactive"
echo ""
echo "Property card workflows:"
echo "  Scan PDF:       python3 cli.py scan --input card.pdf"
echo "  Parse Report:  python3 -c \"from property_card_workflow import LandWiseReportParser; a = LandWiseReportParser.parse_financial_summary('report.pdf')\""
echo ""
echo "================================================"
