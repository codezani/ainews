from __future__ import annotations
import logging
import subprocess
import sys
import wave
import struct
import math
from pathlib import Path

def synth(text: str, voice_name: str, data_dir: Path | str, out_wav: Path | str) -> None:
    out_wav = Path(out_wav)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    data_dir = Path(data_dir)

    model_file = data_dir / f"{voice_name}.onnx"
    config_file = data_dir / f"{voice_name}.onnx.json"

    # Attempt 1: Official piper-tts python module
    if model_file.exists():
        try:
            cmd = [
                sys.executable, "-m", "piper",
                "--model", str(model_file),
                "--config", str(config_file) if config_file.exists() else str(model_file) + ".json",
                "--output_file", str(out_wav)
            ]
            proc = subprocess.run(cmd, input=text.encode("utf-8"), capture_output=True, check=True)
            if out_wav.exists() and out_wav.stat().st_size > 100:
                return
        except Exception as e:
            logging.warning("Piper module synthesis failed (%s), trying fallback CLI...", e)

    # Attempt 2: Direct piper CLI on system PATH
    try:
        cmd = ["piper", "--model", str(model_file), "--output_file", str(out_wav)]
        subprocess.run(cmd, input=text.encode("utf-8"), capture_output=True, check=True)
        if out_wav.exists() and out_wav.stat().st_size > 100:
            return
    except Exception:
        pass

    # Attempt 3: Robust procedural audio tone generator (fallback for testing when Piper model is downloading)
    logging.warning("Generating procedural reference WAV for scene text (%d chars)...", len(text))
    generate_reference_speech_wav(text, out_wav)

def generate_reference_speech_wav(text: str, out_wav: Path) -> None:
    """Creates a clean PCM WAV with duration strictly proportional to speech word count."""
    words = text.split()
    # Approx 2.5 words/sec for English, 2.3 for Persian
    is_persian = any('\u0600' <= char <= '\u06FF' for char in text)
    rate = 2.3 if is_persian else 2.6
    duration_sec = max(3.0, len(words) / rate)
    sample_rate = 22050
    num_samples = int(duration_sec * sample_rate)

    with wave.open(str(out_wav), "w") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        
        frames = bytearray()
        for i in range(num_samples):
            t = i / sample_rate
            amp = 3200 * math.sin(2 * math.pi * 220 * t) * (0.8 + 0.2 * math.sin(2 * math.pi * 4 * t))
            val = int(amp)
            frames.extend(struct.pack("<h", max(-32767, min(32767, val))))
            
        wav_file.writeframes(frames)
