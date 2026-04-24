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
TELEGRAM_CHANNEL = os.environ["TELEGRAM_CHANNEL"]
ANTHROPIC_KEY    = os.environ["ANTHROPIC_API_KEY"]
UNSPLASH_KEY     = os.environ.get("UNSPLASH_ACCESS_KEY", "")
PEXELS_KEY       = os.environ.get("PEXELS_API_KEY", "")
POSTED_FILE      = "posted_ids.json"

# POST_TYPE is set by the workflow: "mood" or "news"
POST_TYPE = os.environ.get("POST_TYPE", "news")

# MOOD_SLOT gives context to mood posts: morning / afternoon / evening
MOOD_SLOT = os.environ.get("MOOD_SLOT", "morning")

# ── RSS Sources ───────────────────────────────────────────────────────────────
RSS_FEEDS = [
    {"name": "Sprudge",             "url": "https://sprudge.com/feed"},
    {"name": "Daily Coffee News",   "url": "https://dailycoffeenews.com/feed/"},
    {"name": "Perfect Daily Grind", "url": "https://perfectdailygrind.com/feed/"},
    {"name": "Barista Magazine",    "url": "https://www.baristamagazine.com/feed/"},
]

# ── Photo search queries by mood slot ─────────────────────────────────────────
PHOTO_QUERIES_BY_SLOT = {
    "morning": [
        "coffee morning sunlight window",
        "cozy coffee cup morning",
        "coffee sunrise golden hour",
        "espresso morning kitchen",
        "coffee book morning routine",
    ],
    "afternoon": [
        "coffee shop afternoon light",
        "iced coffee summer café",
        "latte art coffee table",
        "specialty coffee flat lay",
        "coffee friends café afternoon",
    ],
    "evening": [
        "coffee candle cozy evening",
        "coffee night warm light",
        "cappuccino evening café",
        "cozy coffee blanket autumn",
        "coffee dessert evening",
    ],
}

PHOTO_QUERIES_NEWS = [
    "specialty coffee barista",
    "coffee beans roasting",
    "pour over coffee",
    "espresso machine",
    "coffee shop interior",
    "latte art close up",
    "coffee cupping tasting",
]

# ── Mood post prompts by slot ─────────────────────────────────────────────────
MOOD_PROMPTS = {
    "morning": [
        "Write a warm, uplifting morning greeting for a specialty coffee Telegram channel. Ask followers how they're brewing their morning coffee today (e.g. espresso, pour over, French press?) and invite them to share. Cosy, friendly tone. Max 200 characters. Start with ☀️ or ☕ emoji. No hashtags.",
        "Write a gentle good morning post for a coffee lovers' Telegram channel. Include a short, poetic one-liner about the first sip of the day, then ask: 'What's in your cup this morning?' Max 200 characters. Start with 🌅 or ☕. No hashtags.",
        "Write a cheerful morning coffee post. Ask followers what their go-to morning coffee ritual is — do they grind fresh beans, have a favourite café, or have a secret recipe? Keep it conversational and warm. Max 200 characters. Start with ☕. No hashtags.",
    ],
    "afternoon": [
        "Write a mid-day coffee post for a Telegram coffee channel. It's the afternoon slump — ask followers if they're reaching for a second cup, and what they choose: espresso, cold brew, or something else? Light and fun tone. Max 200 characters. Start with ☕ or 🧊. No hashtags.",
        "Write a cosy afternoon post for coffee lovers. Share a quick tip about afternoon coffee (e.g. why a cortado beats a large latte at 3pm) and ask if they agree. Max 200 characters. Start with 🫗 or ☕. No hashtags.",
    ],
    "evening": [
        "Write a warm, winding-down evening post for a coffee Telegram channel. Ask followers if they allow themselves an evening coffee or switch to decaf/herbal — no judgment! Cosy and conversational. Max 200 characters. Start with 🌙 or ☕. No hashtags.",
        "Write a reflective evening post for coffee lovers. Something like: today's best moment was probably that first sip. Ask followers to share the highlight of their coffee day. Warm, poetic tone. Max 200 characters. Start with 🕯️ or 🌙. No hashtags.",
    ],
}

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
    articles = []
    for feed in RSS_FEEDS:
        try:
            parsed = feedparser.parse(feed["url"])
            for entry in parsed.entries[:10]:
                articles.append({
                    "id":      hashlib.md5(entry.get("link", "").encode()).hexdigest(),
                    "source":  feed["name"],
                    "title":   entry.get("title", ""),
                    "link":    entry.get("link", ""),
                    "summary": entry.get("summary", entry.get("description", "")),
                })
        except Exception as e:
            print(f"[WARN] Feed error {feed['name']}: {e}")
    return articles


def pick_fresh_article(articles: list[dict], posted: set) -> dict | None:
    fresh = [a for a in articles if a["id"] not in posted]
    return random.choice(fresh) if fresh else None


def fetch_photo_url(query: str) -> str | None:
    """Try Unsplash first, fall back to Pexels."""
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


def ai_write_news_post(article: dict) -> str:
    prompt = f"""You are a warm, knowledgeable editor for a specialty coffee Telegram channel.
Write an engaging, concise Telegram post (max 280 characters, NOT counting the link) based on this article.

Rules:
- Friendly, enthusiastic tone — coffee lovers audience
- Start with a relevant emoji (☕ 🫘 🍵 🔥 etc.)
- Highlight the key insight or hook in plain language
- End with the source in parentheses, e.g. (Sprudge)
- Do NOT include the URL — appended separately
- No hashtags

Article title: {article['title']}
Source: {article['source']}
Summary: {article['summary'][:600]}
"""
    msg = Anthropic(api_key=ANTHROPIC_KEY).messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


def ai_write_mood_post(slot: str) -> str:
    prompt = random.choice(MOOD_PROMPTS[slot])
    msg = Anthropic(api_key=ANTHROPIC_KEY).messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


def send_telegram_photo(text: str, photo_url: str | None, link: str | None = None):
    base    = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
    caption = text
    if link:
        caption += f"\n\n🔗 {link}"

    if photo_url:
        r = requests.post(f"{base}/sendPhoto", json={
            "chat_id":    TELEGRAM_CHANNEL,
            "photo":      photo_url,
            "caption":    caption,
            "parse_mode": "HTML",
        }, timeout=15)
    else:
        r = requests.post(f"{base}/sendMessage", json={
            "chat_id":                  TELEGRAM_CHANNEL,
            "text":                     caption,
            "parse_mode":               "HTML",
            "disable_web_page_preview": False,
        }, timeout=15)

    r.raise_for_status()
    print(f"[OK] Telegram message_id={r.json()['result']['message_id']}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    now = datetime.now(timezone.utc).isoformat()
    print(f"[{now}] Coffee Bot — type={POST_TYPE} slot={MOOD_SLOT}")

    posted = load_posted()

    if POST_TYPE == "mood":
        print(f"[INFO] Writing {MOOD_SLOT} mood post…")
        text      = ai_write_mood_post(MOOD_SLOT)
        query     = random.choice(PHOTO_QUERIES_BY_SLOT[MOOD_SLOT])
        photo_url = fetch_photo_url(query)
        send_telegram_photo(text, photo_url, link=None)

    else:
        articles = fetch_articles()
        article  = pick_fresh_article(articles, posted)

        if not article:
            print("[INFO] No fresh articles — skipping.")
            return

        print(f"[INFO] Writing news post: {article['title'][:60]}…")
        text      = ai_write_news_post(article)
        query     = random.choice(PHOTO_QUERIES_NEWS)
        photo_url = fetch_photo_url(query)
        send_telegram_photo(text, photo_url, link=article["link"])
        posted.add(article["id"])
        save_posted(posted)

    print("[DONE]")


if __name__ == "__main__":
    main()
