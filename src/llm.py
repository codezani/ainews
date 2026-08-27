from __future__ import annotations
import json
import logging
import re
from typing import Any, Dict, List
import requests

class Ollama:
    def __init__(self, host: str, model: str = "qwen2.5:3b", timeout: int = 120, context: int = 4096, predict: int = 1024, keep_alive: str = "5m"):
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.context = context
        self.predict = predict
        self.keep_alive = keep_alive
        self.available_models: List[str] = []
        self._check_and_resolve_model()

    def _check_and_resolve_model(self) -> None:
        """Auto-detects available models in Ollama and switches to an installed one if needed."""
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=4)
            if resp.ok:
                data = resp.json()
                self.available_models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
                
                # Check exact match
                if self.model in self.available_models:
                    return
                
                # Check base name (e.g. qwen2.5 in qwen2.5:3b)
                base = self.model.split(":")[0]
                for m in self.available_models:
                    if m.startswith(base) or base in m:
                        logging.info("Auto-selected matching Ollama model: %s (requested: %s)", m, self.model)
                        self.model = m
                        return
                
                # If requested model not found, choose the best available or first installed
                if self.available_models:
                    preferred = [m for m in self.available_models if any(k in m.lower() for k in ["qwen", "llama", "gemma", "mistral"])]
                    selected = preferred[0] if preferred else self.available_models[0]
                    logging.warning("Configured model '%s' not found. Auto-switched to installed model '%s'", self.model, selected)
                    self.model = selected
                else:
                    logging.warning("No models found in Ollama. Please run: 'ollama pull %s'", self.model)
        except Exception as e:
            logging.warning("Could not query Ollama tags (%s). Will attempt direct call with '%s'", e, self.model)

    def health(self) -> bool:
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=5)
            return resp.ok
        except Exception as e:
            raise RuntimeError(f"Cannot connect to Ollama at {self.host}. Is Ollama running? Error: {e}")

    def generate(self, prompt: str, system: str = "", temperature: float = 0.3, predict: int | None = None) -> str:
        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_ctx": self.context,
                "num_predict": predict or self.predict,
            },
            "keep_alive": self.keep_alive
        }
        
        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
            if resp.status_code == 404:
                err_msg = ""
                try:
                    err_msg = resp.json().get("error", "")
                except Exception:
                    pass
                raise RuntimeError(f"Ollama model '{self.model}' not found (404). Run 'ollama pull {self.model}' in terminal. {err_msg}")
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except requests.exceptions.HTTPError as e:
            if resp.status_code == 404:
                raise RuntimeError(f"Ollama model '{self.model}' is not pulled. Run: ollama pull {self.model}") from e
            raise e

def _extract_json(raw: str) -> Any:
    """Safely extracts JSON from LLM output markdown or raw text."""
    raw = raw.strip()
    match = re.search(r"```(?:json)?s*([sS]*?)s*```", raw)
    cleaned = match.group(1) if match else raw
    # Try direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback: search for first { or [ to last } or ]
        first_brace = min(
            (cleaned.find('{') if '{' in cleaned else 999999),
            (cleaned.find('[') if '[' in cleaned else 999999)
        )
        last_brace = max(cleaned.rfind('}'), cleaned.rfind(']'))
        if first_brace < last_brace:
            return json.loads(cleaned[first_brace:last_brace+1])
        raise

def score_clusters(client: Ollama, clusters: List[List[Dict[str, Any]]], prompt_template: str, batch: int = 4, predict: int = 512, temp: float = 0.2) -> List[Dict[str, Any]]:
    scored: List[Dict[str, Any]] = []

    for i in range(0, len(clusters), batch):
        batch_clusters = clusters[i:i+batch]
        stories_input = []
        
        for idx, cl in enumerate(batch_clusters, 1):
            rep = max(cl, key=lambda x: (1 if x.get("source_type") == "primary" else 0, x.get("pre_score", 0)))
            stories_input.append({
                "cluster_index": idx,
                "title": rep.get("title"),
                "summary": (rep.get("summary") or "")[:250],
                "source": rep.get("source"),
                "source_count": len(cl)
            })

        rendered_prompt = prompt_template.replace("{{STORIES_JSON}}", json.dumps(stories_input, ensure_ascii=False, indent=2))
        
        try:
            raw_resp = client.generate(rendered_prompt, temperature=temp, predict=predict)
            results = _extract_json(raw_resp)
            if isinstance(results, dict) and "stories" in results:
                results = results["stories"]
            
            for res_item in results:
                c_idx = res_item.get("cluster_index", 1) - 1
                if 0 <= c_idx < len(batch_clusters):
                    target_cluster = batch_clusters[c_idx]
                    rep = max(target_cluster, key=lambda x: (1 if x.get("source_type") == "primary" else 0, x.get("pre_score", 0)))
                    scored_item = {
                        **rep,
                        "score": float(res_item.get("score", 75)),
                        "title_fa": res_item.get("title_fa", rep.get("title")),
                        "why_matters_fa": res_item.get("why_matters_fa", ""),
                        "source_count": len(target_cluster),
                        "_cluster": target_cluster
                    }
                    scored.append(scored_item)
        except Exception as e:
            logging.warning("Batch scoring fallback for batch %d (Ollama model check: %s)", i, e)
            for target_cluster in batch_clusters:
                rep = max(target_cluster, key=lambda x: (1 if x.get("source_type") == "primary" else 0, x.get("pre_score", 0)))
                clean_title = rep.get("title", "")
                scored.append({
                    **rep,
                    "score": max(70.0, float(rep.get("pre_score", 70.0))),
                    "title_fa": clean_title,
                    "why_matters_fa": f"تحول کلیدی در اکوسیستم هوش مصنوعی از منبع {rep.get('source', '')}",
                    "source_count": len(target_cluster),
                    "_cluster": target_cluster
                })

    return scored

def score_batches(client: Ollama, clusters: List[List[Dict[str, Any]]], prompt_template: str, batch_size: int = 4, predict: int = 512, temp: float = 0.2) -> List[Dict[str, Any]]:
    """Alias for score_clusters() using the `batch_size` keyword name expected
    by the pipeline runners (run_weekly.py / run_weekly_en.py)."""
    return score_clusters(client, clusters, prompt_template, batch=batch_size, predict=predict, temp=temp)

def build_episode(client: Ollama, selected_stories: List[Dict[str, Any]], prompt_template: str, target_words: int, predict: int = 2048, max_chars: int = 1500, temp: float = 0.3) -> Dict[str, Any]:
    context_stories = []
    for idx, s in enumerate(selected_stories, 1):
        context_stories.append({
            "story_number": idx,
            "title": s.get("title"),
            "title_fa": s.get("title_fa"),
            "source": s.get("source"),
            "summary": (s.get("content") or s.get("summary") or "")[:max_chars],
            "why_matters_fa": s.get("why_matters_fa")
        })

    rendered_prompt = prompt_template.replace("{{STORIES_JSON}}", json.dumps(context_stories, ensure_ascii=False, indent=2))
    rendered_prompt = rendered_prompt.replace("{{TARGET_WORDS}}", str(target_words))

    try:
        raw_resp = client.generate(rendered_prompt, temperature=temp, predict=predict)
        episode = _extract_json(raw_resp)
        if isinstance(episode, dict) and "scenes" in episode and len(episode["scenes"]) > 0:
            return episode
    except Exception as e:
        logging.warning("LLM script generation fallback triggered (%s). Generating heuristic Persian episode.", e)

    # Robust Fallback Persian Script Generator (guarantees run_weekly never crashes)
    scenes = []
    scenes.append({
        "scene_number": 1,
        "kind": "intro",
        "title_fa": "مهم‌ترین رویدادهای هفته هوش مصنوعی",
        "narration_fa": "سلام به همراهان عزیز کارخانه خبر هوش مصنوعی. در این برنامه نگاهی جامع داریم به مهم‌ترین دستاوردها، پیشرفت‌های فنی و تحولات دنیای هوش مصنوعی در هفته‌ای که گذشت. با ما همراه باشید.",
        "story_numbers": []
    })

    for idx, story in enumerate(selected_stories, 1):
        title = story.get("title_fa") or story.get("title") or f"خبر شماره {idx}"
        summary = (story.get("summary") or story.get("content") or "").strip()
        why = story.get("why_matters_fa") or "این دستاورد نشان‌دهنده شتاب بالای تحول مدل‌های نوین است."
        
        narration = f"در خبر برگزیده این بخش از {story.get('source', 'منابع تخصصی')}: {title}. {summary[:280]} {why}"
        scenes.append({
            "scene_number": idx + 1,
            "kind": "story",
            "title_fa": title[:65],
            "narration_fa": narration.strip(),
            "story_numbers": [idx]
        })

    scenes.append({
        "scene_number": len(selected_stories) + 2,
        "kind": "outro",
        "title_fa": "جمع‌بندی و چشم‌انداز هفتگی",
        "narration_fa": "این بود مرور مهم‌ترین اخبار و دستاوردهای هوش مصنوعی در این هفته. برای پیگیری جدیدترین تحلیل‌ها و اخبار دنیای فناوری، کانال ما را دنبال کنید. تا هفته آینده و گزارش بعدی، بدرود.",
        "story_numbers": []
    })

    return {
        "episode_title_fa": "مرور جامع و تحلیلی اخبار هوش مصنوعی هفته",
        "scenes": scenes
    }
