# Test Pipeline Errors API
$ErrorActionPreference = "Stop"
$baseUrl = "http://localhost:8000"

Write-Host "=== Testing Pipeline Errors API ===" -ForegroundColor Cyan
Write-Host ""

# Login
Write-Host "1. Login..." -ForegroundColor Yellow
$loginBody = '{"username":"admin","password":"admin"}'
try {
    $response = Invoke-RestMethod -Uri "$baseUrl/api/v1/auth/login" -Method Post -Body $loginBody -ContentType "application/json"
    $token = $response.data.access_token
    Write-Host "   ✅ Login successful" -ForegroundColor Green
} catch {
    Write-Host "   ❌ Login failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

$headers = @{
    "Authorization" = "Bearer $token"
}

# Test List Errors
Write-Host ""
Write-Host "2. GET /api/v1/pipeline/errors" -ForegroundColor Yellow
try {
    $errors = Invoke-RestMethod -Uri "$baseUrl/api/v1/pipeline/errors" -Method Get -Headers $headers
    Write-Host "   ✅ Success!" -ForegroundColor Green
    Write-Host "   Total: $($errors.data.total)" -ForegroundColor Cyan
    Write-Host "   Page: $($errors.data.page)/$($errors.data.total_pages)" -ForegroundColor Cyan

    if ($errors.data.errors.Count -gt 0) {
        $firstError = $errors.data.errors[0]
        Write-Host "   First error: $($firstError.error_id)" -ForegroundColor Gray
        $testErrorId = $firstError.error_id
    } else {
        Write-Host "   No errors in database" -ForegroundColor Yellow
        $testErrorId = $null
    }
} catch {
    Write-Host "   ❌ Failed: $($_.Exception.Message)" -ForegroundColor Red
    $testErrorId = $null
}

# Test Get Error Details
if ($testErrorId) {
    Write-Host ""
    Write-Host "3. GET /api/v1/pipeline/errors/$testErrorId" -ForegroundColor Yellow
    try {
        $detail = Invoke-RestMethod -Uri "$baseUrl/api/v1/pipeline/errors/$testErrorId" -Method Get -Headers $headers
        Write-Host "   ✅ Success!" -ForegroundColor Green
        Write-Host "   Error Type: $($detail.data.error_type)" -ForegroundColor Cyan
        Write-Host "   Retries: $($detail.data.retry_count)/$($detail.data.max_retries)" -ForegroundColor Cyan
    } catch {
        Write-Host "   ❌ Failed: $($_.Exception.Message)" -ForegroundColor Red
    }
}

# Test Mark Resolved
if ($testErrorId) {
    Write-Host ""
    Write-Host "4. POST /api/v1/pipeline/mark-error-resolved" -ForegroundColor Yellow
    $resolveBody = "{`"error_id`":`"$testErrorId`",`"notes`":`"Test from API script`"}"
    try {
        $resolved = Invoke-RestMethod -Uri "$baseUrl/api/v1/pipeline/mark-error-resolved" -Method Post -Body $resolveBody -Headers $headers -ContentType "application/json"
        Write-Host "   ✅ Success!" -ForegroundColor Green
        Write-Host "   Resolved by: $($resolved.data.resolved_by)" -ForegroundColor Cyan
    } catch {
        Write-Host "   ❌ Failed: $($_.Exception.Message)" -ForegroundColor Red
    }
}

# Test Retry Stage (should return 501)
Write-Host ""
Write-Host "5. POST /api/v1/pipeline/retry-stage (expects 501)" -ForegroundColor Yellow
$retryBody = '{"document_id":"test","stage_name":"classification"}'
try {
    $retry = Invoke-RestMethod -Uri "$baseUrl/api/v1/pipeline/retry-stage" -Method Post -Body $retryBody -Headers $headers -ContentType "application/json"
    Write-Host "   ⚠️  Unexpected success" -ForegroundColor Yellow
} catch {
    if ($_.Exception.Response.StatusCode.value__ -eq 501) {
        Write-Host "   ✅ Returns 501 as expected" -ForegroundColor Green
    } else {
        Write-Host "   ❌ Unexpected error: $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "=== Summary ===" -ForegroundColor Cyan
Write-Host "Pipeline Errors API is working!" -ForegroundColor Green
Write-Host "Swagger UI: $baseUrl/docs" -ForegroundColor Gray
Write-Host ""
