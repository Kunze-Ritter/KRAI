# Refactoring Test Script
# Tests all critical endpoints after V2.1 refactoring

Write-Host "`nREFACTORING TESTS - V2.1 Cleanup" -ForegroundColor Cyan
Write-Host "=" * 50

$baseUrl = "http://localhost:8000"
$passed = 0
$failed = 0
function Test-Endpoint {
    param(
        [string]$Name,
        [string]$Url,
        [string]$Method = "GET"
    )

    Write-Host "`n🔍 Testing: $Name" -ForegroundColor Yellow
    Write-Host "   URL: $Url"

    try {
        $response = Invoke-RestMethod -Uri $Url -Method $Method -ErrorAction Stop
        Write-Host "   ✅ PASSED" -ForegroundColor Green
        $script:passed++
        return $response
    } catch {
        Write-Host "   ❌ FAILED: $($_.Exception.Message)" -ForegroundColor Red
        $script:failed++
        return $null
    }
}

# Test 1: Health Check
Write-Host "`n📊 TEST SUITE 1: Core Endpoints" -ForegroundColor Cyan
$health = Test-Endpoint "Health Check" "$baseUrl/health"
$info = Test-Endpoint "API Info" "$baseUrl/info"

# Test 2: Features
Write-Host "`n📊 TEST SUITE 2: Features" -ForegroundColor Cyan
$features = Test-Endpoint "Features List" "$baseUrl/features"

# Test 3: Search
Write-Host "`n📊 TEST SUITE 3: Search Endpoints" -ForegroundColor Cyan
$search = Test-Endpoint "Search Endpoint" "$baseUrl/search?query=test&limit=5"

# Test 4: Defect Detection
Write-Host "`n📊 TEST SUITE 4: Defect Detection" -ForegroundColor Cyan
$defects = Test-Endpoint "Defect Detection" "$baseUrl/defects"

# Test 5: Documents
Write-Host "`n📊 TEST SUITE 5: Document Endpoints" -ForegroundColor Cyan
# Skip upload test (requires file)
Write-Host "`n🔍 Testing: Document Upload" -ForegroundColor Yellow
Write-Host "   ⏭️  SKIPPED (requires file upload)" -ForegroundColor Yellow

# Summary
Write-Host "`n" + ("=" * 50)
Write-Host "📊 TEST RESULTS SUMMARY" -ForegroundColor Cyan
Write-Host ("=" * 50)
Write-Host "✅ Passed: $passed" -ForegroundColor Green
Write-Host "❌ Failed: $failed" -ForegroundColor Red
Write-Host "📈 Total:  $($passed + $failed)"

if ($failed -eq 0) {
    Write-Host "`n🎉 ALL TESTS PASSED! REFACTORING SUCCESSFUL!" -ForegroundColor Green
    exit 0
} else {
    Write-Host "`n⚠️  SOME TESTS FAILED! CHECK LOGS!" -ForegroundColor Yellow
    exit 1
}
