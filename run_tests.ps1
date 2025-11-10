# PowerShell script to run tests in Docker container

Write-Host "🧪 Running tests in Docker container..." -ForegroundColor Cyan

# Check if container is running
$containerRunning = docker ps --filter "name=telecaht_bot" --format "{{.Names}}"
if (-not $containerRunning) {
    Write-Host "❌ Container 'telecaht_bot' is not running. Please start it first with: docker-compose up -d" -ForegroundColor Red
    exit 1
}

# Run tests in the container
docker exec -it telecaht_bot pytest $args


