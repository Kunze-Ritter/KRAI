# Refactoring Test Script - V2.1 Cleanup
# Tests all critical endpoints after refactoring

Write-Host ""
Write-Host "REFACTORING TESTS - V2.1 Cleanup" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

$baseUrl = "http://localhost:8000"
$passed = 0
$failed = 0

function Test-Endpoint {
    param(
        [string]$Name,
        [string]$Url,
        [string]$Method = "GET"
    )

    Write-Host ""
    Write-Host "Testing: $Name" -ForegroundColor Yellow
    Write-Host "URL: $Url"

    try {
        $response = Invoke-RestMethod -Uri $Url -Method $Method -ErrorAction Stop
        Write-Host "[PASSED]" -ForegroundColor Green
        $script:passed++
        return $response
    } catch {
        Write-Host "[FAILED] $($_.Exception.Message)" -ForegroundColor Red
        $script:failed++
        return $null
    }
}

# Test 1: Core Endpoints
Write-Host ""
Write-Host "TEST SUITE 1: Core Endpoints" -ForegroundColor Cyan
Write-Host "--------------------------------------------------"
$health = Test-Endpoint "Health Check" "$baseUrl/health"
$info = Test-Endpoint "API Info" "$baseUrl/info"

# Test 2: Features
Write-Host ""
Write-Host "TEST SUITE 2: Features" -ForegroundColor Cyan
Write-Host "--------------------------------------------------"
$features = Test-Endpoint "Features List" "$baseUrl/features"

# Test 3: Search
Write-Host ""
Write-Host "TEST SUITE 3: Search Endpoints" -ForegroundColor Cyan
Write-Host "--------------------------------------------------"
$search = Test-Endpoint "Search Endpoint" "$baseUrl/search?query=test&limit=5"

# Test 4: Defect Detection
Write-Host ""
Write-Host "TEST SUITE 4: Defect Detection" -ForegroundColor Cyan
Write-Host "--------------------------------------------------"
$defects = Test-Endpoint "Defect Detection" "$baseUrl/defects"

# Summary
Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "TEST RESULTS SUMMARY" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "Passed: $passed" -ForegroundColor Green
Write-Host "Failed: $failed" -ForegroundColor Red
Write-Host "Total:  $($passed + $failed)"

if ($failed -eq 0) {
    Write-Host ""
    Write-Host "ALL TESTS PASSED! REFACTORING SUCCESSFUL!" -ForegroundColor Green
    exit 0
} else {
    Write-Host ""
    Write-Host "SOME TESTS FAILED! CHECK LOGS!" -ForegroundColor Yellow
    exit 1
}
