import os
import json
import random
import hashlib
import requests
import feedparser
from datetime import datetime, timezone
from anthropic import Anthropic

# ── Config ────────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHANNEL = os.environ["TELEGRAM_CHANNEL"]   # e.g. @mycoffeechannel
ANTHROPIC_KEY    = os.environ["ANTHROPIC_API_KEY"]
UNSPLASH_KEY     = os.environ.get("UNSPLASH_ACCESS_KEY", "")
PEXELS_KEY       = os.environ.get("PEXELS_API_KEY", "")
POSTED_FILE      = "posted_ids.json"                # kept as GitHub artifact

POSTS_PER_RUN    = int(os.environ.get("POSTS_PER_RUN", "1"))  # 1 post per run; run 2-3x/day via cron

# ── RSS Sources ───────────────────────────────────────────────────────────────
RSS_FEEDS = [
    {"name": "Sprudge",            "url": "https://sprudge.com/feed"},
    {"name": "Daily Coffee News",  "url": "https://dailycoffeenews.com/feed/"},
    {"name": "Perfect Daily Grind","url": "https://perfectdailygrind.com/feed/"},
    {"name": "Barista Magazine",   "url": "https://www.baristamagazine.com/feed/"},
]

# ── Photo Queries ─────────────────────────────────────────────────────────────
PHOTO_QUERIES = [
    "specialty coffee", "coffee latte art", "coffee shop cozy",
    "espresso bar", "coffee beans roasting", "barista making coffee",
    "coffee morning light", "coffee cup aesthetic", "pour over coffee",
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_posted() -> set:
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE) as f:
            return set(json.load(f))
    return set()


def save_posted(ids: set):
    with open(POSTED_FILE, "w") as f:
        json.dump(list(ids), f)


def fetch_articles() -> list[dict]:
    """Fetch fresh articles from all RSS feeds."""
    articles = []
    for feed in RSS_FEEDS:
        try:
            parsed = feedparser.parse(feed["url"])
            for entry in parsed.entries[:10]:
                articles.append({
                    "id":      hashlib.md5(entry.get("link","").encode()).hexdigest(),
                    "source":  feed["name"],
                    "title":   entry.get("title", ""),
                    "link":    entry.get("link", ""),
                    "summary": entry.get("summary", entry.get("description", "")),
                })
        except Exception as e:
            print(f"[WARN] Feed error {feed['name']}: {e}")
    return articles


def pick_new_articles(articles: list[dict], posted: set, n: int) -> list[dict]:
    fresh = [a for a in articles if a["id"] not in posted]
    random.shuffle(fresh)
    return fresh[:n]


def ai_write_post(article: dict) -> str:
    """Ask Claude to write an engaging Telegram post from the article."""
    client = Anthropic(api_key=ANTHROPIC_KEY)
    prompt = f"""You are a warm, knowledgeable editor for a specialty coffee Telegram channel.
Write an engaging, concise Telegram post (max 280 characters of text, NOT counting the link) based on this article.

Rules:
- Friendly, enthusiastic tone — coffee lovers audience
- Start with a relevant emoji (☕ 🫘 🍵 ☀️ etc.)
- Mention the key insight or hook in plain language
- End with the source name in parentheses, e.g. (Perfect Daily Grind)
- Do NOT include the URL — it will be appended separately
- No hashtags

Article title: {article['title']}
Source: {article['source']}
Summary: {article['summary'][:600]}
"""
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


def fetch_photo_url(query: str) -> str | None:
    """Try Unsplash first, fall back to Pexels."""
    # Unsplash
    if UNSPLASH_KEY:
        try:
            r = requests.get(
                "https://api.unsplash.com/photos/random",
                params={"query": query, "orientation": "landscape", "content_filter": "high"},
                headers={"Authorization": f"Client-ID {UNSPLASH_KEY}"},
                timeout=10,
            )
            if r.status_code == 200:
                return r.json()["urls"]["regular"]
        except Exception as e:
            print(f"[WARN] Unsplash error: {e}")

    # Pexels fallback
    if PEXELS_KEY:
        try:
            r = requests.get(
                "https://api.pexels.com/v1/search",
                params={"query": query, "per_page": 15, "orientation": "landscape"},
                headers={"Authorization": PEXELS_KEY},
                timeout=10,
            )
            if r.status_code == 200:
                photos = r.json().get("photos", [])
                if photos:
                    return random.choice(photos)["src"]["large"]
        except Exception as e:
            print(f"[WARN] Pexels error: {e}")

    return None


def send_telegram(text: str, photo_url: str | None, link: str):
    """Send photo+caption or plain text message to the channel."""
    base = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
    caption = f"{text}\n\n🔗 {link}"

    if photo_url:
        r = requests.post(f"{base}/sendPhoto", json={
            "chat_id":    TELEGRAM_CHANNEL,
            "photo":      photo_url,
            "caption":    caption,
            "parse_mode": "HTML",
        }, timeout=15)
    else:
        r = requests.post(f"{base}/sendMessage", json={
            "chat_id":    TELEGRAM_CHANNEL,
            "text":       caption,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }, timeout=15)

    r.raise_for_status()
    print(f"[OK] Posted: {r.json()['result']['message_id']}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Coffee Bot starting — {POSTS_PER_RUN} post(s) this run")

    posted   = load_posted()
    articles = fetch_articles()
    picks    = pick_new_articles(articles, posted, POSTS_PER_RUN)

    if not picks:
        print("[INFO] No new articles found — skipping run.")
        return

    for article in picks:
        print(f"[INFO] Processing: {article['title'][:60]}…")
        try:
            post_text = ai_write_post(article)
            query     = random.choice(PHOTO_QUERIES)
            photo_url = fetch_photo_url(query)
            send_telegram(post_text, photo_url, article["link"])
            posted.add(article["id"])
        except Exception as e:
            print(f"[ERROR] Failed to post article: {e}")

    save_posted(posted)
    print("[DONE] Run complete.")


if __name__ == "__main__":
    main()
