################################################################################
# Docker Health Check Script (Windows PowerShell)
# Validates all KRAI service components with detailed reporting
#
# Usage:
#   .\scripts\docker-health-check.ps1              # Run regular health checks
#   .\scripts\docker-health-check.ps1 -TestPersistency  # Run persistency tests
################################################################################

[CmdletBinding()]
param(
    [switch]$TestPersistency
)

# Script configuration
$ErrorActionPreference = "Continue"
$script:exitCode = 0

# Service endpoints
$POSTGRES_HOST = "localhost"
$POSTGRES_PORT = "5432"
$POSTGRES_USER = "krai_user"
$POSTGRES_DB = "krai"
$BACKEND_URL = "http://localhost:8000"
$LARAVEL_URL = "http://localhost:8080"
$MINIO_API_URL = "http://localhost:9000"
$MINIO_CONSOLE_URL = "http://localhost:9001"
$OLLAMA_URL = "http://localhost:11434"

# Expected values
$EXPECTED_SCHEMAS = 6
$EXPECTED_TABLES = 44
$EXPECTED_MANUFACTURERS = 14
$EXPECTED_RETRY_POLICIES = 4
$EXPECTED_EMBEDDING_DIM = 768

################################################################################
# Helper Functions
################################################################################

function Write-Status {
    param(
        [Parameter(Mandatory=$true)]
        [ValidateSet("success", "warning", "error", "info")]
        [string]$Status,

        [Parameter(Mandatory=$true)]
        [string]$Message
    )

    switch ($Status) {
        "success" {
            Write-Host "✅ $Message" -ForegroundColor Green
        }
        "warning" {
            Write-Host "⚠️  $Message" -ForegroundColor Yellow
        }
        "error" {
            Write-Host "❌ $Message" -ForegroundColor Red
        }
        "info" {
            Write-Host "ℹ️  $Message" -ForegroundColor Cyan
        }
    }
}

function Test-Command {
    param([string]$CommandName)

    $command = Get-Command $CommandName -ErrorAction SilentlyContinue
    if (-not $command) {
        Write-Status "warning" "Command '$CommandName' not found, some checks may be skipped"
        return $false
    }
    return $true
}

function Update-ExitCode {
    param([int]$NewCode)

    if ($NewCode -gt $script:exitCode) {
        $script:exitCode = $NewCode
    }
}

function Get-DockerComposeCommand {
    # Check for docker-compose command
    $dockerCompose = Get-Command docker-compose -ErrorAction SilentlyContinue
    if ($dockerCompose) {
        return "docker-compose"
    }

    # Check for docker compose (plugin)
    try {
        docker compose version 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            return "docker compose"
        }
    } catch {
        # Ignore error
    }

    Write-Status "error" "Neither 'docker-compose' nor 'docker compose' found"
    exit 2
}

################################################################################
# Data Persistency Test Functions
################################################################################

<#
.SYNOPSIS
    Test data persistency across container restarts
.DESCRIPTION
    Verifies that data survives docker-compose down/up cycle by creating test data,
    restarting containers, and verifying the data persisted.
#>
function Test-DataPersistency {
    Write-Status "info" "Testing Data Persistency Across Container Restarts"
    Write-Host ""

    $testName = "TEST_PERSISTENCY_$(Get-Date -Format 'yyyyMMddHHmmss')"
    $testWebsite = "http://test.persistency.local"
    $testId = $null

    # Detect Docker Compose command
    $composeCmd = Get-DockerComposeCommand

    # Create test manufacturer entry
    Write-Status "info" "Creating test data..."
    $insertSql = "INSERT INTO krai_core.manufacturers (name, website, is_active) VALUES ('$testName', '$testWebsite', true) RETURNING id;"

    try {
        $result = docker exec krai-postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -t -c $insertSql 2>$null
        if ($LASTEXITCODE -eq 0) {
            $testId = $result.Trim()
        } else {
            throw "Insert failed"
        }
    } catch {
        Write-Status "error" "Failed to create test data"
        Update-ExitCode 2
        return
    }

    if (-not $testId) {
        Write-Status "error" "Failed to create test data (no ID returned)"
        Update-ExitCode 2
        return
    }

    Write-Status "success" "Test manufacturer created: $testName (ID: $testId)"
    Write-Host ""

    # Stop all containers
    Write-Status "info" "Stopping containers..."
    try {
        if ($composeCmd -eq "docker-compose") {
            docker-compose down 2>$null | Out-Null
        } else {
            docker compose down 2>$null | Out-Null
        }

        if ($LASTEXITCODE -ne 0) {
            throw "Compose down failed"
        }

        Write-Status "success" "Containers stopped"
    } catch {
        Write-Status "error" "Failed to stop containers with '$composeCmd down'"
        Update-ExitCode 2
        return
    }
    Write-Host ""

    # Restart containers
    Write-Status "info" "Starting containers..."
    try {
        if ($composeCmd -eq "docker-compose") {
            docker-compose up -d 2>$null | Out-Null
        } else {
            docker compose up -d 2>$null | Out-Null
        }

        if ($LASTEXITCODE -ne 0) {
            throw "Compose up failed"
        }

        Write-Status "success" "Containers started"
    } catch {
        Write-Status "error" "Failed to start containers with '$composeCmd up -d'"
        Update-ExitCode 2
        return
    }
    Write-Host ""

    # Wait for services to initialize
    Write-Status "info" "Waiting for services to initialize (60 seconds)..."
    for ($i = 60; $i -gt 0; $i--) {
        Write-Host "`r  ⏳ $($i.ToString('00')) seconds remaining..." -NoNewline
        Start-Sleep -Seconds 1
    }
    Write-Host "`r  ✅ Wait complete                    "
    Write-Host ""

    # Verify test data persisted
    Write-Status "info" "Verifying data persistence..."
    $verifySql = "SELECT name, website, is_active FROM krai_core.manufacturers WHERE id = $testId;"

    try {
        $result = docker exec krai-postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -t -c $verifySql 2>$null

        if ($LASTEXITCODE -ne 0 -or -not $result) {
            Write-Status "error" "Test data was lost! Persistency test FAILED"
            Write-Host "  Expected: $testName | $testWebsite | t"
            Write-Host "  Actual: (no data found)"
            Update-ExitCode 2
        } else {
            # Parse result and verify fields
            $fields = $result -split '\|'
            $retrievedName = $fields[0].Trim()
            $retrievedWebsite = $fields[1].Trim()

            if ($retrievedName -eq $testName -and $retrievedWebsite -eq $testWebsite) {
                Write-Status "success" "Data persisted successfully!"
                Write-Host "  Verified: $retrievedName | $retrievedWebsite"
            } else {
                Write-Status "error" "Data integrity issue detected"
                Write-Host "  Expected: $testName | $testWebsite"
                Write-Host "  Actual: $retrievedName | $retrievedWebsite"
                Update-ExitCode 2
            }
        }
    } catch {
        Write-Status "error" "Failed to verify data persistence"
        Update-ExitCode 2
    }
    Write-Host ""

    # Cleanup test data
    Write-Status "info" "Cleaning up test data..."
    $deleteSql = "DELETE FROM krai_core.manufacturers WHERE id = $testId;"

    try {
        docker exec krai-postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -c $deleteSql 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Status "success" "Test data cleaned up"
        } else {
            throw "Delete failed"
        }
    } catch {
        Write-Status "warning" "Failed to clean up test data (ID: $testId)"
        Update-ExitCode 1
    }
}

<#
.SYNOPSIS
    Verify volume mounts are correctly configured
.DESCRIPTION
    Checks that required volumes exist and are mounted to correct containers
#>
function Test-VolumeMounts {
    Write-Status "info" "Volume Mount Verification"
    Write-Host ""

    # Get list of Docker volumes
    try {
        $volumes = docker volume ls --format "{{.Name}}" 2>$null
    } catch {
        Write-Status "error" "Failed to list Docker volumes"
        Update-ExitCode 2
        return
    }

    # Check PostgreSQL volume
    if ($volumes -match "krai_postgres_data") {
        Write-Status "success" "PostgreSQL volume 'krai_postgres_data' exists"

        # Verify mount
        try {
            $pgMount = docker inspect krai-postgres --format '{{range .Mounts}}{{.Name}}{{end}}' 2>$null
            if ($pgMount -match "krai_postgres_data") {
                Write-Status "success" "PostgreSQL volume correctly mounted"
            } else {
                Write-Status "warning" "PostgreSQL volume not mounted to container"
                Update-ExitCode 1
            }
        } catch {
            Write-Status "warning" "Failed to verify PostgreSQL volume mount"
            Update-ExitCode 1
        }
    } else {
        Write-Status "error" "PostgreSQL volume 'krai_postgres_data' not found"
        Write-Host "  Recommendation: Check docker-compose.yml volume configuration"
        Update-ExitCode 2
    }
    Write-Host ""

    # Check MinIO volume (try both naming conventions)
    $minioVolumeFound = $false
    if ($volumes -match "minio_data") {
        Write-Status "success" "MinIO volume 'minio_data' exists"
        $minioVolumeFound = $true
    } elseif ($volumes -match "krai_minio_data") {
        Write-Status "success" "MinIO volume 'krai_minio_data' exists"
        $minioVolumeFound = $true
    }

    if ($minioVolumeFound) {
        try {
            $minioMount = docker inspect krai-minio --format '{{range .Mounts}}{{.Name}}{{end}}' 2>$null
            if ($minioMount -match "minio_data|krai_minio_data") {
                Write-Status "success" "MinIO volume correctly mounted"
            } else {
                Write-Status "warning" "MinIO volume not mounted to container"
                Update-ExitCode 1
            }
        } catch {
            Write-Status "warning" "Failed to verify MinIO volume mount"
            Update-ExitCode 1
        }
    } else {
        Write-Status "warning" "MinIO volume not found (checked 'minio_data' and 'krai_minio_data')"
        Update-ExitCode 1
    }
    Write-Host ""

    # Check Ollama volume (try both naming conventions)
    $ollamaVolumeFound = $false
    if ($volumes -match "ollama_data") {
        Write-Status "success" "Ollama volume 'ollama_data' exists"
        $ollamaVolumeFound = $true
    } elseif ($volumes -match "krai_ollama_data") {
        Write-Status "success" "Ollama volume 'krai_ollama_data' exists"
        $ollamaVolumeFound = $true
    }

    if ($ollamaVolumeFound) {
        try {
            $ollamaMount = docker inspect krai-ollama --format '{{range .Mounts}}{{.Name}}{{end}}' 2>$null
            if ($ollamaMount -match "ollama_data|krai_ollama_data") {
                Write-Status "success" "Ollama volume correctly mounted"
            } else {
                Write-Status "warning" "Ollama volume not mounted to container"
                Update-ExitCode 1
            }
        } catch {
            Write-Status "warning" "Failed to verify Ollama volume mount"
            Update-ExitCode 1
        }
    } else {
        Write-Status "warning" "Ollama volume not found (checked 'ollama_data' and 'krai_ollama_data')"
        Update-ExitCode 1
    }
    Write-Host ""

    # Check Redis volume
    if ($volumes -match "redis_data") {
        Write-Status "success" "Redis volume 'redis_data' exists"
    } else {
        Write-Status "warning" "Redis volume 'redis_data' not found"
        Update-ExitCode 1
    }
}

################################################################################
# PostgreSQL Health Check
################################################################################

function Test-PostgreSQL {
    Write-Status "info" "Checking PostgreSQL..."

    # Test connection
    try {
        $result = docker exec krai-postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT 1" 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Status "success" "PostgreSQL connection successful"
        } else {
            throw "Connection failed"
        }
    } catch {
        Write-Status "error" "PostgreSQL connection failed"
        Write-Host "  Recommendation: Check PostgreSQL logs: docker logs krai-postgres"
        Update-ExitCode 2
        return
    }

    # Check schema count
    try {
        $schemaCount = docker exec krai-postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -t -c "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name LIKE 'krai_%'" 2>$null
        $schemaCount = $schemaCount.Trim()

        if ([int]$schemaCount -eq $EXPECTED_SCHEMAS) {
            Write-Status "success" "Schema count: $schemaCount (expected: $EXPECTED_SCHEMAS)"
        } else {
            Write-Status "error" "Schema count: $schemaCount (expected: $EXPECTED_SCHEMAS)"
            Write-Host "  Recommendation: Run database migrations: docker exec krai-postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -f /docker-entrypoint-initdb.d/001_core_schema.sql"
            Update-ExitCode 2
        }
    } catch {
        Write-Status "error" "Failed to check schema count"
        Update-ExitCode 2
    }

    # Check table count
    try {
        $tableCount = docker exec krai-postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema LIKE 'krai_%' AND table_type = 'BASE TABLE'" 2>$null
        $tableCount = $tableCount.Trim()

        if ([int]$tableCount -eq $EXPECTED_TABLES) {
            Write-Status "success" "Table count: $tableCount (expected: $EXPECTED_TABLES)"
        } else {
            Write-Status "error" "Table count: $tableCount (expected: $EXPECTED_TABLES)"
            Write-Host "  Recommendation: Run database migrations in database/migrations_postgresql/"
            Update-ExitCode 2
        }
    } catch {
        Write-Status "error" "Failed to check table count"
        Update-ExitCode 2
    }

    # Check manufacturers
    try {
        $mfrCount = docker exec krai-postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -t -c "SELECT COUNT(*) FROM krai_core.manufacturers" 2>$null
        $mfrCount = $mfrCount.Trim()

        if ([int]$mfrCount -ge $EXPECTED_MANUFACTURERS) {
            Write-Status "success" "Manufacturers: $mfrCount (expected: >=$EXPECTED_MANUFACTURERS)"
        } else {
            Write-Status "warning" "Manufacturers: $mfrCount (expected: >=$EXPECTED_MANUFACTURERS)"
            Write-Host "  Recommendation: Load seed data: docker exec krai-postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -f /docker-entrypoint-initdb.d/030_seeds.sql"
            Update-ExitCode 1
        }
    } catch {
        Write-Status "warning" "Failed to check manufacturers"
        Update-ExitCode 1
    }

    # Check retry policies
    try {
        $retryCount = docker exec krai-postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -t -c "SELECT COUNT(*) FROM krai_system.retry_policies" 2>$null
        $retryCount = $retryCount.Trim()

        if ([int]$retryCount -ge $EXPECTED_RETRY_POLICIES) {
            Write-Status "success" "Retry policies: $retryCount (expected: >=$EXPECTED_RETRY_POLICIES)"
        } else {
            Write-Status "warning" "Retry policies: $retryCount (expected: >=$EXPECTED_RETRY_POLICIES)"
            Write-Host "  Recommendation: Load seed data for retry policies"
            Update-ExitCode 1
        }
    } catch {
        Write-Status "warning" "Failed to check retry policies"
        Update-ExitCode 1
    }

    # Check pgvector extension
    try {
        $pgvectorVersion = docker exec krai-postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -t -c "SELECT extversion FROM pg_extension WHERE extname = 'vector'" 2>$null
        $pgvectorVersion = $pgvectorVersion.Trim()

        if ($pgvectorVersion) {
            Write-Status "success" "pgvector extension: v$pgvectorVersion"
        } else {
            Write-Status "error" "pgvector extension not found"
            Write-Host "  Recommendation: Install pgvector extension: CREATE EXTENSION vector;"
            Update-ExitCode 2
        }
    } catch {
        Write-Status "error" "Failed to check pgvector extension"
        Update-ExitCode 2
    }
}

################################################################################
# FastAPI Backend Health Check
################################################################################

function Test-FastAPIBackend {
    Write-Status "info" "Checking FastAPI Backend..."

    # Test /health endpoint
    try {
        $response = Invoke-RestMethod -Uri "$BACKEND_URL/health" -Method Get -TimeoutSec 10 -ErrorAction Stop
        Write-Status "success" "Backend /health endpoint responding"

        # Parse response
        if ($response.database) {
            Write-Host "  Database: $($response.database)"
        }
        if ($response.storage) {
            Write-Host "  Storage: $($response.storage)"
        }
        if ($response.ai) {
            Write-Host "  AI: $($response.ai)"
        }

        if ($response.database -ne "healthy" -or $response.storage -ne "healthy") {
            Write-Status "warning" "Some backend services are not healthy"
            Update-ExitCode 1
        }
    } catch {
        Write-Status "error" "Backend /health endpoint not responding"
        Write-Host "  Recommendation: Check backend logs: docker logs krai-engine"
        Update-ExitCode 2
        return
    }

    # Test /docs endpoint
    try {
        $response = Invoke-WebRequest -Uri "$BACKEND_URL/docs" -Method Head -TimeoutSec 5 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            Write-Status "success" "Backend /docs (Swagger UI) accessible"
        }
    } catch {
        Write-Status "warning" "Backend /docs endpoint not accessible"
        Update-ExitCode 1
    }

    # Test /redoc endpoint
    try {
        $response = Invoke-WebRequest -Uri "$BACKEND_URL/redoc" -Method Head -TimeoutSec 5 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            Write-Status "success" "Backend /redoc (ReDoc) accessible"
        }
    } catch {
        Write-Status "warning" "Backend /redoc endpoint not accessible"
        Update-ExitCode 1
    }
}

################################################################################
# Laravel Admin Health Check
################################################################################

function Test-LaravelAdmin {
    Write-Status "info" "Checking Laravel Admin Dashboard..."

    # Test dashboard accessibility
    try {
        $response = Invoke-WebRequest -Uri "$LARAVEL_URL/kradmin" -Method Get -TimeoutSec 10 -ErrorAction Stop
        Write-Status "success" "Laravel dashboard accessible"
    } catch {
        Write-Status "error" "Laravel dashboard not accessible"
        Write-Host "  Recommendation: Check nginx logs: docker logs krai-laravel-nginx"
        Write-Host "  Recommendation: Check Laravel logs: docker logs krai-laravel-admin"
        Update-ExitCode 2
        return
    }

    # Test login page
    try {
        $response = Invoke-WebRequest -Uri "$LARAVEL_URL/kradmin/login" -Method Get -TimeoutSec 5 -ErrorAction Stop
        Write-Status "success" "Laravel login page accessible"
    } catch {
        Write-Status "warning" "Laravel login page not accessible"
        Update-ExitCode 1
    }

    # Test database connection via artisan
    try {
        $result = docker exec krai-laravel-admin php artisan db:show 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Status "success" "Laravel database connection successful"
        } else {
            throw "Database connection failed"
        }
    } catch {
        Write-Status "error" "Laravel database connection failed"
        Write-Host "  Recommendation: Check .env configuration in laravel-admin/"
        Update-ExitCode 2
    }

    # List Filament resources
    Write-Status "info" "Checking Filament resources..."
    $resources = @("documents", "products", "manufacturers", "users", "pipeline-errors", "alert-configurations")
    $resourceCount = 0

    foreach ($resource in $resources) {
        try {
            $response = Invoke-WebRequest -Uri "$LARAVEL_URL/kradmin/$resource" -Method Head -TimeoutSec 3 -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200 -or $response.StatusCode -eq 302) {
                $resourceCount++
            }
        } catch {
            try {
                $response = Invoke-WebRequest -Uri "$LARAVEL_URL/kradmin/resources/$resource" -Method Head -TimeoutSec 3 -ErrorAction SilentlyContinue
                if ($response.StatusCode -eq 200 -or $response.StatusCode -eq 302) {
                    $resourceCount++
                }
            } catch {
                # Resource not accessible
            }
        }
    }

    if ($resourceCount -ge 3) {
        Write-Status "success" "Filament resources accessible ($resourceCount/$($resources.Count))"
    } else {
        Write-Status "warning" "Limited Filament resources accessible ($resourceCount/$($resources.Count))"
        Update-ExitCode 1
    }
}

################################################################################
# MinIO Health Check
################################################################################

function Test-MinIO {
    Write-Status "info" "Checking MinIO..."

    # Test API endpoint
    try {
        $response = Invoke-WebRequest -Uri "$MINIO_API_URL/minio/health/live" -Method Get -TimeoutSec 5 -ErrorAction Stop
        Write-Status "success" "MinIO API responding"
    } catch {
        Write-Status "error" "MinIO API not responding"
        Write-Host "  Recommendation: Check MinIO logs: docker logs krai-minio"
        Update-ExitCode 2
        return
    }

    # Test console accessibility
    try {
        $response = Invoke-WebRequest -Uri $MINIO_CONSOLE_URL -Method Head -TimeoutSec 5 -ErrorAction Stop
        if ($response.StatusCode -in @(200, 301, 302)) {
            Write-Status "success" "MinIO console accessible"
        }
    } catch {
        Write-Status "warning" "MinIO console not accessible"
        Update-ExitCode 1
    }

    # Test bucket operations (if mc command available)
    if (Test-Command "mc") {
        $testBucket = "health-check-test-$(Get-Date -Format 'yyyyMMddHHmmss')"

        # Read MinIO credentials from environment or use defaults
        $minioAccessKey = if ($env:OBJECT_STORAGE_ACCESS_KEY) { $env:OBJECT_STORAGE_ACCESS_KEY } else { "minioadmin" }
        $minioSecretKey = if ($env:OBJECT_STORAGE_SECRET_KEY) { $env:OBJECT_STORAGE_SECRET_KEY } else { "minioadmin123" }

        # Configure mc alias
        mc alias set local $MINIO_API_URL $minioAccessKey $minioSecretKey 2>$null | Out-Null

        # Create test bucket
        try {
            mc mb "local/$testBucket" 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Status "success" "MinIO bucket creation successful"

                # Upload test file
                "test" | mc pipe "local/$testBucket/test.txt" 2>$null | Out-Null
                if ($LASTEXITCODE -eq 0) {
                    Write-Status "success" "MinIO file upload successful"

                    # Download test file
                    mc cat "local/$testBucket/test.txt" 2>$null | Out-Null
                    if ($LASTEXITCODE -eq 0) {
                        Write-Status "success" "MinIO file download successful"
                    }
                }

                # Cleanup
                mc rm "local/$testBucket/test.txt" 2>$null | Out-Null
                mc rb "local/$testBucket" 2>$null | Out-Null
            } else {
                throw "Bucket creation failed"
            }
        } catch {
            Write-Status "warning" "MinIO bucket operations not tested (permissions issue)"
            Write-Host "  Recommendation: Initialize MinIO: python scripts/init_minio.py"
            Update-ExitCode 1
        }
    } else {
        Write-Status "info" "MinIO client (mc) not found, skipping bucket operation tests"
    }
}

################################################################################
# Ollama Health Check
################################################################################

function Test-Ollama {
    Write-Status "info" "Checking Ollama..."

    # Test API availability
    try {
        $response = Invoke-RestMethod -Uri "$OLLAMA_URL/api/tags" -Method Get -TimeoutSec 10 -ErrorAction Stop
        Write-Status "success" "Ollama API responding"
    } catch {
        Write-Status "error" "Ollama API not responding"
        Write-Host "  Recommendation: Check Ollama logs: docker logs krai-ollama"
        Update-ExitCode 2
        return
    }

    # Check model presence
    try {
        $models = Invoke-RestMethod -Uri "$OLLAMA_URL/api/tags" -Method Get -TimeoutSec 10 -ErrorAction Stop
        $hasModel = $false

        foreach ($model in $models.models) {
            if ($model.name -like "*nomic-embed-text*") {
                $hasModel = $true
                break
            }
        }

        if ($hasModel) {
            Write-Status "success" "Model 'nomic-embed-text' found"
        } else {
            Write-Status "error" "Model 'nomic-embed-text' not found"
            Write-Host "  Recommendation: Pull model: docker exec krai-ollama ollama pull nomic-embed-text"
            Update-ExitCode 2
            return
        }
    } catch {
        Write-Status "error" "Failed to check models"
        Update-ExitCode 2
        return
    }

    # Test embedding generation
    try {
        $body = @{
            model = "nomic-embed-text"
            prompt = "test"
        } | ConvertTo-Json

        $response = Invoke-RestMethod -Uri "$OLLAMA_URL/api/embeddings" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 30 -ErrorAction Stop

        if ($response.embedding) {
            $embedDim = $response.embedding.Count

            if ($embedDim -eq $EXPECTED_EMBEDDING_DIM) {
                Write-Status "success" "Embedding generation successful (dim: $embedDim)"
            } else {
                Write-Status "warning" "Embedding dimension mismatch: $embedDim (expected: $EXPECTED_EMBEDDING_DIM)"
                Update-ExitCode 1
            }
        } else {
            Write-Status "error" "Embedding generation failed (no embedding in response)"
            Update-ExitCode 2
        }
    } catch {
        Write-Status "error" "Embedding generation failed"
        Write-Host "  Recommendation: Verify model is loaded: docker exec krai-ollama ollama list"
        Update-ExitCode 2
    }
}

################################################################################
# Main Execution
################################################################################

function Main {
    Write-Host "==================================" -ForegroundColor Cyan
    if ($TestPersistency) {
        Write-Host "KRAI Data Persistency Tests" -ForegroundColor Cyan
    } else {
        Write-Host "KRAI Docker Health Check" -ForegroundColor Cyan
    }
    Write-Host "==================================" -ForegroundColor Cyan
    Write-Host ""

    # Check required commands
    Write-Status "info" "Checking required commands..."
    if (-not (Test-Command "docker")) {
        Write-Status "error" "Docker is required"
        exit 2
    }

    Write-Host ""

    # Run persistency tests or regular health checks
    if ($TestPersistency) {
        # Run persistency tests
        Test-DataPersistency
        Write-Host ""

        Test-VolumeMounts
        Write-Host ""

        # Generate summary
        Write-Host "==================================" -ForegroundColor Cyan
        Write-Host "Persistency Test Summary" -ForegroundColor Cyan
        Write-Host "==================================" -ForegroundColor Cyan

        if ($script:exitCode -eq 0) {
            Write-Status "success" "All persistency tests passed! Data survives container restarts."
        } elseif ($script:exitCode -eq 1) {
            Write-Status "warning" "Some warnings detected. Volumes may have configuration issues."
        } else {
            Write-Status "error" "Critical errors detected. Data persistency is not working properly."
        }
    } else {
        # Run all regular health checks
        Test-PostgreSQL
        Write-Host ""

        Test-FastAPIBackend
        Write-Host ""

        Test-LaravelAdmin
        Write-Host ""

        Test-MinIO
        Write-Host ""

        Test-Ollama
        Write-Host ""

        # Generate summary
        Write-Host "==================================" -ForegroundColor Cyan
        Write-Host "Health Check Summary" -ForegroundColor Cyan
        Write-Host "==================================" -ForegroundColor Cyan

        if ($script:exitCode -eq 0) {
            Write-Status "success" "All checks passed successfully!"
        } elseif ($script:exitCode -eq 1) {
            Write-Status "warning" "Some warnings detected. System is functional but may have degraded performance."
        } else {
            Write-Status "error" "Critical errors detected. System may not function properly."
        }
    }

    Write-Host ""
    Write-Host "Exit code: $script:exitCode"
    exit $script:exitCode
}

# Run main function
Main
