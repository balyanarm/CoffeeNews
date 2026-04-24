# ☕ Coffee Bot — Telegram Channel Automation

Automatically posts **2–3 AI-written specialty coffee news updates per day** to your Telegram channel, with cosy photos from Unsplash/Pexels. Runs entirely on **GitHub Actions** — no server needed, completely free.

---

## How It Works

```
GitHub Actions (cron: 3×/day)
       │
       ├─ Fetches RSS from Sprudge, Daily Coffee News,
       │  Perfect Daily Grind, Barista Magazine
       │
       ├─ Claude AI rewrites into engaging Telegram post
       │
       ├─ Fetches cosy coffee photo (Unsplash → Pexels)
       │
       └─ Sends photo + caption + link to your channel
```

---

## Setup Guide

### Step 1 — Create a Telegram Bot

1. Open Telegram, search for **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy your **Bot Token** (looks like `7123456789:AAFxxx...`)

### Step 2 — Create & Prepare Your Channel

1. Create a new Telegram channel (public or private)
2. Add your bot as an **Administrator** with "Post Messages" permission
3. Note your channel username (e.g. `@mycoffeeChannel`) or numeric ID

### Step 3 — Get API Keys

| Service | Where to get it | Required? |
|---------|----------------|-----------|
| **Anthropic** | https://console.anthropic.com/keys | ✅ Yes |
| **Unsplash** | https://unsplash.com/developers → New Application | ✅ Recommended |
| **Pexels** | https://www.pexels.com/api/ → Your API Key | ✅ Recommended |

> You need at least one photo API (Unsplash or Pexels). Both is best — Unsplash is tried first, Pexels is the fallback.

### Step 4 — Create GitHub Repository

1. Go to https://github.com/new
2. Create a **private** repo (e.g. `coffee-bot`)
3. Upload all files from this project, keeping the folder structure:

```
coffee-bot/
├── .github/
│   └── workflows/
│       └── coffee_bot.yml
├── src/
│   └── bot.py
├── requirements.txt
└── README.md
```

### Step 5 — Add Secrets to GitHub

Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these secrets one by one:

| Secret Name | Value |
|-------------|-------|
| `TELEGRAM_TOKEN` | Your bot token from BotFather |
| `TELEGRAM_CHANNEL` | e.g. `@mycoffeeChannel` or `-100123456789` |
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `UNSPLASH_ACCESS_KEY` | Your Unsplash Access Key |
| `PEXELS_API_KEY` | Your Pexels API key |

### Step 6 — Test It!

1. Go to **Actions** tab in your GitHub repo
2. Click **☕ Coffee Bot** → **Run workflow** → **Run workflow**
3. Watch the logs — a post should appear in your channel within ~30 seconds ☕

---

## Posting Schedule

The bot posts **3 times per day** by default:

| Time (UTC) | Local (CET/Berlin) |
|------------|-------------------|
| 08:00 UTC  | 10:00 AM          |
| 13:00 UTC  | 3:00 PM           |
| 18:00 UTC  | 8:00 PM           |

To change the schedule, edit `.github/workflows/coffee_bot.yml` and adjust the `cron` lines.

---

## Customization

**Change posting times** — edit the `cron:` lines in `coffee_bot.yml`  
**Post more per run** — change `POSTS_PER_RUN: "1"` to `"2"` in the workflow  
**Add more photo moods** — edit the `PHOTO_QUERIES` list in `src/bot.py`  
**Change AI tone** — edit the `prompt` string in the `ai_write_post()` function  

---

## Cost Estimate (monthly)

| Service | Cost |
|---------|------|
| GitHub Actions | Free (2,000 min/month free tier) |
| Anthropic API (90 posts × ~300 tokens) | ~$0.05 |
| Unsplash / Pexels | Free |
| **Total** | **~$0.05/month** |

---

## Troubleshooting

**Bot doesn't post** — Make sure the bot is an Admin in the channel with "Post Messages" enabled.  
**No photos** — Check your Unsplash/Pexels API keys in GitHub Secrets.  
**Same articles reposted** — The `posted_ids.json` cache tracks what's been posted; it persists via GitHub Actions cache.  
**Workflow doesn't trigger** — GitHub may disable scheduled workflows on inactive repos; just push a small commit to reactivate.
