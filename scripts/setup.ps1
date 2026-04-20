# Dhara AI Setup Script for Windows

Write-Host "Setting up Dhara AI Re-Development environment..." -ForegroundColor Cyan

# Create necessary directories
Write-Host "Creating data directories..."
$dirs = @(
    "services\rag_service\data\docs",
    "services\rag_service\data\vectors",
    "services\rag_service\data\uploads",
    "services\rag_service\data\workflows",
    "services\rag_service\data\projects",
    "services\rag_service\data\templates",
    "report_outputs",
    "logs"
)

foreach ($dir in $dirs) {
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "  + Created $dir"
    }
}

# Copy environment file if it doesn't exist
if (!(Test-Path ".env")) {
    Write-Host "Copying .env.example to .env..."
    Copy-Item ".env.example" ".env"
    Write-Host "⚠️  Please update .env with your API keys!" -ForegroundColor Yellow
} else {
    Write-Host ".env file already exists." -ForegroundColor Green
}

Write-Host "`n Setup complete!" -ForegroundColor Green
Write-Host "Next step: docker compose up --build" -ForegroundColor Cyan
