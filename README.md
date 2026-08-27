# AI News Factory 🇮🇷

A fully **local** system that automatically generates a weekly Persian AI news video.

Designed for Windows and low-VRAM laptops (e.g. ASUS TUF F15 with RTX 3050 Ti 4GB).

---

## Key Features

- Fetches news from RSS feeds
- URL deduplication
- Local pre-ranking (no LLM)
- Story clustering
- Selects 7–9 important stories using **Qwen3 4B** (via Ollama)
- Generates a Persian script
- Text-to-speech with **Piper TTS** (Persian voices)
- Builds the video with FFmpeg (no AI video generation)
- Output: ~10-minute MP4 + SRT subtitles + sources

**No paid APIs required.** The core system runs completely offline.

---

## Pipeline

```text
RSS / News
   ↓
Collect last 7 days
   ↓
URL Deduplication
   ↓
Local Pre-Ranking
   ↓
Story Clustering
   ↓
Extract full text only for important candidates
   ↓
Qwen3 4B Local
   ↓
Select 7–9 Stories
   ↓
Generate Persian Script
   ↓
Piper TTS (Persian)
   ↓
Build Scenes + News Images
   ↓
FFmpeg
   ↓
~10 min MP4 + SRT + Sources




Why It’s Optimized for RTX 3050 Ti 4GBHundreds of articles are first filtered and reduced on CPU
Full text is extracted for only ~45 candidates
LLM runs sequentially and lightly
Default model: qwen3:4b-instruct-2507-q4_K_M (~2.5 GB)
No Stable Diffusion, Flux, or AI video generation
Fully local TTS
Controlled VRAM usage (default context: 6144)

PrerequisitesWindows 10/11
Python 3.11 or 3.12
Ollama
FFmpeg (must be in PATH)
At least 4 GB VRAM (recommended)

InstallationIn PowerShell:powershell

Set-ExecutionPolicy -Scope Process Bypass
cd C:\path\to\ainews
.\install.ps1

If Ollama or FFmpeg are not found, install them manually and run install.ps1 again.Ollama’s local API runs by default at http://localhost:11434.UsageTest run (no video)powershell

.\.venv\Scripts\python.exe run_weekly.py --test --no-video

Full runpowershell

.\.venv\Scripts\python.exe run_weekly.py

Or use the helper scripts:powershell

.\run_test.ps1
.\run_full.ps1

Example outputtext

output\2026-W35\
├── episode.mp4
├── episode.json
├── script_fa.md
├── subtitles.srt
├── selected_stories.json
├── sources.json
├── report.json
├── scenes\
├── segments\
└── media\

Weekly Scheduling (Task Scheduler)After a successful run:powershell

.\scripts\create_task.ps1

By default it creates a weekly task for Sundays at 22:00. Change the time in the script if needed.News Selection Architecture1. Local Pre-Rank (no LLM)Recency
Source weight
AI keywords
Reduces ~250–400 items → ~45 candidates

2. Story ClusteringArticles about the same event from different sources are grouped into one story.3. LLM Editorial ScoringQwen scores each cluster on:importance
impact
novelty
credibility
audience interest
topic
risk

4. Script GenerationOnly the selected stories are sent to the model to reduce hallucination.Video Length Control (~10 minutes)The system measures the actual duration of each audio segment (WAV).
If the total episode falls outside the 9:24 – 10:36 range, it adjusts the target word count once and regenerates.Persian TTSDefault voice:text

fa_IR-ganji-medium

Other available voices:fa_IR-amir-medium
fa_IR-gyro-medium

Change the voice in config/settings.json.Internet & Offline UsageThe AI core is fully local:Component
Status
Qwen
Local
Ollama
Local
Piper
Local
FFmpeg
Local
SQLite
Local

The only required online parts are RSS fetching and (optionally) downloading news images.To reduce internet usage, set in config/settings.json:json

"download_images": false

In this mode the video is built using text-only scene cards.Project Structuretext

ainews/
├── config/
│   ├── settings.json
│   ├── sources.json
│   └── topics.json
├── prompts/
│   ├── score_batch.txt
│   └── episode.txt
├── src/
│   ├── core.py
│   ├── llm.py
│   ├── media.py
│   ├── tts.py
│   └── video.py
├── scripts/
│   └── create_task.ps1
├── models/piper/
├── data/
├── logs/
├── output/
├── run_weekly.py
├── run_full.ps1
├── run_test.ps1
├── install.ps1
├── diagnose.ps1
├── diagnose.py
└── requirements.txt

Important Notes Before PublishingThis is not a fully autonomous publishing system.Before releasing publicly:Review selected_stories.json
Check sources.json
Read script_fa.md
Remove any unwanted stories if needed
Then publish episode.mp4

This project does not perform independent fact-checking.SecurityLocalhost / private / link-local addresses are blocked
RSS, article, and image sizes are limited
Article text is treated as UNTRUSTED SOURCE MATERIAL
No news URL or text is ever executed as a shell command

LicenseThe project code can be used and modified according to the LICENSE file.
However, the rights to images, text, and content from news sites belong to their respective owners. Always check the source terms before public distribution.

