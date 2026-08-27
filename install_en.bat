@echo off
title AI News Factory - English Setup
echo ========================================================
echo   Installing Dependencies & Piper English Voice
echo ========================================================
echo.

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

mkdir models\piper 2>nul
mkdir output 2>nul
mkdir data 2>nul

echo.
echo Downloading English Piper Voice (en_US-lessac-medium)...
python -m piper.download_voices en_US-lessac-medium --data-dir models\piper

echo.
echo ========================================================
echo   Setup Complete! You can now run run_en.bat or F5 in IDLE.
echo ========================================================
pause
