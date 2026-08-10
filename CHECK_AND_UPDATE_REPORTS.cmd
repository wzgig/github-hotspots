@echo off
setlocal
title GitHub Hotspots - Check and Repair Daily and Weekly Reports

powershell.exe -NoLogo -NoProfile -ExecutionPolicy RemoteSigned -File "%~dp0scripts\automation\run_manual_update.ps1"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
    echo Daily and weekly report check and repair completed successfully.
) else if "%EXIT_CODE%"=="76" (
    echo No safe frozen weekly report is available for automatic recovery.
    echo Historical rankings were not recollected or fabricated.
) else (
    echo Check and update failed with exit code %EXIT_CODE%.
    echo Review the messages above and the logs under %%LOCALAPPDATA%%\GitHubHotspots\logs\.
)
echo.
pause
exit /b %EXIT_CODE%
