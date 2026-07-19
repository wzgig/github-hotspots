@echo off
setlocal
title GitHub Hotspots - Check and Update Reports

powershell.exe -NoLogo -NoProfile -ExecutionPolicy RemoteSigned -File "%~dp0scripts\automation\run_manual_update.ps1"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
    echo Check and update completed successfully.
) else (
    echo Check and update failed with exit code %EXIT_CODE%.
    echo Review the messages above and the logs under %%LOCALAPPDATA%%\GitHubHotspots\logs\.
)
echo.
pause
exit /b %EXIT_CODE%
