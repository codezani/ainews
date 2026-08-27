#!/usr/bin/env bash
set -e

echo "=== AI News Factory Installer (Linux / macOS) ==="

if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required. Please install python 3.10+."
    exit 1
fi

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create directories
mkdir -p models/piper data logs output

# Download Persian Piper voice
if [ ! -f "models/piper/fa_IR-ganji-medium.onnx" ]; then
    echo "Downloading Persian Piper TTS voice (ganji-medium)..."
    python -m piper.download_voices fa_IR-ganji-medium --data-dir models/piper || true
fi

# Download English Piper voice
if [ ! -f "models/piper/en_US-lessac-medium.onnx" ]; then
    echo "Downloading English Piper TTS voice (en_US-lessac-medium)..."
    python -m piper.download_voices en_US-lessac-medium --data-dir models/piper || true
fi

# Pull Ollama model if Ollama exists
if command -v ollama &> /dev/null; then
    echo "Pulling Qwen2.5 3B model for Ollama..."
    ollama pull qwen2.5:3b || true
else
    echo "Notice: Ollama not found. Install from https://ollama.com if running locally."
fi

echo "Installation finished successfully."
echo "Persian Edition: python run_weekly.py --test"
echo "English Edition: python run_weekly_en.py --test"
