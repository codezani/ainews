$ErrorActionPreference = "Stop"
Write-Host "=== AI News Factory Fixed Windows Installer ===" -ForegroundColor Cyan

function Has($name) { return [bool](Get-Command $name -ErrorAction SilentlyContinue) }

if (-not (Has python)) { throw "Python 3.10+ is required and must be on PATH." }
Write-Host "Python found: $(& python --version)"

if (-not (Test-Path .venv)) { & python -m venv .venv }
$vp = Join-Path $PWD ".venv\Scripts\python.exe"

& $vp -m pip install --upgrade pip wheel setuptools
& $vp -m pip install -r requirements.txt

# Check FFmpeg
if (-not (Has ffmpeg)) {
    Write-Host "FFmpeg is missing. Download from https://ffmpeg.org and add to PATH." -ForegroundColor Yellow
} else {
    Write-Host "FFmpeg: OK" -ForegroundColor Green
}

# Piper Voices Directory
New-Item -ItemType Directory -Force -Path models\piper | Out-Null

# 1. Piper Persian Voice
$voiceModelFa = Join-Path (Join-Path $PWD 'models\piper') 'fa_IR-ganji-medium.onnx'
if (-not (Test-Path $voiceModelFa)) {
    Write-Host "Downloading Persian Piper voice (fa_IR-ganji-medium)..." -ForegroundColor Green
    & $vp -m piper.download_voices fa_IR-ganji-medium --data-dir models\piper
} else {
    Write-Host "Piper Persian voice already installed." -ForegroundColor Green
}

# 2. Piper English Voice
$voiceModelEn = Join-Path (Join-Path $PWD 'models\piper') 'en_US-lessac-medium.onnx'
if (-not (Test-Path $voiceModelEn)) {
    Write-Host "Downloading English Piper voice (en_US-lessac-medium)..." -ForegroundColor Green
    & $vp -m piper.download_voices en_US-lessac-medium --data-dir models\piper
} else {
    Write-Host "Piper English voice already installed." -ForegroundColor Green
}

# Pull valid Qwen model for Ollama
if (Has ollama) {
    Write-Host "Pulling Qwen2.5 3B (qwen2.5:3b)..." -ForegroundColor Green
    & ollama pull qwen2.5:3b
} else {
    Write-Host "Ollama is not installed. Download from https://ollama.com" -ForegroundColor Yellow
}

Write-Host "Installation complete!" -ForegroundColor Green
Write-Host "  To run Persian edition: .\.venv\Scripts\python.exe run_weekly.py" -ForegroundColor Cyan
Write-Host "  To run English edition: .\.venv\Scripts\python.exe run_weekly_en.py" -ForegroundColor Cyan
