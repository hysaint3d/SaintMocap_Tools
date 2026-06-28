@echo off
title Saint's OpenVR OSC Streamer
cd /d "%~dp0"

echo ===================================================
echo   Saint's OpenVR OSC Streamer Startup Script
echo ===================================================
echo.
echo Checking dependencies...
python -c "import openvr" 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] 'openvr' is not installed!
    echo Attempting to install 'openvr' automatically...
    python -m pip install openvr
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install 'openvr'. Please run "pip install openvr" manually.
        pause
        exit /b 1
    )
)

echo Starting OVR OSC Streamer...
python OVR_OSC_Streamer.pyw
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Streamer exited with an error code: %errorlevel%
    pause
)
