#!/usr/bin/env python3
"""
AI News Factory - Dedicated English Broadcast Edition Runner
=============================================================
This script runs the 100% English pipeline:
1. Ingests premier global English AI RSS feeds (OpenAI, Anthropic, DeepMind, TechCrunch, MIT Tech Review, ArXiv)
2. Clusters and scores breakthrough stories using English criteria
3. Writes a broadcast-quality English script with intro, story scenes, and outro
4. Renders Left-to-Right Full HD 1080p visual scene cards
5. Synthesizes English voiceover (Piper en_US-lessac-medium)
6. Compiles final output/episode_en.mp4 and synchronized output/subtitles_en.srt

HOW TO RUN:
- In Python IDLE: Press F5
- In Terminal: python run_weekly_en.py
- On Windows: Double-click run_en.bat
"""
from __future__ import annotations
import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def ensure_dependencies():
    """Checks and auto-installs missing packages in user's Python environment."""
    required = ["requests", "pillow", "piper-tts"]
    missing = []
    for pkg in required:
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            missing.append(pkg)
    
    if missing:
        print(f"[Notice] Missing packages: {missing}. Auto-installing with pip...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", *missing, "feedparser", "beautifulsoup4"])
            print("[Success] All dependencies installed successfully.")
        except Exception as e:
            print(f"[Warning] Pip auto-install notice: {e}. Attempting to proceed with built-in modules...")

def main():
    # Make sure packages are present
    ensure_dependencies()

    parser = argparse.ArgumentParser(description="AI News Factory - English Video Generator")
    parser.add_argument("--config", default="config/settings_en.json", help="Path to settings_en.json")
    parser.add_argument("--test", action="store_true", help="Run in quick test mode")
    parser.add_argument("--no-video", action="store_true", help="Skip video rendering")
    parser.add_argument("--no-tts", action="store_true", help="Skip audio synthesis")
    
    # parse_known_args guarantees IDLE F5 never crashes on unexpected flags
    args, unknown = parser.parse_known_args()
    
    try:
        from run_weekly import run_pipeline
        run_pipeline(
            language="en",
            config_path=args.config,
            is_test=args.test,
            no_video=args.no_video,
            no_tts=args.no_tts
        )
    except Exception as e:
        logging.exception("Pipeline error: %s", e)
        print(f"\n[Error] {e}")

if __name__ == "__main__":
    main()
