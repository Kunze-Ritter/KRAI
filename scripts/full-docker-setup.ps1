<#
.SYNOPSIS
    KRAI Full Docker Setup Orchestrator

.DESCRIPTION
    Runs complete Docker setup workflow: clean setup, health checks,
    integration tests, and persistency tests with detailed reporting.

.PARAMETER SkipClean
    Skip the clean setup step

.PARAMETER SkipIntegration
    Skip integration tests

.PARAMETER LogFile
    Path to log file for persistent logging

.EXAMPLE
    .\scripts\full-docker-setup.ps1

.EXAMPLE
    .\scripts\full-docker-setup.ps1 -SkipClean -LogFile "setup.log"

.NOTES
    Exit Codes:
    0 - All steps completed successfully
    1 - Completed with warnings (system functional but degraded)
    2 - Critical errors detected (manual intervention required)
#>

[CmdletBinding()]
param(
    [switch]$SkipClean,
    [switch]$SkipIntegration,
    [string]$LogFile
)

$ErrorActionPreference = "Continue"

# Global variables for tracking
$script:OverallExitCode = 0
$script:CleanExitCode = 0
$script:HealthExitCode = 0
$script:IntegrationExitCode = 0
$script:PersistencyExitCode = 0

$script:CleanStartTime = $null
$script:HealthStartTime = $null
$script:IntegrationStartTime = $null
$script:PersistencyStartTime = $null

$script:CleanDuration = ""
$script:HealthDuration = ""
$script:IntegrationDuration = ""
$script:PersistencyDuration = ""

$script:CleanTimestamp = ""
$script:HealthTimestamp = ""
$script:IntegrationTimestamp = ""
$script:PersistencyTimestamp = ""

# Helper functions
function Write-Header {
    param([string]$Title)

    Write-Host ""
    Write-Host "╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║  $Title" -ForegroundColor Cyan
    Write-Host "╚═══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
}

function Write-StepStatus {
    param(
        [string]$Status,
        [string]$Message
    )

    $timestamp = Get-Timestamp

    switch ($Status) {
        "success" {
            Write-Host "[$timestamp] " -NoNewline
            Write-Host "[SUCCESS]" -ForegroundColor Green -NoNewline
            Write-Host " ✅ $Message"
        }
        "warning" {
            Write-Host "[$timestamp] " -NoNewline
            Write-Host "[WARNING]" -ForegroundColor Yellow -NoNewline
            Write-Host " ⚠️  $Message"
        }
        "error" {
            Write-Host "[$timestamp] " -NoNewline
            Write-Host "[ERROR]" -ForegroundColor Red -NoNewline
            Write-Host " ❌ $Message"
        }
        "info" {
            Write-Host "[$timestamp] " -NoNewline
            Write-Host "[INFO]" -ForegroundColor Blue -NoNewline
            Write-Host " $Message"
        }
    }
}

function Get-Timestamp {
    return Get-Date -Format "yyyy-MM-dd HH:mm:ss"
}

function Update-ExitCode {
    param([int]$NewCode)

    if ($NewCode -gt $script:OverallExitCode) {
        $script:OverallExitCode = $NewCode
    }
}

function Write-LogStep {
    param(
        [string]$StepNum,
        [string]$StepName
    )

    $timestamp = Get-Timestamp

    Write-Host ""
    Write-Host "[$timestamp] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
    Write-StepStatus "info" "Step $StepNum/4: $StepName..."
    Write-Host "[$timestamp] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
    Write-Host ""
}

function Format-Duration {
    param([TimeSpan]$Duration)

    $minutes = [Math]::Floor($Duration.TotalMinutes)
    $seconds = $Duration.Seconds

    if ($minutes -gt 0) {
        return "${minutes}m ${seconds}s"
    } else {
        return "${seconds}s"
    }
}

# Setup logging if requested
if ($LogFile) {
    Start-Transcript -Path $LogFile -Append
}

# Main execution
$workflowStartTime = Get-Date

Write-Header "KRAI Full Docker Setup - Starting Workflow"

# Step 1: Clean Setup
if (-not $SkipClean) {
    Write-LogStep "1" "Running Clean Setup"
    $script:CleanStartTime = Get-Date
    $script:CleanTimestamp = Get-Timestamp

    & .\scripts\docker-clean-setup.ps1
    $script:CleanExitCode = $LASTEXITCODE

    $cleanEndTime = Get-Date
    $script:CleanDuration = Format-Duration ($cleanEndTime - $script:CleanStartTime)

    Write-Host ""
    Write-Host "[$(Get-Timestamp)] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan

    if ($script:CleanExitCode -eq 0) {
        Write-StepStatus "success" "Step 1 completed (Duration: $($script:CleanDuration), Exit Code: 0)"
    } elseif ($script:CleanExitCode -eq 1) {
        Write-StepStatus "warning" "Step 1 completed with warnings (Duration: $($script:CleanDuration), Exit Code: 1)"
        Update-ExitCode $script:CleanExitCode
    } else {
        Write-StepStatus "error" "Step 1 failed (Duration: $($script:CleanDuration), Exit Code: $($script:CleanExitCode))"
        Update-ExitCode $script:CleanExitCode

        if ($script:CleanExitCode -eq 2) {
            Write-StepStatus "error" "Critical error in clean setup. Continuing to final report."
            $script:OverallExitCode = 2
        }
    }

    Write-Host "[$(Get-Timestamp)] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
} else {
    Write-StepStatus "info" "Skipping Step 1: Clean Setup (-SkipClean flag)"
    $script:CleanTimestamp = Get-Timestamp
    $script:CleanDuration = "skipped"
    $script:CleanExitCode = -1
}

# Step 2: Health Check
Write-LogStep "2" "Running Health Check"
$script:HealthStartTime = Get-Date
$script:HealthTimestamp = Get-Timestamp

& .\scripts\docker-health-check.ps1
$script:HealthExitCode = $LASTEXITCODE

$healthEndTime = Get-Date
$script:HealthDuration = Format-Duration ($healthEndTime - $script:HealthStartTime)

Write-Host ""
Write-Host "[$(Get-Timestamp)] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan

if ($script:HealthExitCode -eq 0) {
    Write-StepStatus "success" "Step 2 completed (Duration: $($script:HealthDuration), Exit Code: 0)"
} elseif ($script:HealthExitCode -eq 1) {
    Write-StepStatus "warning" "Step 2 completed with warnings (Duration: $($script:HealthDuration), Exit Code: 1)"
    Update-ExitCode $script:HealthExitCode
} else {
    Write-StepStatus "error" "Step 2 failed (Duration: $($script:HealthDuration), Exit Code: $($script:HealthExitCode))"
    Update-ExitCode $script:HealthExitCode

    if ($script:HealthExitCode -eq 2) {
        Write-StepStatus "error" "Critical health check failure. System may not be functional."
        Write-StepStatus "error" "Recommendation: Review health check logs and fix critical issues before proceeding."
        $script:OverallExitCode = 2
    }
}

Write-Host "[$(Get-Timestamp)] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan

# Step 3: Integration Tests
if (-not $SkipIntegration) {
    Write-LogStep "3" "Running Integration Tests"
    $script:IntegrationStartTime = Get-Date
    $script:IntegrationTimestamp = Get-Timestamp

    # Check for BACKEND_API_TOKEN
    if (-not $env:BACKEND_API_TOKEN) {
        Write-StepStatus "warning" "BACKEND_API_TOKEN not set. Some write tests may be skipped."
    }

    & .\scripts\docker-integration-tests.ps1
    $script:IntegrationExitCode = $LASTEXITCODE

    $integrationEndTime = Get-Date
    $script:IntegrationDuration = Format-Duration ($integrationEndTime - $script:IntegrationStartTime)

    Write-Host ""
    Write-Host "[$(Get-Timestamp)] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan

    if ($script:IntegrationExitCode -eq 0) {
        Write-StepStatus "success" "Step 3 completed (Duration: $($script:IntegrationDuration), Exit Code: 0)"
    } elseif ($script:IntegrationExitCode -eq 1) {
        Write-StepStatus "warning" "Step 3 completed with warnings (Duration: $($script:IntegrationDuration), Exit Code: 1)"
        Update-ExitCode $script:IntegrationExitCode
    } else {
        Write-StepStatus "error" "Step 3 failed (Duration: $($script:IntegrationDuration), Exit Code: $($script:IntegrationExitCode))"
        Update-ExitCode $script:IntegrationExitCode
    }

    Write-Host "[$(Get-Timestamp)] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
} else {
    Write-StepStatus "info" "Skipping Step 3: Integration Tests (-SkipIntegration flag)"
    $script:IntegrationTimestamp = Get-Timestamp
    $script:IntegrationDuration = "skipped"
    $script:IntegrationExitCode = -1
}

# Step 4: Persistency Tests
Write-LogStep "4" "Running Persistency Tests"
$script:PersistencyStartTime = Get-Date
$script:PersistencyTimestamp = Get-Timestamp

& .\scripts\docker-health-check.ps1 -TestPersistency
$script:PersistencyExitCode = $LASTEXITCODE

$persistencyEndTime = Get-Date
$script:PersistencyDuration = Format-Duration ($persistencyEndTime - $script:PersistencyStartTime)

Write-Host ""
Write-Host "[$(Get-Timestamp)] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan

if ($script:PersistencyExitCode -eq 0) {
    Write-StepStatus "success" "Step 4 completed (Duration: $($script:PersistencyDuration), Exit Code: 0)"
} elseif ($script:PersistencyExitCode -eq 1) {
    Write-StepStatus "warning" "Step 4 completed with warnings (Duration: $($script:PersistencyDuration), Exit Code: 1)"
    Update-ExitCode $script:PersistencyExitCode
} else {
    Write-StepStatus "error" "Step 4 failed (Duration: $($script:PersistencyDuration), Exit Code: $($script:PersistencyExitCode))"
    Update-ExitCode $script:PersistencyExitCode
}

Write-Host "[$(Get-Timestamp)] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan

# Generate final report
$workflowEndTime = Get-Date
$totalDuration = Format-Duration ($workflowEndTime - $workflowStartTime)

Write-Host ""
Write-Host ""
Write-Host "╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  KRAI Full Docker Setup - Final Report                   ║" -ForegroundColor Cyan
Write-Host "╠═══════════════════════════════════════════════════════════╣" -ForegroundColor Cyan

# Step 1 Report
Write-Host "║  Step 1: Clean Setup                                      ║" -ForegroundColor Cyan
if ($script:CleanExitCode -eq -1) {
    Write-Host "║    Status: ⏭️  SKIPPED                                     ║" -ForegroundColor Cyan
} elseif ($script:CleanExitCode -eq 0) {
    Write-Host "║    Status: " -ForegroundColor Cyan -NoNewline
    Write-Host "✅ SUCCESS" -ForegroundColor Green -NoNewline
    Write-Host " (Exit Code: 0)                      ║" -ForegroundColor Cyan
} elseif ($script:CleanExitCode -eq 1) {
    Write-Host "║    Status: " -ForegroundColor Cyan -NoNewline
    Write-Host "⚠️  WARNING" -ForegroundColor Yellow -NoNewline
    Write-Host " (Exit Code: 1)                     ║" -ForegroundColor Cyan
} else {
    Write-Host "║    Status: " -ForegroundColor Cyan -NoNewline
    Write-Host "❌ ERROR" -ForegroundColor Red -NoNewline
    Write-Host " (Exit Code: $($script:CleanExitCode))                       ║" -ForegroundColor Cyan
}
Write-Host "║    Duration: $($script:CleanDuration.PadRight(45))║" -ForegroundColor Cyan
Write-Host "║    Timestamp: $($script:CleanTimestamp.PadRight(44))║" -ForegroundColor Cyan
Write-Host "║                                                           ║" -ForegroundColor Cyan

# Step 2 Report
Write-Host "║  Step 2: Health Check                                     ║" -ForegroundColor Cyan
if ($script:HealthExitCode -eq 0) {
    Write-Host "║    Status: " -ForegroundColor Cyan -NoNewline
    Write-Host "✅ SUCCESS" -ForegroundColor Green -NoNewline
    Write-Host " (Exit Code: 0)                      ║" -ForegroundColor Cyan
} elseif ($script:HealthExitCode -eq 1) {
    Write-Host "║    Status: " -ForegroundColor Cyan -NoNewline
    Write-Host "⚠️  WARNING" -ForegroundColor Yellow -NoNewline
    Write-Host " (Exit Code: 1)                     ║" -ForegroundColor Cyan
} else {
    Write-Host "║    Status: " -ForegroundColor Cyan -NoNewline
    Write-Host "❌ ERROR" -ForegroundColor Red -NoNewline
    Write-Host " (Exit Code: $($script:HealthExitCode))                       ║" -ForegroundColor Cyan
}
Write-Host "║    Duration: $($script:HealthDuration.PadRight(45))║" -ForegroundColor Cyan
Write-Host "║    Timestamp: $($script:HealthTimestamp.PadRight(44))║" -ForegroundColor Cyan
Write-Host "║                                                           ║" -ForegroundColor Cyan

# Step 3 Report
Write-Host "║  Step 3: Integration Tests                                ║" -ForegroundColor Cyan
if ($script:IntegrationExitCode -eq -1) {
    Write-Host "║    Status: ⏭️  SKIPPED                                     ║" -ForegroundColor Cyan
} elseif ($script:IntegrationExitCode -eq 0) {
    Write-Host "║    Status: " -ForegroundColor Cyan -NoNewline
    Write-Host "✅ SUCCESS" -ForegroundColor Green -NoNewline
    Write-Host " (Exit Code: 0)                      ║" -ForegroundColor Cyan
} elseif ($script:IntegrationExitCode -eq 1) {
    Write-Host "║    Status: " -ForegroundColor Cyan -NoNewline
    Write-Host "⚠️  WARNING" -ForegroundColor Yellow -NoNewline
    Write-Host " (Exit Code: 1)                     ║" -ForegroundColor Cyan
} else {
    Write-Host "║    Status: " -ForegroundColor Cyan -NoNewline
    Write-Host "❌ ERROR" -ForegroundColor Red -NoNewline
    Write-Host " (Exit Code: $($script:IntegrationExitCode))                       ║" -ForegroundColor Cyan
}
Write-Host "║    Duration: $($script:IntegrationDuration.PadRight(45))║" -ForegroundColor Cyan
Write-Host "║    Timestamp: $($script:IntegrationTimestamp.PadRight(44))║" -ForegroundColor Cyan
Write-Host "║                                                           ║" -ForegroundColor Cyan

# Step 4 Report
Write-Host "║  Step 4: Persistency Tests                                ║" -ForegroundColor Cyan
if ($script:PersistencyExitCode -eq 0) {
    Write-Host "║    Status: " -ForegroundColor Cyan -NoNewline
    Write-Host "✅ SUCCESS" -ForegroundColor Green -NoNewline
    Write-Host " (Exit Code: 0)                      ║" -ForegroundColor Cyan
} elseif ($script:PersistencyExitCode -eq 1) {
    Write-Host "║    Status: " -ForegroundColor Cyan -NoNewline
    Write-Host "⚠️  WARNING" -ForegroundColor Yellow -NoNewline
    Write-Host " (Exit Code: 1)                     ║" -ForegroundColor Cyan
} else {
    Write-Host "║    Status: " -ForegroundColor Cyan -NoNewline
    Write-Host "❌ ERROR" -ForegroundColor Red -NoNewline
    Write-Host " (Exit Code: $($script:PersistencyExitCode))                       ║" -ForegroundColor Cyan
}
Write-Host "║    Duration: $($script:PersistencyDuration.PadRight(45))║" -ForegroundColor Cyan
Write-Host "║    Timestamp: $($script:PersistencyTimestamp.PadRight(44))║" -ForegroundColor Cyan

Write-Host "╠═══════════════════════════════════════════════════════════╣" -ForegroundColor Cyan

# Overall Status
if ($script:OverallExitCode -eq 0) {
    Write-Host "║  Overall Status: " -ForegroundColor Cyan -NoNewline
    Write-Host "✅ ALL STEPS COMPLETED SUCCESSFULLY" -ForegroundColor Green -NoNewline
    Write-Host "      ║" -ForegroundColor Cyan
} elseif ($script:OverallExitCode -eq 1) {
    Write-Host "║  Overall Status: " -ForegroundColor Cyan -NoNewline
    Write-Host "⚠️  COMPLETED WITH WARNINGS" -ForegroundColor Yellow -NoNewline
    Write-Host "              ║" -ForegroundColor Cyan
} else {
    Write-Host "║  Overall Status: " -ForegroundColor Cyan -NoNewline
    Write-Host "❌ CRITICAL ERRORS DETECTED" -ForegroundColor Red -NoNewline
    Write-Host "                ║" -ForegroundColor Cyan
}

Write-Host "║  Total Duration: $($totalDuration.PadRight(42))║" -ForegroundColor Cyan
Write-Host "║  Final Exit Code: $($script:OverallExitCode.ToString().PadRight(40))║" -ForegroundColor Cyan
Write-Host "╚═══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Final recommendations
if ($script:OverallExitCode -eq 0) {
    Write-StepStatus "success" "KRAI Docker environment is fully validated and ready!"
} elseif ($script:OverallExitCode -eq 1) {
    Write-StepStatus "warning" "System is functional but some warnings were detected."
    Write-Host ""
    Write-Host "Recommendations:" -ForegroundColor Yellow
    if (-not $env:BACKEND_API_TOKEN) {
        Write-Host "  - Set BACKEND_API_TOKEN environment variable for full integration tests"
    }
    Write-Host "  - Review individual step logs for detailed warnings"
    Write-Host "  - Consider running failed steps individually for more details"
} else {
    Write-StepStatus "error" "Critical errors detected. System may not be functional."
    Write-Host ""
    Write-Host "Recommendations:" -ForegroundColor Red
    Write-Host "  - Review error messages above for specific issues"
    Write-Host "  - Run failed steps individually with verbose output"
    Write-Host "  - Check Docker logs: docker logs <container-name>"
    Write-Host "  - Verify .env configuration and Docker daemon status"
}

Write-Host ""

if ($LogFile) {
    Stop-Transcript
}

exit $script:OverallExitCode
