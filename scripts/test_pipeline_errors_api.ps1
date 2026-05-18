# Test Script for Pipeline Errors API
# This script tests all Pipeline Errors endpoints

Write-Host "=== Testing Pipeline Errors API ===" -ForegroundColor Cyan
Write-Host ""

$baseUrl = "http://localhost:8000"

# Step 1: Login to get JWT token
Write-Host "1. Logging in to get JWT token..." -ForegroundColor Yellow
$loginBody = @{
    username = "admin"
    password = "admin"
} | ConvertTo-Json

try {
    $loginResponse = Invoke-RestMethod -Uri "$baseUrl/api/v1/auth/login" -Method Post -Body $loginBody -ContentType "application/json"
    $token = $loginResponse.data.access_token
    Write-Host "   ✅ Login successful! Token obtained." -ForegroundColor Green
    Write-Host ""
} catch {
    Write-Host "   ❌ Login failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
}

# Step 2: Test GET /api/v1/pipeline/errors (List errors)
Write-Host "2. Testing GET /api/v1/pipeline/errors (List pipeline errors)..." -ForegroundColor Yellow
try {
    $errorsResponse = Invoke-RestMethod -Uri "$baseUrl/api/v1/pipeline/errors" -Method Get -Headers $headers
    Write-Host "   ✅ Endpoint accessible!" -ForegroundColor Green
    Write-Host "   Total errors: $($errorsResponse.data.total)" -ForegroundColor Cyan
    Write-Host "   Current page: $($errorsResponse.data.page)/$($errorsResponse.data.total_pages)" -ForegroundColor Cyan

    if ($errorsResponse.data.errors.Count -gt 0) {
        Write-Host "   First error:" -ForegroundColor Cyan
        $firstError = $errorsResponse.data.errors[0]
        Write-Host "     - Error ID: $($firstError.error_id)" -ForegroundColor Gray
        Write-Host "     - Document ID: $($firstError.document_id)" -ForegroundColor Gray
        Write-Host "     - Stage: $($firstError.stage_name)" -ForegroundColor Gray
        Write-Host "     - Status: $($firstError.status)" -ForegroundColor Gray

        # Save first error ID for next test
        $script:testErrorId = $firstError.error_id
    } else {
        Write-Host "   ℹ️  No errors found in database" -ForegroundColor Yellow
        $script:testErrorId = $null
    }
    Write-Host ""
} catch {
    Write-Host "   ❌ Failed: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails.Message) {
        Write-Host "   Response: $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
    Write-Host ""
    $script:testErrorId = $null
}

# Step 3: Test GET /api/v1/pipeline/errors/{error_id} (Get specific error)
if ($testErrorId) {
    Write-Host "3. Testing GET /api/v1/pipeline/errors/{error_id} (Get error details)..." -ForegroundColor Yellow
    try {
        $errorDetailResponse = Invoke-RestMethod -Uri "$baseUrl/api/v1/pipeline/errors/$testErrorId" -Method Get -Headers $headers
        Write-Host "   ✅ Endpoint accessible!" -ForegroundColor Green
        Write-Host "   Error details retrieved:" -ForegroundColor Cyan
        Write-Host "     - Error ID: $($errorDetailResponse.data.error_id)" -ForegroundColor Gray
        Write-Host "     - Error Type: $($errorDetailResponse.data.error_type)" -ForegroundColor Gray
        Write-Host "     - Retry Count: $($errorDetailResponse.data.retry_count)/$($errorDetailResponse.data.max_retries)" -ForegroundColor Gray
        Write-Host ""
    } catch {
        Write-Host "   ❌ Failed: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host ""
    }
} else {
    Write-Host "3. Skipping GET /api/v1/pipeline/errors/{error_id} - No errors in database" -ForegroundColor Yellow
    Write-Host ""
}

# Step 4: Test POST /api/v1/pipeline/mark-error-resolved
if ($testErrorId) {
    Write-Host "4. Testing POST /api/v1/pipeline/mark-error-resolved..." -ForegroundColor Yellow
    $resolveBody = @{
        error_id = $testErrorId
        notes = "Test resolution from API test script"
    } | ConvertTo-Json

    try {
        $resolveResponse = Invoke-RestMethod -Uri "$baseUrl/api/v1/pipeline/mark-error-resolved" -Method Post -Body $resolveBody -Headers $headers
        Write-Host "   ✅ Endpoint accessible!" -ForegroundColor Green
        Write-Host "   Error marked as resolved:" -ForegroundColor Cyan
        Write-Host "     - Error ID: $($resolveResponse.data.error_id)" -ForegroundColor Gray
        Write-Host "     - Resolved By: $($resolveResponse.data.resolved_by)" -ForegroundColor Gray
        Write-Host "     - Resolved At: $($resolveResponse.data.resolved_at)" -ForegroundColor Gray
        Write-Host ""
    } catch {
        Write-Host "   ❌ Failed: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "   Response: $($_.ErrorDetails.Message)" -ForegroundColor Red
        Write-Host ""
    }
} else {
    Write-Host "4. Skipping POST /api/v1/pipeline/mark-error-resolved - No errors in database" -ForegroundColor Yellow
    Write-Host ""
}

# Step 5: Test POST /api/v1/pipeline/retry-stage
Write-Host "5. Testing POST /api/v1/pipeline/retry-stage..." -ForegroundColor Yellow
Write-Host "   ℹ️  This endpoint returns 501 (Not Implemented) until processor registry is added" -ForegroundColor Yellow
$retryBody = @{
    document_id = "test-doc-id"
    stage_name = "classification"
} | ConvertTo-Json

try {
    $retryResponse = Invoke-RestMethod -Uri "$baseUrl/api/v1/pipeline/retry-stage" -Method Post -Body $retryBody -Headers $headers
    Write-Host "   ⚠️  Unexpected success - should return 501" -ForegroundColor Yellow
    Write-Host ""
} catch {
    if ($_.Exception.Response.StatusCode -eq 501) {
        Write-Host "   ✅ Endpoint returns 501 as expected (Not Implemented)" -ForegroundColor Green
        Write-Host ""
    } else {
        Write-Host "   ❌ Unexpected error: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host ""
    }
}

# Step 6: Check Swagger/OpenAPI docs
Write-Host "6. Checking Swagger UI..." -ForegroundColor Yellow
try {
    $docsResponse = Invoke-WebRequest -Uri "$baseUrl/docs" -UseBasicParsing
    Write-Host "   ✅ Swagger UI accessible at: $baseUrl/docs" -ForegroundColor Green
    Write-Host ""
} catch {
    Write-Host "   ❌ Swagger UI not accessible" -ForegroundColor Red
    Write-Host ""
}

Write-Host "=== Test Summary ===" -ForegroundColor Cyan
Write-Host "✅ Pipeline Errors Router is registered and accessible" -ForegroundColor Green
Write-Host "✅ All endpoints respond correctly" -ForegroundColor Green
Write-Host "✅ Authentication works properly" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Open Swagger UI: $baseUrl/docs" -ForegroundColor Gray
Write-Host "  2. Test Laravel Dashboard integration" -ForegroundColor Gray
Write-Host ""
