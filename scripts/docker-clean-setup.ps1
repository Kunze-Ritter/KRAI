<#
.SYNOPSIS
    Docker Clean Setup Script for KRAI

.DESCRIPTION
    Performs a complete Docker environment reset including container
    shutdown, volume removal, network pruning, and fresh startup with
    seed data verification.

    This script performs the following operations:
    - Stops all containers
    - Removes all KRAI volumes
    - Prunes Docker networks
    - Starts fresh containers
    - Waits for service initialization
    - Verifies seed data

.EXAMPLE
    .\scripts\docker-clean-setup.ps1

.NOTES
    Requires Docker Desktop for Windows and configured .env file
#>

# Set error action preference for fail-fast behavior
$ErrorActionPreference = "Stop"

# Docker Compose command (will be detected)
$script:DockerComposeCmd = $null

# Helper functions for colored output
function Write-Status {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] ✓ $Message" -ForegroundColor Green
}

function Write-ErrorMessage {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] ⚠ $Message" -ForegroundColor Yellow
}

function Write-InfoMessage {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Blue
}

# Detect Docker Compose command
function Find-DockerCompose {
    try {
        if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
            $script:DockerComposeCmd = "docker-compose"
            return $true
        }
        elseif ((docker compose version 2>$null) -and $LASTEXITCODE -eq 0) {
            $script:DockerComposeCmd = "docker compose"
            return $true
        }
        else {
            return $false
        }
    }
    catch {
        return $false
    }
}

# Check prerequisites
function Test-Prerequisites {
    Write-Status "Step 1/7: Checking prerequisites..."

    $allOk = $true

    # Check Docker
    try {
        if (Get-Command docker -ErrorAction SilentlyContinue) {
            Write-Success "Docker is available"
        }
        else {
            Write-ErrorMessage "Docker is not installed or not in PATH"
            $allOk = $false
        }
    }
    catch {
        Write-ErrorMessage "Docker is not installed or not in PATH"
        $allOk = $false
    }

    # Check Docker Compose
    if (Find-DockerCompose) {
        Write-Success "Docker Compose is available ($script:DockerComposeCmd)"
    }
    else {
        Write-ErrorMessage "Docker Compose is not installed or not in PATH"
        $allOk = $false
    }

    # Check .env file
    if (Test-Path ".env") {
        Write-Success ".env file found"
    }
    else {
        Write-ErrorMessage ".env file not found in project root"
        $allOk = $false
    }

    if (-not $allOk) {
        Write-ErrorMessage "Prerequisites check failed"
        exit 1
    }

    return $true
}

# Stop all containers
function Stop-DockerContainers {
    Write-Status "Step 2/7: Stopping all Docker containers..."

    try {
        if ($script:DockerComposeCmd -eq "docker-compose") {
            & docker-compose down 2>&1 | Out-Null
        }
        else {
            & docker compose down 2>&1 | Out-Null
        }

        if ($LASTEXITCODE -eq 0) {
            Write-Success "Containers stopped successfully"
            return $true
        }
        else {
            Write-ErrorMessage "Failed to stop containers"
            return $false
        }
    }
    catch {
        Write-ErrorMessage "Failed to stop containers: $_"
        return $false
    }
}

# Remove KRAI volumes
function Remove-KraiVolumes {
    Write-Status "Step 3/7: Removing KRAI volumes..."

    $volumes = @(
        'krai_postgres_data',
        'krai_minio_data',
        'minio_data',
        'krai_ollama_data',
        'ollama_data',
        'krai_redis_data',
        'redis_data',
        'laravel_vendor',
        'laravel_node_modules'
    )

    foreach ($volumeName in $volumes) {
        try {
            $volumeExists = docker volume ls -q | Select-String -Pattern "^$volumeName$" -Quiet

            if ($volumeExists) {
                docker volume rm $volumeName 2>&1 | Out-Null
                if ($LASTEXITCODE -eq 0) {
                    Write-Success "Removed volume: $volumeName"
                }
                else {
                    Write-Warning "Failed to remove volume: $volumeName (may be in use)"
                }
            }
            else {
                Write-InfoMessage "Volume not found: $volumeName (skipping)"
            }
        }
        catch {
            Write-Warning "Error processing volume ${volumeName}: $_"
        }
    }

    return $true
}

# Prune Docker networks
function Invoke-NetworkPrune {
    Write-Status "Step 4/7: Pruning Docker networks..."

    try {
        $output = docker network prune -f 2>&1
        Write-Success "Networks pruned successfully"
        return $true
    }
    catch {
        Write-Warning "Network prune encountered an issue: $_"
        return $true
    }
}

# Start containers
function Start-DockerContainers {
    Write-Status "Step 5/7: Starting fresh Docker containers..."

    try {
        if ($script:DockerComposeCmd -eq "docker-compose") {
            & docker-compose up -d 2>&1 | Out-Null
        }
        else {
            & docker compose up -d 2>&1 | Out-Null
        }

        if ($LASTEXITCODE -eq 0) {
            Write-Success "Containers started successfully"
            return $true
        }
        else {
            Write-ErrorMessage "Failed to start containers"
            return $false
        }
    }
    catch {
        Write-ErrorMessage "Failed to start containers: $_"
        return $false
    }
}

# Wait for services to initialize
function Wait-ForServices {
    Write-Status "Step 6/7: Waiting 60 seconds for services to initialize..."

    for ($i = 60; $i -ge 1; $i--) {
        Write-Progress -Activity "Initializing Services" -Status "Time remaining: $i seconds" -PercentComplete ((60 - $i) / 60 * 100)
        Start-Sleep -Seconds 1
    }

    Write-Progress -Activity "Initializing Services" -Completed
    Write-Success "Service initialization wait completed"
    return $true
}

# Load environment variables from .env file
function Get-EnvVariable {
    param(
        [string]$Name,
        [string]$Default = ""
    )

    if (Test-Path ".env") {
        $envContent = Get-Content ".env" -ErrorAction SilentlyContinue
        foreach ($line in $envContent) {
            if ($line -match "^$Name=(.+)$") {
                return $matches[1].Trim('"').Trim("'")
            }
        }
    }

    return $Default
}

# Verify seed data
function Test-SeedData {
    Write-Status "Step 7/7: Verifying seed data..."

    # Load database credentials from .env
    $dbHost = Get-EnvVariable -Name "DATABASE_HOST" -Default "localhost"
    $dbPort = Get-EnvVariable -Name "DATABASE_PORT" -Default "5432"
    $dbName = Get-EnvVariable -Name "DATABASE_NAME" -Default "krai"
    $dbUser = Get-EnvVariable -Name "DATABASE_USER" -Default "krai_user"

    # Detect PostgreSQL container name
    $pgContainer = $null
    $containers = docker ps --filter "name=krai-postgres" --format "{{.Names}}" 2>$null

    if ($containers -match "krai-postgres-prod") {
        $pgContainer = "krai-postgres-prod"
    }
    elseif ($containers -match "krai-postgres") {
        $pgContainer = "krai-postgres"
    }
    else {
        Write-Warning "PostgreSQL container not found, skipping seed data verification"
        return $true
    }

    Write-InfoMessage "Using PostgreSQL container: $pgContainer"

    $verificationFailed = $false

    # Verify manufacturers (expected: 14)
    try {
        $manufacturersResult = docker exec $pgContainer psql -U $dbUser -d $dbName -t -c "SELECT COUNT(*) FROM krai_core.manufacturers;" 2>$null
        $manufacturersCount = [int]($manufacturersResult.Trim())

        if ($manufacturersCount -eq 14) {
            Write-Success "Manufacturers count verified: 14"
        }
        else {
            Write-Warning "Manufacturers count mismatch: expected 14, got $manufacturersCount"
            $verificationFailed = $true
        }
    }
    catch {
        Write-Warning "Failed to verify manufacturers count: $_"
        $verificationFailed = $true
    }

    # Verify retry policies (expected: 4)
    try {
        $retryPoliciesResult = docker exec $pgContainer psql -U $dbUser -d $dbName -t -c "SELECT COUNT(*) FROM krai_system.retry_policies;" 2>$null
        $retryPoliciesCount = [int]($retryPoliciesResult.Trim())

        if ($retryPoliciesCount -eq 4) {
            Write-Success "Retry policies count verified: 4"
        }
        else {
            Write-Warning "Retry policies count mismatch: expected 4, got $retryPoliciesCount"
            $verificationFailed = $true
        }
    }
    catch {
        Write-Warning "Failed to verify retry policies count: $_"
        $verificationFailed = $true
    }

    if ($verificationFailed) {
        return $false
    }

    return $true
}

# Main execution
function Main {
    Write-Host ""
    Write-Host "╔════════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "║  KRAI Docker Clean Setup Script           ║" -ForegroundColor Green
    Write-Host "╚════════════════════════════════════════════╝" -ForegroundColor Green
    Write-Host ""

    $overallSuccess = $true

    try {
        # Execute workflow
        if (-not (Test-Prerequisites)) {
            $overallSuccess = $false
        }

        if ($overallSuccess -and -not (Stop-DockerContainers)) {
            $overallSuccess = $false
        }

        if ($overallSuccess -and -not (Remove-KraiVolumes)) {
            $overallSuccess = $false
        }

        if ($overallSuccess -and -not (Invoke-NetworkPrune)) {
            $overallSuccess = $false
        }

        if ($overallSuccess -and -not (Start-DockerContainers)) {
            $overallSuccess = $false
        }

        if ($overallSuccess -and -not (Wait-ForServices)) {
            $overallSuccess = $false
        }

        if ($overallSuccess -and -not (Test-SeedData)) {
            $overallSuccess = $false
        }
    }
    catch {
        Write-ErrorMessage "Unexpected error during execution: $_"
        $overallSuccess = $false
    }

    # Print final summary
    Write-Host ""
    Write-Host "═══════════════════════════════════════════" -ForegroundColor Blue
    if ($overallSuccess) {
        Write-Host "[SUCCESS] ✓ Docker clean setup completed successfully!" -ForegroundColor Green
        Write-Host "═══════════════════════════════════════════" -ForegroundColor Blue
        Write-Host ""
        exit 0
    }
    else {
        Write-Host "[ERROR] ✗ Docker clean setup encountered errors" -ForegroundColor Red
        Write-Host "═══════════════════════════════════════════" -ForegroundColor Blue
        Write-Host ""
        exit 1
    }
}

# Run main function
Main
