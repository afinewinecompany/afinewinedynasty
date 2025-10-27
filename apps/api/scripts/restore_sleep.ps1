# PowerShell script to restore normal sleep settings

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Restoring Normal Sleep Settings" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Restore default sleep settings (30 minutes for AC, 15 minutes for DC)
Write-Host "Restoring sleep timeouts..." -ForegroundColor Yellow

powercfg /change standby-timeout-ac 30
powercfg /change standby-timeout-dc 15
powercfg /change hibernate-timeout-ac 60
powercfg /change hibernate-timeout-dc 30

Write-Host "Sleep settings restored!" -ForegroundColor Green
Write-Host ""

Write-Host "Current Power Settings:" -ForegroundColor Cyan
powercfg /query SCHEME_CURRENT SUB_SLEEP | Select-String "Standby|Hibernate" | ForEach-Object { Write-Host "  $_" }

Write-Host ""
Write-Host "System will now sleep normally." -ForegroundColor Green