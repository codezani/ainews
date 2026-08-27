from __future__ import annotations
import logging
from pathlib import Path
import requests

def download_image(url: str, out_path: Path | str, timeout: int = 10, min_bytes: int = 1024, max_bytes: int = 10485760) -> bool:
    if not url or not url.startswith("http"):
        return False
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AI-News-Bot/1.0"},
            stream=True
        )
        if not resp.ok:
            return False

        content_len = resp.headers.get("content-length")
        if content_len and (int(content_len) < min_bytes or int(content_len) > max_bytes):
            return False

        data = resp.content
        if len(data) < min_bytes or len(data) > max_bytes:
            return False

        out_path.write_bytes(data)
        return True
    except Exception as e:
        logging.warning("Failed to download image from %s: %s", url, e)
        return False
