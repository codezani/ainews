from __future__ import annotations
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict
import requests

class PreflightError(Exception):
    pass

def check_ffmpeg() -> None:
    if not shutil.which("ffmpeg"):
        raise PreflightError("ابزار FFmpeg روی PATH سیستم پیدا نشد. لطفاً FFmpeg را نصب کنید و مسیر bin آن را به PATH اضافه کنید.")

def check_piper_module() -> None:
    try:
        import piper  # type: ignore
    except ImportError:
        # Fallback to binary check
        if not shutil.which("piper"):
            raise PreflightError("ماژول piper-tts نصب نیست. لطفاً دستور: pip install piper-tts را اجرا کنید.")

def check_piper_voice(voice_name: str, data_dir: Path | str) -> None:
    p = Path(data_dir) / f"{voice_name}.onnx"
    if not p.exists():
        raise PreflightError(f"فایل مدل صدای فارسی ({voice_name}.onnx) در مسیر {data_dir} یافت نشد.\nدستور دانلود: python -m piper.download_voices {voice_name} --data-dir {data_dir}")

def check_ollama(host: str, model: str) -> None:
    host = host.rstrip("/")
    try:
        resp = requests.get(f"{host}/api/tags", timeout=4)
        if not resp.ok:
            raise PreflightError(f"سرویس Ollama روی {host} پاسخگو نیست.")
        data = resp.json()
        models = [m.get("name", "") for m in data.get("models", [])]
        if not models:
            print(f"\n⚠️ هشدار Ollama: هیچ مدلی روی سیستم یافت نشد. برای کیفیت بالا دستور زیر را اجرا کنید:\n   ollama pull {model}\n")
        elif model not in models and not any(model.split(":")[0] in m for m in models):
            print(f"\n💡 راهنما: مدل '{model}' در Ollama دانلود نشده است. مدل‌های موجود: {models}.\nسیستم به مدل موجود سوئیچ می‌کند یا می‌توانید دستور 'ollama pull {model}' را اجرا کنید.\n")
    except requests.exceptions.RequestException:
        raise PreflightError(f"ارتباط با Ollama برقرار نشد ({host}). لطفاً مطمئن شوید نرم‌افزار Ollama باز و در حال اجرا است.")
    except Exception as e:
        raise PreflightError(f"خطای Ollama: {e}")

def run_all(settings: Dict[str, Any], need_video: bool = True) -> None:
    check_ollama(settings.get("ollama_host", "http://localhost:11434"), settings.get("llm_model", "qwen2.5:3b"))
    if need_video:
        check_ffmpeg()
        check_piper_module()
        voice = settings.get("tts_voice", "fa_IR-ganji-medium")
        data_dir = settings.get("_root", Path(".")) / settings.get("tts_data_dir", "models/piper")
        check_piper_voice(voice, data_dir)
