# PowerShell script to prevent Windows from sleeping during collections
# Run as Administrator for best results

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "MLB Collection Sleep Prevention Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Method 1: Using PowerCfg to temporarily disable sleep
Write-Host "Disabling sleep and hibernation..." -ForegroundColor Yellow

# Save current power settings
$originalACTimeout = powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE | Select-String "Current AC Power Setting Index" | ForEach-Object { $_.Line.Split(':')[1].Trim() }
$originalDCTimeout = powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE | Select-String "Current DC Power Setting Index" | ForEach-Object { $_.Line.Split(':')[1].Trim() }

# Disable sleep (0 = never)
powercfg /change standby-timeout-ac 0
powercfg /change standby-timeout-dc 0
powercfg /change hibernate-timeout-ac 0
powercfg /change hibernate-timeout-dc 0

Write-Host "Sleep disabled successfully!" -ForegroundColor Green
Write-Host ""

# Method 2: Keep system active with background activity
Write-Host "Starting keep-alive background process..." -ForegroundColor Yellow

# Create a background job that prevents idle
$keepAliveJob = Start-Job -ScriptBlock {
    Add-Type @"
        using System;
        using System.Runtime.InteropServices;

        public class KeepAwake {
            [DllImport("kernel32.dll")]
            public static extern uint SetThreadExecutionState(uint esFlags);

            public const uint ES_CONTINUOUS = 0x80000000;
            public const uint ES_SYSTEM_REQUIRED = 0x00000001;
            public const uint ES_DISPLAY_REQUIRED = 0x00000002;
        }
"@

    # Keep system awake
    [KeepAwake]::SetThreadExecutionState([KeepAwake]::ES_CONTINUOUS -bor [KeepAwake]::ES_SYSTEM_REQUIRED -bor [KeepAwake]::ES_DISPLAY_REQUIRED)

    # Keep alive loop
    while ($true) {
        Start-Sleep -Seconds 60
        Write-Output "Keep-alive tick at $(Get-Date)"
    }
}

Write-Host "Keep-alive process started (Job ID: $($keepAliveJob.Id))" -ForegroundColor Green
Write-Host ""

# Display status
Write-Host "Current Power Settings:" -ForegroundColor Cyan
powercfg /query SCHEME_CURRENT SUB_SLEEP | Select-String "Power Scheme GUID|Standby|Hibernate" | ForEach-Object { Write-Host "  $_" }

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "System will stay awake until you run:" -ForegroundColor Yellow
Write-Host "  .\restore_sleep.ps1" -ForegroundColor White
Write-Host "Or press Ctrl+C and run the restore script" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan

# Wait for user to press Ctrl+C
Write-Host ""
Write-Host "Press Ctrl+C when collections are done..." -ForegroundColor Yellow

try {
    while ($true) {
        Start-Sleep -Seconds 60
        # Check if Python processes are still running
        $pythonProcesses = Get-Process python -ErrorAction SilentlyContinue
        if ($pythonProcesses) {
            Write-Host "$(Get-Date -Format 'HH:mm:ss') - Python processes running: $($pythonProcesses.Count)" -ForegroundColor Gray
        } else {
            Write-Host "No Python processes found. Collections may be complete." -ForegroundColor Yellow
        }
    }
}
finally {
    # Cleanup on exit
    Write-Host ""
    Write-Host "Stopping keep-alive job..." -ForegroundColor Yellow
    Stop-Job -Job $keepAliveJob
    Remove-Job -Job $keepAliveJob

    Write-Host "Run .\restore_sleep.ps1 to restore original power settings" -ForegroundColor Yellow
}