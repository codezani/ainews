from __future__ import annotations
import json
import sqlite3
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Resilient optional imports with fallback to standard library
try:
    import requests
except ImportError:
    requests = None

try:
    import feedparser
except ImportError:
    feedparser = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    import trafilatura
except ImportError:
    trafilatura = None

def load_json(path: Path | str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Configuration file not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))

def init_db(db_path: Path | str) -> sqlite3.Connection:
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p))
    con.row_factory = sqlite3.Row
    with con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                url TEXT PRIMARY KEY,
                source TEXT,
                source_type TEXT,
                title TEXT,
                summary TEXT,
                content TEXT,
                image_url TEXT,
                published_at TEXT,
                created_at TEXT,
                pre_score REAL DEFAULT 0,
                cluster_id INTEGER DEFAULT 0,
                importance_score REAL DEFAULT 0,
                final_score REAL DEFAULT 0,
                status TEXT DEFAULT 'new'
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_published ON articles(published_at)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_cluster ON articles(cluster_id)")
    return con

def _parse_xml_feed_fallback(raw_xml: str, source_name: str, source_type: str, weight: float) -> List[Dict[str, Any]]:
    """Native Python Standard Library parser for RSS 2.0 and Atom feeds when feedparser is not installed."""
    items = []
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        root = ET.fromstring(raw_xml)
        
        # Check RSS 2.0 (<channel><item>...)
        channel = root.find("channel")
        if channel is not None:
            for item in channel.findall("item"):
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                desc = (item.findtext("description") or "").strip()
                desc = re.sub(r"<[^>]+>", " ", desc).strip()
                pub = (item.findtext("pubDate") or now_iso).strip()
                if link and title:
                    items.append({
                        "url": link,
                        "source": source_name,
                        "source_type": source_type,
                        "weight": weight,
                        "title": title,
                        "summary": desc[:500],
                        "content": "",
                        "image_url": "",
                        "published_at": pub,
                        "created_at": now_iso
                    })
            return items

        # Check Atom (<feed><entry>...)
        for entry in root.findall("{http://www.w3.org/2005/Atom}entry") or root.findall("entry"):
            title = (entry.findtext("{http://www.w3.org/2005/Atom}title") or entry.findtext("title") or "").strip()
            link_elem = entry.find("{http://www.w3.org/2005/Atom}link") or entry.find("link")
            link = link_elem.get("href", "") if link_elem is not None else ""
            summary = (entry.findtext("{http://www.w3.org/2005/Atom}summary") or entry.findtext("summary") or "").strip()
            summary = re.sub(r"<[^>]+>", " ", summary).strip()
            pub = (entry.findtext("{http://www.w3.org/2005/Atom}published") or entry.findtext("updated") or now_iso).strip()
            if link and title:
                items.append({
                    "url": link,
                    "source": source_name,
                    "source_type": source_type,
                    "weight": weight,
                    "title": title,
                    "summary": summary[:500],
                    "content": "",
                    "image_url": "",
                    "published_at": pub,
                    "created_at": now_iso
                })
    except Exception:
        pass
    return items

def fetch_feed(source: Dict[str, Any], timeout: int = 15, retries: int = 2) -> List[Dict[str, Any]]:
    url = source["url"]
    name = source["name"]
    source_type = source.get("type", "secondary")
    weight = source.get("weight", 1.0)
    now_iso = datetime.now(timezone.utc).isoformat()

    for attempt in range(retries + 1):
        try:
            # Fetch content using requests or urllib standard library
            raw_content = b""
            if requests:
                resp = requests.get(
                    url,
                    timeout=timeout,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AI-News-Bot/1.0"}
                )
                resp.raise_for_status()
                raw_content = resp.content
            else:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AI-News-Bot/1.0"})
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    raw_content = response.read()

            # Parse with feedparser if available, else native XML fallback
            if feedparser:
                parsed = feedparser.parse(raw_content)
                items = []
                for entry in parsed.entries:
                    link = entry.get("link") or entry.get("id")
                    if not link or not link.startswith("http"):
                        continue
                    
                    title = entry.get("title", "").strip()
                    summary = entry.get("summary", "") or entry.get("description", "")
                    if summary:
                        summary = re.sub(r"<[^>]+>", " ", summary).strip()
                        summary = re.sub(r"\s+", " ", summary)[:500]

                    pub = entry.get("published") or entry.get("updated") or now_iso
                    items.append({
                        "url": link,
                        "source": name,
                        "source_type": source_type,
                        "weight": weight,
                        "title": title,
                        "summary": summary,
                        "content": "",
                        "image_url": "",
                        "published_at": pub,
                        "created_at": now_iso
                    })
                return items
            else:
                return _parse_xml_feed_fallback(raw_content.decode("utf-8", errors="ignore"), name, source_type, weight)

        except Exception as e:
            if attempt == retries:
                raise e
            time.sleep(1)
    return []

def insert_articles(con: sqlite3.Connection, rows: List[Dict[str, Any]]) -> int:
    inserted = 0
    with con:
        for r in rows:
            cur = con.execute("""
                INSERT OR IGNORE INTO articles 
                (url, source, source_type, title, summary, content, image_url, published_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                r["url"], r["source"], r["source_type"], r["title"], 
                r["summary"], r["content"], r["image_url"], r["published_at"], r["created_at"]
            ))
            if cur.rowcount > 0:
                inserted += 1
    return inserted

def recent(con: sqlite3.Connection, lookback_days: int = 7, max_articles: int = 250) -> List[Dict[str, Any]]:
    cur = con.cursor()
    cur.execute("""
        SELECT * FROM articles 
        ORDER BY created_at DESC 
        LIMIT ?
    """, (max_articles,))
    return [dict(row) for row in cur.fetchall()]

def local_prerank(articles: List[Dict[str, Any]], keywords: List[Dict[str, Any]], top_n: int = 45) -> List[Dict[str, Any]]:
    """Scores articles locally by title keywords, source authority, and freshness without calling LLM."""
    kw_map = {k["term"].lower(): k.get("weight", 1.0) for k in keywords}

    for art in articles:
        text = f"{art.get('title', '')} {art.get('summary', '')}".lower()
        score = 0.0

        # Match weighted keywords
        for kw, w in kw_map.items():
            if re.search(r"\b" + re.escape(kw) + r"\b", text):
                score += w * 12.0
            elif kw in text:
                score += w * 5.0

        # Source priority bonus
        if art.get("source_type") == "primary":
            score += 25.0

        # Title length and clarity bonus
        if 20 <= len(art.get("title", "")) <= 120:
            score += 8.0

        art["pre_score"] = round(score, 2)

    articles.sort(key=lambda x: x.get("pre_score", 0), reverse=True)
    return articles[:top_n]

def _tokenize(text: str) -> set[str]:
    words = re.findall(r"\b[a-zA-Z0-9_]{3,}\b", text.lower())
    stop_words = {"the", "and", "for", "with", "that", "this", "from", "are", "was", "will", "has", "have", "its", "news", "show", "today"}
    return {w for w in words if w not in stop_words}

def cluster_rows(candidates: List[Dict[str, Any]], threshold: float = 0.45) -> List[List[Dict[str, Any]]]:
    """Clusters articles that cover the exact same news story using Jaccard token overlap."""
    clusters: List[List[Dict[str, Any]]] = []
    
    for item in candidates:
        tokens = _tokenize(f"{item.get('title', '')} {item.get('summary', '')[:200]}")
        placed = False
        
        for cluster in clusters:
            rep = cluster[0]
            rep_tokens = _tokenize(f"{rep.get('title', '')} {rep.get('summary', '')[:200]}")
            
            intersection = len(tokens & rep_tokens)
            union = len(tokens | rep_tokens) or 1
            similarity = intersection / union
            
            if similarity >= threshold:
                cluster.append(item)
                placed = True
                break
                
        if not placed:
            clusters.append([item])
            
    return clusters

def cluster_stories(candidates: List[Dict[str, Any]], threshold: float = 0.45, max_clusters: Optional[int] = None) -> List[List[Dict[str, Any]]]:
    """Public entry point used by the pipeline runners.

    Wraps cluster_rows() and additionally ranks clusters (larger / more
    corroborated stories and higher pre-scores first) and trims the result
    to at most `max_clusters` groups.
    """
    clusters = cluster_rows(candidates, threshold=threshold)

    def _cluster_rank(cluster: List[Dict[str, Any]]) -> tuple:
        best_pre_score = max((c.get("pre_score", 0) for c in cluster), default=0)
        return (len(cluster), best_pre_score)

    clusters.sort(key=_cluster_rank, reverse=True)

    if max_clusters is not None:
        clusters = clusters[:max_clusters]

    return clusters

def extract(url: str, timeout: int = 12, max_chars: int = 4000) -> str:
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
            if text:
                return text[:max_chars].strip()
    except Exception:
        pass
    return ""

def og_image(url: str, timeout: int = 8) -> str:
    try:
        resp = requests.get(
            url, 
            timeout=timeout, 
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        if resp.ok:
            soup = BeautifulSoup(resp.content, "html.parser")
            og = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
            if og and og.get("content"):
                return urllib.parse.urljoin(url, og["content"])
    except Exception:
        pass
    return ""

def save_state(con: sqlite3.Connection, rows: List[Dict[str, Any]]) -> None:
    with con:
        for r in rows:
            con.execute("""
                UPDATE articles 
                SET cluster_id = ?, content = ?, image_url = ?, pre_score = ?
                WHERE url = ?
            """, (r.get("cluster_id", 0), r.get("content", ""), r.get("image_url", ""), r.get("pre_score", 0), r["url"]))

def update_scores(con: sqlite3.Connection, scored_clusters: List[Dict[str, Any]]) -> None:
    with con:
        for sc in scored_clusters:
            rep_url = sc.get("url")
            if rep_url:
                con.execute("""
                    UPDATE articles 
                    SET importance_score = ?, final_score = ?, status = 'scored'
                    WHERE url = ?
                """, (sc.get("score", 0), sc.get("_score", sc.get("score", 0)), rep_url))

def combined_score(article: Dict[str, Any]) -> float:
    base = float(article.get("score", 70))
    src_bonus = 15.0 if article.get("source_type") == "primary" else 0.0
    cluster_bonus = min(10.0, (article.get("source_count", 1) - 1) * 4.0)
    return round(base + src_bonus + cluster_bonus, 2)
