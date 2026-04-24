#!/bin/bash
# Dhara AI Setup Script for Linux/macOS

echo "Setting up Dhara AI Re-Development environment..."

# Create necessary directories
echo "Creating data directories..."
mkdir -p services/rag_service/data/docs
mkdir -p services/rag_service/data/vectors
mkdir -p services/rag_service/data/uploads
mkdir -p services/rag_service/data/workflows
mkdir -p services/rag_service/data/projects
mkdir -p services/rag_service/data/templates
mkdir -p report_outputs
mkdir -p logs

# Copy environment file if it doesn't exist
if [ ! -f .env ]; then
    echo "Copying .env.example to .env..."
    cp .env.example .env
    echo "⚠️  Please update .env with your API keys!"
else
    echo ".env file already exists."
fi

# Set permissions
chmod +x scripts/*.sh 2>/dev/null || true

echo ""
echo "Setup complete!"
echo "Next step: docker compose up --build"
