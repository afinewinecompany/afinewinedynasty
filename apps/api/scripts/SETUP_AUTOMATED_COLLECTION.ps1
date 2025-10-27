# PowerShell script to set up Windows Task Scheduler for daily collection
# Run this as Administrator

$taskName = "AFineWineDynasty Daily Collection"
$taskDescription = "Automated daily collection of MLB prospect data"
$scriptPath = "C:\Users\lilra\myprojects\afinewinedynasty\apps\api\scripts\DAILY_COLLECTION_SCHEDULE.bat"

# Create the scheduled task action
$action = New-ScheduledTaskAction -Execute $scriptPath

# Create the trigger (daily at 3 AM)
$trigger = New-ScheduledTaskTrigger -Daily -At 3:00AM

# Create the principal (run whether user is logged in or not)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -LogonType S4U -RunLevel Limited

# Create the settings
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5)

# Register the task
try {
    $task = Register-ScheduledTask `
        -TaskName $taskName `
        -Description $taskDescription `
        -Action $action `
        -Trigger $trigger `
        -Principal $principal `
        -Settings $settings `
        -Force

    Write-Host "✓ Task scheduled successfully!" -ForegroundColor Green
    Write-Host "Task Name: $taskName"
    Write-Host "Schedule: Daily at 3:00 AM"
    Write-Host "Script: $scriptPath"
    Write-Host ""
    Write-Host "To test the task now, run:" -ForegroundColor Yellow
    Write-Host "Start-ScheduledTask -TaskName '$taskName'"
    Write-Host ""
    Write-Host "To view task status:" -ForegroundColor Yellow
    Write-Host "Get-ScheduledTask -TaskName '$taskName' | Get-ScheduledTaskInfo"
}
catch {
    Write-Host "✗ Error creating scheduled task: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Make sure to run this script as Administrator!" -ForegroundColor Yellow
}