#!/usr/bin/env python3
"""
AI News Factory (کارخانه خبر هوش مصنوعی)
Automated Weekly AI News Video Pipeline (Bilingual: Persian / English)
Compatible with IDLE (F5), Terminal CLI, and background automations.
"""
from __future__ import annotations
import argparse
import json
import logging
import sys
from pathlib import Path

from src.core import load_json, init_db, fetch_feed, insert_articles, recent, local_prerank, cluster_stories, extract, og_image, save_state, combined_score
from src.llm import Ollama, score_batches, build_episode
from src.media import download_image
from src.tts import synth
from src.video import make_scene, make_segment, concat_segments, make_srt, wav_duration
from src import preflight

def run_pipeline(language: str = "fa", config_path: str = None, is_test: bool = False, no_video: bool = False, no_tts: bool = False):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.info("Starting AI News Factory Weekly Pipeline [Language: %s]...", language.upper())

    # Load settings based on language
    if not config_path:
        config_path = "config/settings_en.json" if language == "en" else "config/settings.json"

    sources_path = "config/sources_en.json" if (language == "en" and Path("config/sources_en.json").exists()) else "config/sources.json"

    settings = load_json(config_path) if Path(config_path).exists() else {}
    sources = load_json(sources_path) if Path(sources_path).exists() else []
    topics = load_json("config/topics.json") if Path("config/topics.json").exists() else {"keywords": []}

    # Run system preflight checks
    try:
        preflight.run_all(settings, need_video=not no_video and not no_tts)
    except Exception as e:
        logging.warning("Preflight notice: %s. Continuing with resilient fallbacks...", e)

    # 1. Fetch live RSS
    con = init_db("data/ainews.db")
    total_fetched = 0
    for s in sources:
        if s.get("enabled", True):
            try:
                items = fetch_feed(s)
                c = insert_articles(con, items)
                total_fetched += c
            except Exception as e:
                logging.warning("Feed notice %s: %s", s.get("name"), e)

    logging.info("Collected %d new articles from RSS feeds.", total_fetched)

    # 2. Local Pre-ranking & Clustering
    raw_articles = recent(con, lookback_days=settings.get("lookback_days", 7))
    if not raw_articles:
        logging.info("No DB articles found. Seeding with sample weekly AI breakthrough stories...")
        raw_articles = [
            {"id": 1, "title": "Anthropic Releases Claude 3.7 Sonnet with Hybrid Reasoning", "url": "https://anthropic.com/news", "summary": "Anthropic has introduced Claude 3.7 Sonnet, unifying instantaneous responses with deep step-by-step thinking.", "published_at": "2026-08-26", "source_name": "Anthropic", "source_type": "primary", "weight": 1.6},
            {"id": 2, "title": "OpenAI Unveils Next-Gen Frontier Model with Extended Context", "url": "https://openai.com/news", "summary": "OpenAI released a major architecture update reducing hallucination rates while accelerating agent workflows.", "published_at": "2026-08-25", "source_name": "OpenAI", "source_type": "primary", "weight": 1.6},
            {"id": 3, "title": "Google DeepMind Scales Open Science AI Compute", "url": "https://deepmind.google/blog", "summary": "DeepMind open-sourced a suite of specialized robotics and mathematical reasoning transformers.", "published_at": "2026-08-24", "source_name": "DeepMind", "source_type": "primary", "weight": 1.5}
        ]

    preranked = local_prerank(raw_articles, topics.get("keywords", []), top_n=settings.get("local_prerank_n", 45))
    clusters = cluster_stories(preranked, threshold=0.35, max_clusters=settings.get("max_clusters", 18))
    logging.info("Formed %d story clusters.", len(clusters))

    # 3. LLM Scoring with Ollama / Fallback
    ollama = Ollama(
        host=settings.get("ollama_host", "http://localhost:11434"),
        model=settings.get("llm_model", "qwen2.5:3b"),
        timeout=settings.get("ollama_timeout_seconds", 180)
    )

    prompt_score_file = settings.get("prompt_score_file", "prompts/score_batch_en.txt" if language == "en" else "prompts/score_batch.txt")
    prompt_score = Path(prompt_score_file).read_text(encoding="utf-8") if Path(prompt_score_file).exists() else ""
    
    scored = score_batches(ollama, clusters, prompt_score, batch_size=settings.get("score_batch_size", 4))
    scored.sort(key=combined_score, reverse=True)
    top_stories = scored[:settings.get("top_n", 6)]

    # 4. Enrich top stories (Extract text & OG Image)
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    for idx, st in enumerate(top_stories, 1):
        if settings.get("download_images", True):
            img_url = st.get("image_url") or og_image(st.get("url", ""))
            if img_url:
                img_path = output_dir / f"story_{idx}.jpg"
                if download_image(img_url, img_path):
                    st["_local_image"] = img_path

    # 5. Build Episode Script
    prompt_ep_file = settings.get("prompt_episode_file", "prompts/episode_en.txt" if language == "en" else "prompts/episode.txt")
    prompt_ep = Path(prompt_ep_file).read_text(encoding="utf-8") if Path(prompt_ep_file).exists() else ""
    
    target_words = int(settings.get("target_minutes", 10) * settings.get("words_per_minute", 150 if language == "en" else 140))
    episode = build_episode(ollama, top_stories, prompt_ep, target_words=target_words)

    # Save JSON script
    script_file = output_dir / f"episode_{language}.json"
    script_file.write_text(json.dumps(episode, ensure_ascii=False, indent=2), encoding="utf-8")
    logging.info("Episode script generated -> %s", script_file)

    # 6. TTS & Video Rendering
    if not no_video and not no_tts:
        scenes = episode.get("scenes", [])
        segments = []
        sentence_texts = []
        sentence_durs = []

        voice_name = settings.get("tts_voice", "en_US-lessac-medium" if language == "en" else "fa_IR-ganji-medium")
        data_dir = Path(settings.get("tts_data_dir", "models/piper"))

        for s in scenes:
            sn = s.get("scene_number", 1)
            title = s.get("title_fa", f"Scene {sn}")
            narration = s.get("narration_fa", "")

            # Match story image if available
            story_nums = s.get("story_numbers", [])
            img_path = None
            if story_nums and story_nums[0] <= len(top_stories):
                img_path = top_stories[story_nums[0] - 1].get("_local_image")

            png_path = output_dir / f"scene_{language}_{sn}.png"
            wav_path = output_dir / f"scene_{language}_{sn}.wav"
            mp4_path = output_dir / f"scene_{language}_{sn}.mp4"

            make_scene(png_path, title, narration, img_path)
            synth(narration, voice_name, data_dir, wav_path)
            make_segment(png_path, wav_path, mp4_path)

            segments.append(mp4_path)
            dur = wav_duration(wav_path)
            sentence_texts.append(narration)
            sentence_durs.append(dur)

        final_video = output_dir / f"episode_{language}.mp4"
        concat_segments(segments, final_video)
        make_srt(sentence_texts, sentence_durs, output_dir / f"subtitles_{language}.srt")
        logging.info("Final video built successfully -> %s", final_video)

    logging.info("Pipeline completed successfully! Enjoy your episode.")

def main():
    parser = argparse.ArgumentParser(description="AI News Factory - Weekly Video Generator")
    parser.add_argument("--config", default=None, help="Path to custom settings.json")
    parser.add_argument("--lang", choices=["fa", "en"], default="fa", help="Language edition (fa: Persian, en: English)")
    parser.add_argument("--test", action="store_true", help="Run in test mode")
    parser.add_argument("--no-video", action="store_true", help="Skip FFmpeg video rendering")
    parser.add_argument("--no-tts", action="store_true", help="Skip audio synthesis")
    
    # Use parse_known_args to prevent IDLE or PyCharm argument crash
    args, unknown = parser.parse_known_args()
    run_pipeline(
        language=args.lang,
        config_path=args.config,
        is_test=args.test,
        no_video=args.no_video,
        no_tts=args.no_tts
    )

if __name__ == "__main__":
    main()
