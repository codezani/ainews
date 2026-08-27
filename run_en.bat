@echo off
title AI News Factory - English Edition
echo ========================================================
echo   AI News Factory - English Broadcast Edition (Windows)
echo ========================================================
echo.

if exist .venv\Scripts\python.exe (
    echo [OK] Using virtual environment...
    .\.venv\Scripts\python.exe run_weekly_en.py %*
) else (
    echo [OK] Using system Python...
    python run_weekly_en.py %*
)

echo.
echo ========================================================
echo   Generation finished! Check output/ folder for video.
echo ========================================================
pause
