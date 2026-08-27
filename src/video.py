from __future__ import annotations
import logging
import subprocess
import wave
import re
from pathlib import Path
from typing import List, Optional
from PIL import Image, ImageDraw, ImageFont

# Optional Persian reshaper & bidi support for proper RTL rendering
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    HAS_BIDI = True
except ImportError:
    HAS_BIDI = False

def is_rtl(text: str) -> bool:
    """Checks if text contains Persian/Arabic characters."""
    return bool(re.search(r"[\u0600-\u06FF]", text))

def format_text_direction(text: str) -> str:
    if not text:
        return ""
    if is_rtl(text) and HAS_BIDI:
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    return text

def get_font(size: int, prefer_english: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidate_fonts = [
        "C:\\Windows\\Fonts\\segoeui.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\tahoma.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "Vazirmatn-Bold.ttf", "Vazirmatn.ttf", "vazir.ttf"
    ] if prefer_english else [
        "Vazirmatn-Bold.ttf", "Vazirmatn.ttf", "vazir.ttf",
        "B Yekan.ttf", "Yekan.ttf", "IRANSans.ttf",
        "C:\\Windows\\Fonts\\tahoma.ttf", "C:\\Windows\\Fonts\\segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for fp in candidate_fonts:
        try:
            return ImageFont.truetype(fp, size)
        except Exception:
            continue
    return ImageFont.load_default()

def make_scene(out_png: Path | str, title: str, narration: str, image_path: Optional[Path | str], width: int = 1920, height: int = 1080) -> Path:
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)

    rtl_mode = is_rtl(f"{title} {narration}")

    # 1. Create stylish high-tech dark background
    img = Image.new("RGBA", (width, height), (13, 17, 23, 255))
    draw = ImageDraw.Draw(img)

    # 2. Add accent top gradient bar and frame
    draw.rectangle([(0, 0), (width, 8)], fill=(16, 185, 129, 255) if not rtl_mode else (59, 130, 246, 255))
    draw.rectangle([(36, 36), (width - 36, height - 36)], outline=(30, 41, 59, 255), width=2)

    # 3. Header badge
    badge_font = get_font(26, prefer_english=not rtl_mode)
    badge_text = "AI NEWS FACTORY | WEEKLY GLOBAL EDITION" if not rtl_mode else format_text_direction("بسته خبری هفتگی هوش مصنوعی | AI News Factory")
    
    if rtl_mode:
        draw.text((width - 80, 68), badge_text, fill=(148, 163, 184, 255), font=badge_font, anchor="rt")
    else:
        draw.text((80, 68), badge_text, fill=(52, 211, 153, 255), font=badge_font, anchor="lt")

    # 4. Main Title
    title_font = get_font(50, prefer_english=not rtl_mode)
    display_title = format_text_direction(title[:85])
    
    if rtl_mode:
        draw.text((width - 80, 135), display_title, fill=(248, 250, 252, 255), font=title_font, anchor="rt")
    else:
        draw.text((80, 135), display_title, fill=(248, 250, 252, 255), font=title_font, anchor="lt")

    # 5. Dual Column Layout (Image & Narrative Text)
    content_w = (width - 220) // 2
    content_h = height - 330
    y_base = 230

    if rtl_mode:
        img_x = 80
        text_x = width - 80
        text_anchor = "rt"
    else:
        # LTR: Text on Left, Media Card on Right
        img_x = width - content_w - 80
        text_x = 80
        text_anchor = "lt"

    # Render image thumbnail
    if image_path and Path(image_path).exists():
        try:
            thumb = Image.open(str(image_path)).convert("RGBA")
            thumb.thumbnail((content_w, content_h), Image.Resampling.LANCZOS)
            paste_y = y_base + (content_h - thumb.height) // 2
            img.paste(thumb, (img_x, paste_y))
            draw.rectangle([(img_x, paste_y), (img_x + thumb.width, paste_y + thumb.height)], 
                           outline=(51, 65, 85, 255), width=2)
        except Exception as e:
            logging.warning("Failed to render scene image: %s", e)

    # 6. Render wrapped narration text
    body_font = get_font(32, prefer_english=not rtl_mode)
    words = narration.split()
    lines = []
    curr = []
    max_line_len = 50 if rtl_mode else 46
    
    for w in words:
        curr.append(w)
        if len(" ".join(curr)) > max_line_len:
            lines.append(" ".join(curr))
            curr = []
    if curr:
        lines.append(" ".join(curr))

    y_pos = y_base + 20
    for line in lines[:8]:
        line_rendered = format_text_direction(line)
        draw.text((text_x, y_pos), line_rendered, fill=(226, 232, 240, 255), font=body_font, anchor=text_anchor)
        y_pos += 52

    img.save(str(out_png), "PNG")
    return out_png

def wav_duration(wav_path: Path | str) -> float:
    try:
        with wave.open(str(wav_path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return frames / float(rate)
    except Exception:
        return 5.0

def make_segment(image_png: Path | str, wav_file: Path | str, out_mp4: Path | str, fps: int = 30, crf: int = 22, preset: str = "medium") -> Path:
    out_mp4 = Path(out_mp4)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    
    dur = wav_duration(wav_file)
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(image_png),
        "-i", str(wav_file),
        "-c:v", "libx264", "-tune", "stillimage",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-r", str(fps),
        "-crf", str(crf),
        "-preset", preset,
        "-t", str(dur),
        "-shortest",
        str(out_mp4)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
    return out_mp4

def concat_segments(segment_paths: List[Path], out_mp4: Path | str) -> Path:
    out_mp4 = Path(out_mp4)
    list_file = out_mp4.parent / "concat_list.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for p in segment_paths:
            f.write(f"file '{p.resolve().as_posix()}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(out_mp4)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
    return out_mp4

def make_srt(sentence_text: List[str], sentence_durations: List[float], out_srt: Path | str) -> None:
    out_srt = Path(out_srt)
    out_srt.parent.mkdir(parents=True, exist_ok=True)

    def _fmt(sec: float) -> str:
        ms = int((sec % 1) * 1000)
        s = int(sec)
        h = s // 3600
        m = (s % 3600) // 60
        s_rem = s % 60
        return f"{h:02d}:{m:02d}:{s_rem:02d},{ms:03d}"

    lines = []
    curr = 0.0
    for idx, (txt, dur) in enumerate(zip(sentence_text, sentence_durations), 1):
        st = curr
        et = curr + dur
        curr = et
        lines.append(f"{idx}\n{_fmt(st)} --> {_fmt(et)}\n{txt}\n")

    out_srt.write_text("\n".join(lines), encoding="utf-8")
