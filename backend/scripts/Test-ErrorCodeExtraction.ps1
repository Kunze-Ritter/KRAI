# Error Code Extraction Test Script
# PowerShell version with better output formatting

param(
    [Parameter(Mandatory=$false)]
    [string]$Pdf,

    [Parameter(Mandatory=$false)]
    [string]$Directory,

    [Parameter(Mandatory=$false)]
    [string]$Manufacturer,

    [Parameter(Mandatory=$false)]
    [string]$Output = "error_code_test_$(Get-Date -Format 'yyyyMMdd_HHmmss').txt",

    [Parameter(Mandatory=$false)]
    [string]$Pattern = "*.pdf"
)

function Show-Help {
    Write-Host ""
    Write-Host "Error Code Extraction Testing Tool" -ForegroundColor Cyan
    Write-Host "=====================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage:"
    Write-Host "  .\Test-ErrorCodeExtraction.ps1 -Pdf <path>"
    Write-Host "  .\Test-ErrorCodeExtraction.ps1 -Directory <path> [-Pattern <pattern>]"
    Write-Host ""
    Write-Host "Parameters:"
    Write-Host "  -Pdf           Single PDF file to test"
    Write-Host "  -Directory     Directory containing PDFs to test"
    Write-Host "  -Manufacturer  Manufacturer name (hp, konica_minolta, canon, etc.)"
    Write-Host "  -Output        Output report file (default: timestamped)"
    Write-Host "  -Pattern       File pattern for batch test (default: *.pdf)"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\Test-ErrorCodeExtraction.ps1 -Pdf 'C:\Manuals\bizhub_4750i_SM.pdf'"
    Write-Host "  .\Test-ErrorCodeExtraction.ps1 -Directory 'C:\Manuals\KonicaMinolta' -Manufacturer konica_minolta"
    Write-Host "  .\Test-ErrorCodeExtraction.ps1 -Directory 'C:\Manuals' -Pattern '*bizhub*.pdf'"
    Write-Host ""
}

# Check if no parameters provided
if (-not $Pdf -and -not $Directory) {
    Show-Help
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Error Code Extraction Test" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Build command
$pythonScript = Join-Path $PSScriptRoot "test_error_code_extraction.py"

if (-not (Test-Path $pythonScript)) {
    Write-Host "ERROR: Script not found: $pythonScript" -ForegroundColor Red
    exit 1
}

$command = "python `"$pythonScript`""

if ($Pdf) {
    Write-Host "Mode: Single PDF Test" -ForegroundColor Yellow
    Write-Host "File: $Pdf"
    $command += " --pdf `"$Pdf`""
}
elseif ($Directory) {
    Write-Host "Mode: Batch Test" -ForegroundColor Yellow
    Write-Host "Directory: $Directory"
    Write-Host "Pattern: $Pattern"
    $command += " --directory `"$Directory`" --pattern `"$Pattern`""
}

if ($Manufacturer) {
    Write-Host "Manufacturer: $Manufacturer"
    $command += " --manufacturer $Manufacturer"
}

Write-Host "Output: $Output"
$command += " --output `"$Output`""

Write-Host ""
Write-Host "Running test..." -ForegroundColor Green
Write-Host ""

# Change to backend directory
$backendDir = Split-Path $PSScriptRoot -Parent
Push-Location $backendDir

try {
    # Execute test
    Invoke-Expression $command

    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Green
        Write-Host " Test Complete!" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "Report saved to: $Output" -ForegroundColor Green

        # Show report summary
        if (Test-Path $Output) {
            Write-Host ""
            Write-Host "Report Summary:" -ForegroundColor Cyan
            Write-Host "---------------" -ForegroundColor Cyan
            Get-Content $Output | Select-String -Pattern "^(Total|Average|Codes)" | ForEach-Object {
                Write-Host $_.Line
            }

            Write-Host ""
            $response = Read-Host "Open full report? (Y/N)"
            if ($response -eq "Y" -or $response -eq "y") {
                Start-Process notepad $Output
            }

            # Also open JSON if exists
            $jsonFile = $Output.Replace('.txt', '.json')
            if (Test-Path $jsonFile) {
                Write-Host ""
                Write-Host "JSON data available: $jsonFile" -ForegroundColor Cyan
            }
        }
    }
    else {
        Write-Host ""
        Write-Host "Test failed with exit code: $LASTEXITCODE" -ForegroundColor Red
    }
}
catch {
    Write-Host ""
    Write-Host "ERROR: $_" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
}
finally {
    Pop-Location
}

Write-Host ""
