# PowerShell Integration Tests for KRAI Docker Services
$ErrorActionPreference = "Stop"

# Service endpoints
$script:PostgresHost = "localhost"
$script:PostgresPort = "5432"
$script:PostgresUser = "krai_user"
$script:PostgresDb = "krai"
$script:BackendUrl = "http://localhost:8000"
$script:LaravelUrl = "http://localhost:8080"
$script:MinioApiUrl = "http://localhost:9000"
$script:OllamaUrl = "http://localhost:11434"

# Authentication
$script:BackendToken = $env:BACKEND_API_TOKEN  # Set via environment variable

# Test tracking
$script:ExitCode = 0
$script:TestsPassed = 0
$script:TestsFailed = 0
$script:TestDocumentId = ""
$script:TestImageId = ""
$script:LaravelJwtToken = ""

# Color output functions
function Write-Success {
    param([string]$Message)
    Write-Host "✅ $Message" -ForegroundColor Green
    $script:TestsPassed++
}

function Write-Warning {
    param([string]$Message)
    Write-Host "⚠️  $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "❌ $Message" -ForegroundColor Red
    $script:TestsFailed++
}

function Write-Info {
    param([string]$Message)
    Write-Host "ℹ️  $Message" -ForegroundColor Blue
}

function Set-ExitCode {
    param([string]$Severity)

    if ($Severity -eq "critical" -and $script:ExitCode -lt 2) {
        $script:ExitCode = 2
    }
    elseif ($Severity -eq "warning" -and $script:ExitCode -lt 1) {
        $script:ExitCode = 1
    }
}

function Remove-TestData {
    Write-Info "Cleaning up test data..."

    # Remove test document from PostgreSQL
    if ($script:TestDocumentId) {
        try {
            docker exec krai-postgres-prod psql -U $script:PostgresUser -d $script:PostgresDb -c "DELETE FROM krai_core.documents WHERE document_id = '$($script:TestDocumentId)'" 2>$null | Out-Null
            Write-Info "Removed test document: $($script:TestDocumentId)"
        }
        catch {
            # Ignore cleanup errors
        }
    }

    # Remove test image from MinIO via backend API
    if ($script:TestImageId -and $script:BackendToken) {
        try {
            $headers = @{ "Authorization" = "Bearer $($script:BackendToken)" }
            Invoke-RestMethod -Uri "$($script:BackendUrl)/api/v1/images/$($script:TestImageId)?delete_from_storage=true" -Method Delete -Headers $headers -ErrorAction SilentlyContinue | Out-Null
            Write-Info "Removed test image: $($script:TestImageId)"
        }
        catch {
            # Ignore cleanup errors
        }
    }
}

# Backend → PostgreSQL Tests
function Test-BackendPostgres {
    Write-Info "Testing Backend → PostgreSQL integration..."

    # Query test - check backend health
    try {
        $health = Invoke-RestMethod -Uri "$($script:BackendUrl)/health" -Method Get -ErrorAction Stop
        if ($health.services.database.status -eq "healthy") {
            Write-Success "Backend database connection verified"
        }
        else {
            Write-Error "Backend database status not healthy"
            Set-ExitCode "critical"
        }
    }
    catch {
        Write-Error "Backend health check failed: $_"
        Set-ExitCode "critical"
        return
    }

    # Read manufacturers test
    try {
        $mfrCount = docker exec krai-postgres-prod psql -U $script:PostgresUser -d $script:PostgresDb -t -c "SELECT COUNT(*) FROM krai_core.manufacturers" 2>$null
        $mfrCount = $mfrCount.Trim()

        if ([int]$mfrCount -ge 14) {
            Write-Success "Manufacturers query successful: $mfrCount records"
        }
        else {
            Write-Warning "Manufacturers count lower than expected: $mfrCount"
            Set-ExitCode "warning"
        }
    }
    catch {
        Write-Error "Manufacturers query failed: $_"
        Set-ExitCode "critical"
    }

    # Write test - create test document (requires authentication)
    if (-not $script:BackendToken) {
        Write-Warning "Backend token not set - skipping write tests (set BACKEND_API_TOKEN env var)"
        Set-ExitCode "warning"
        return
    }

    $script:TestDocumentId = "test_integration_$(Get-Date -Format 'yyyyMMddHHmmss')"
    $testDoc = @{
        document_id = $script:TestDocumentId
        filename = "integration_test.pdf"
        file_path = "/tmp/test.pdf"
        file_hash = "test_hash_$(Get-Date -Format 'yyyyMMddHHmmss')"
        file_size = 1024
        mime_type = "application/pdf"
    } | ConvertTo-Json

    try {
        $headers = @{
            "Content-Type" = "application/json"
            "Authorization" = "Bearer $($script:BackendToken)"
        }
        $response = Invoke-RestMethod -Uri "$($script:BackendUrl)/api/v1/documents" -Method Post -Body $testDoc -Headers $headers -ErrorAction Stop

        # Verify document created in database
        $docExists = docker exec krai-postgres-prod psql -U $script:PostgresUser -d $script:PostgresDb -t -c "SELECT COUNT(*) FROM krai_core.documents WHERE document_id = '$($script:TestDocumentId)'" 2>$null
        $docExists = $docExists.Trim()

        if ([int]$docExists -eq 1) {
            Write-Success "Test document created and persisted: $($script:TestDocumentId)"
        }
        else {
            Write-Error "Test document not found in database"
            Set-ExitCode "critical"
        }
    }
    catch {
        Write-Error "Document creation failed (check authentication)"
        Set-ExitCode "critical"
    }

    # Transaction rollback test - attempt invalid document
    $invalidDoc = @{
        filename = "invalid.pdf"
    } | ConvertTo-Json

    try {
        $headers = @{
            "Content-Type" = "application/json"
            "Authorization" = "Bearer $($script:BackendToken)"
        }
        Invoke-RestMethod -Uri "$($script:BackendUrl)/api/v1/documents" -Method Post -Body $invalidDoc -Headers $headers -ErrorAction Stop | Out-Null
        Write-Warning "Invalid document was accepted (validation may be weak)"
        Set-ExitCode "warning"
    }
    catch {
        Write-Success "Transaction rollback test passed (invalid document rejected)"

        # Verify no stray rows inserted
        $strayCount = docker exec krai-postgres-prod psql -U $script:PostgresUser -d $script:PostgresDb -t -c "SELECT COUNT(*) FROM krai_core.documents WHERE filename = 'invalid.pdf'" 2>$null
        $strayCount = $strayCount.Trim()

        if ([int]$strayCount -eq 0) {
            Write-Success "No stray rows inserted after rollback"
        }
        else {
            Write-Error "Found $strayCount stray row(s) after rollback"
            Set-ExitCode "critical"
        }
    }
}

# Backend → MinIO Tests
function Test-BackendMinio {
    Write-Info "Testing Backend → MinIO integration..."

    if (-not $script:BackendToken) {
        Write-Warning "Backend token not set - skipping MinIO tests (set BACKEND_API_TOKEN env var)"
        Set-ExitCode "warning"
        return
    }

    # Upload test - create temporary test file
    $testFile = "$env:TEMP\integration_test_$(Get-Date -Format 'yyyyMMddHHmmss').png"
    "test image content $(Get-Date -Format 'yyyyMMddHHmmss')" | Out-File -FilePath $testFile -Encoding UTF8

    try {
        $headers = @{ "Authorization" = "Bearer $($script:BackendToken)" }
        $form = @{ file = Get-Item -Path $testFile }
        $response = Invoke-RestMethod -Uri "$($script:BackendUrl)/api/v1/images/upload" -Method Post -Headers $headers -Form $form -ErrorAction Stop

        if ($response.image_id) {
            $script:TestImageId = $response.image_id
            $storagePath = $response.storage_path
            $publicUrl = $response.public_url

            Write-Success "File upload successful: image_id=$($script:TestImageId), storage_path=$storagePath"

            # Download test - verify file exists via public URL
            if ($publicUrl) {
                try {
                    Invoke-WebRequest -Uri $publicUrl -Method Head -ErrorAction Stop | Out-Null
                    Write-Success "File download verified via public URL"
                }
                catch {
                    Write-Warning "File uploaded but not accessible via public URL"
                    Set-ExitCode "warning"
                }
            }
            else {
                Write-Warning "Upload response missing public_url"
                Set-ExitCode "warning"
            }
        }
        else {
            Write-Error "File upload response missing image_id"
            Set-ExitCode "critical"
        }
    }
    catch {
        Write-Error "File upload failed (check authentication and endpoint): $_"
        Set-ExitCode "critical"
    }
    finally {
        # Cleanup temporary file
        if (Test-Path $testFile) {
            Remove-Item $testFile -Force
        }
    }

    # Delete test
    if ($script:TestImageId) {
        try {
            $headers = @{ "Authorization" = "Bearer $($script:BackendToken)" }
            Invoke-RestMethod -Uri "$($script:BackendUrl)/api/v1/images/$($script:TestImageId)?delete_from_storage=true" -Method Delete -Headers $headers -ErrorAction Stop | Out-Null
            Write-Success "File deletion successful (image_id=$($script:TestImageId))"
            $script:TestImageId = ""
        }
        catch {
            Write-Warning "File deletion failed"
            Set-ExitCode "warning"
        }
    }
}

# Backend → Ollama Tests
function Test-BackendOllama {
    Write-Info "Testing Backend → Ollama integration..."

    # Check AI service health
    try {
        $health = Invoke-RestMethod -Uri "$($script:BackendUrl)/health" -Method Get -ErrorAction Stop
        if ($health.services.ai.status -eq "healthy") {
            Write-Success "Backend AI service connection verified"
        }
        else {
            Write-Warning "Backend AI service status not healthy"
            Set-ExitCode "warning"
        }
    }
    catch {
        Write-Warning "Backend AI health check failed"
        Set-ExitCode "warning"
    }

    # Embedding generation test
    $embedBody = @{
        model = "nomic-embed-text"
        prompt = "integration test"
    } | ConvertTo-Json

    try {
        $embedResult = Invoke-RestMethod -Uri "$($script:OllamaUrl)/api/embeddings" -Method Post -Body $embedBody -ContentType "application/json" -ErrorAction Stop
        $embedDim = $embedResult.embedding.Count

        if ($embedDim -eq 768) {
            Write-Success "Embedding generation successful: $embedDim dimensions"
        }
        else {
            Write-Error "Embedding dimension mismatch: $embedDim (expected 768)"
            Set-ExitCode "critical"
        }
    }
    catch {
        Write-Error "Embedding generation failed: $_"
        Set-ExitCode "critical"
    }

    # Model availability check
    try {
        $models = Invoke-RestMethod -Uri "$($script:OllamaUrl)/api/tags" -Method Get -ErrorAction Stop
        $modelNames = $models.models | ForEach-Object { $_.name }

        if ($modelNames -contains "nomic-embed-text") {
            Write-Success "Model 'nomic-embed-text' available"
        }
        else {
            Write-Warning "Model 'nomic-embed-text' not found in available models"
            Set-ExitCode "warning"
        }
    }
    catch {
        Write-Error "Failed to query Ollama models: $_"
        Set-ExitCode "critical"
    }
}

# Laravel → Backend Tests
function Test-LaravelBackend {
    Write-Info "Testing Laravel → Backend integration..."

    # JWT authentication test - mint or retrieve token
    Write-Info "Attempting to retrieve JWT token from Laravel..."

    # Try to get JWT token via artisan command (adjust command as needed)
    try {
        $jwtOutput = docker exec krai-laravel-admin php artisan tinker --execute="echo (new \App\Services\JwtService())->generateToken(['user_id' => 1, 'role' => 'admin']);" 2>$null
        $script:LaravelJwtToken = ($jwtOutput -split "`n")[-1].Trim().Trim('"').Trim("'")

        if ($script:LaravelJwtToken -and $script:LaravelJwtToken -ne "null" -and $script:LaravelJwtToken.Length -gt 10) {
            Write-Success "JWT token retrieved from Laravel"

            # Test valid JWT token
            try {
                $headers = @{ "Authorization" = "Bearer $($script:LaravelJwtToken)" }
                $response = Invoke-RestMethod -Uri "$($script:BackendUrl)/api/v1/pipeline/errors?page=1&page_size=10" -Headers $headers -ErrorAction Stop

                if ($response.errors -and $null -ne $response.total) {
                    Write-Success "JWT authentication test passed (valid token accepted)"
                }
                else {
                    Write-Error "Valid JWT token accepted but response invalid"
                    Set-ExitCode "critical"
                }
            }
            catch {
                Write-Error "Valid JWT token rejected"
                Set-ExitCode "critical"
            }

            # Test invalid JWT token
            try {
                $headers = @{ "Authorization" = "Bearer invalid.jwt.token" }
                Invoke-RestMethod -Uri "$($script:BackendUrl)/api/v1/pipeline/errors?page=1&page_size=10" -Headers $headers -ErrorAction Stop | Out-Null
                Write-Error "Invalid JWT token was accepted (should return 401)"
                Set-ExitCode "critical"
            }
            catch {
                Write-Success "JWT authentication test passed (invalid token rejected with 401)"
            }
        }
        else {
            Write-Warning "JWT token generation returned empty/null"
            Set-ExitCode "warning"
        }
    }
    catch {
        Write-Warning "JWT service not available - testing without authentication"
        Set-ExitCode "warning"
    }

    # REST API call test with valid token (if available)
    if ($script:LaravelJwtToken) {
        try {
            $headers = @{ "Authorization" = "Bearer $($script:LaravelJwtToken)" }
            $apiResponse = docker exec krai-laravel-admin curl -sf "$($script:BackendUrl)/api/v1/pipeline/errors?page=1&page_size=10" -H "Authorization: Bearer $($script:LaravelJwtToken)" 2>$null
            $parsed = $apiResponse | ConvertFrom-Json

            if ($parsed.errors -and $null -ne $parsed.total) {
                Write-Success "Laravel → Backend REST API call successful (with JWT)"
            }
            else {
                Write-Error "Laravel → Backend API response invalid"
                Set-ExitCode "critical"
            }
        }
        catch {
            Write-Warning "Laravel → Backend API call failed"
            Set-ExitCode "warning"
        }
    }
    else {
        # Fallback: test without authentication
        try {
            $apiResponse = docker exec krai-laravel-admin curl -sf "$($script:BackendUrl)/api/v1/pipeline/errors?page=1&page_size=10" 2>$null
            $parsed = $apiResponse | ConvertFrom-Json

            if ($parsed.errors -and $null -ne $parsed.total) {
                Write-Success "Laravel → Backend API call successful (no auth)"
            }
            else {
                Write-Error "Laravel → Backend API response invalid"
                Set-ExitCode "critical"
            }
        }
        catch {
            Write-Warning "Laravel → Backend API call failed"
            Set-ExitCode "warning"
        }
    }
}

# Laravel → PostgreSQL Tests
function Test-LaravelPostgres {
    Write-Info "Testing Laravel → PostgreSQL integration..."

    # Direct query test - Manufacturer count
    try {
        $output = docker exec krai-laravel-admin php artisan tinker --execute="echo App\Models\Manufacturer::count();" 2>$null
        $mfrCount = ($output -split "`n")[-1].Trim()

        if ([int]$mfrCount -ge 14) {
            Write-Success "Laravel Eloquent query successful: $mfrCount manufacturers"
        }
        else {
            Write-Warning "Manufacturer count lower than expected: $mfrCount"
            Set-ExitCode "warning"
        }
    }
    catch {
        Write-Error "Laravel Eloquent query failed: $_"
        Set-ExitCode "critical"
    }

    # Product model test
    try {
        docker exec krai-laravel-admin php artisan tinker --execute="echo App\Models\Product::count();" 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Product model test passed"
        }
        else {
            Write-Warning "Product model test failed"
            Set-ExitCode "warning"
        }
    }
    catch {
        Write-Warning "Product model test failed: $_"
        Set-ExitCode "warning"
    }

    # User model test
    try {
        $output = docker exec krai-laravel-admin php artisan tinker --execute="echo App\Models\User::count();" 2>$null
        $userCount = ($output -split "`n")[-1].Trim()

        if ([int]$userCount -ge 1) {
            Write-Success "User model test passed: $userCount users"
        }
        else {
            Write-Warning "No users found in database"
            Set-ExitCode "warning"
        }
    }
    catch {
        Write-Warning "User model test failed: $_"
        Set-ExitCode "warning"
    }

    # PipelineError model test
    try {
        docker exec krai-laravel-admin php artisan tinker --execute="echo App\Models\PipelineError::count();" 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "PipelineError model test passed"
        }
        else {
            Write-Warning "PipelineError model test failed"
            Set-ExitCode "warning"
        }
    }
    catch {
        Write-Warning "PipelineError model test failed: $_"
        Set-ExitCode "warning"
    }
}

# Generate report
function Show-IntegrationReport {
    Write-Host ""
    Write-Host "╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║  Integration Test Results                                 ║" -ForegroundColor Cyan
    Write-Host "╠═══════════════════════════════════════════════════════════╣" -ForegroundColor Cyan

    $totalTests = $script:TestsPassed + $script:TestsFailed

    if ($script:TestsFailed -eq 0) {
        Write-Host "║  " -NoNewline -ForegroundColor Cyan
        Write-Host "Total:                       ✅ $($script:TestsPassed)/$totalTests passed" -NoNewline -ForegroundColor Green
        Write-Host "             ║" -ForegroundColor Cyan
    }
    else {
        Write-Host "║  " -NoNewline -ForegroundColor Cyan
        Write-Host "Total:                       ❌ $($script:TestsPassed)/$totalTests passed" -NoNewline -ForegroundColor Red
        Write-Host "             ║" -ForegroundColor Cyan
        Write-Host "║  " -NoNewline -ForegroundColor Cyan
        Write-Host "Failed:                      $($script:TestsFailed) tests" -NoNewline -ForegroundColor Red
        Write-Host "                        ║" -ForegroundColor Cyan
    }

    Write-Host "╚═══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""

    if ($script:ExitCode -eq 0) {
        Write-Success "All integration tests passed successfully!"
    }
    elseif ($script:ExitCode -eq 1) {
        Write-Warning "Some tests passed with warnings"
    }
    else {
        Write-Error "Critical integration test failures detected"
    }

    Write-Host ""
    Write-Host "Exit code: $($script:ExitCode)"
}

# Main execution
try {
    Write-Host "╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "║  KRAI Docker Integration Tests                            ║" -ForegroundColor Green
    Write-Host "╚═══════════════════════════════════════════════════════════╝" -ForegroundColor Green
    Write-Host ""

    Test-BackendPostgres
    Write-Host ""
    Test-BackendMinio
    Write-Host ""
    Test-BackendOllama
    Write-Host ""
    Test-LaravelBackend
    Write-Host ""
    Test-LaravelPostgres

    Show-IntegrationReport
}
finally {
    Remove-TestData
}

exit $script:ExitCode
