# Daily-digest-ai

AI-summarized daily brief from any RSS feeds and webpages. Configure your
sources in YAML, set a system prompt to define the brief's voice, and get
a Claude-generated summary delivered to Telegram and Discord on whatever
schedule you choose.
<p align="center">
  <img src="docs/discord run.png" width="400" alt="Daily brief delivered to Discord">
</p>
## What it does

Pulls content from RSS feeds and webpages listed in `sources.yaml`,
concatenates it, and sends it to Claude with a configurable system prompt.
The model returns a structured summary (overview + bullet points + forward
look) that gets pushed to your notification channels.

```yaml
# Example sources.yaml
rss:
  - name: "Hacker News"
    url: "https://hnrss.org/frontpage"
    max_items: 10

pages:
  - name: "GitHub Trending Python"
    url: "https://github.com/trending/python"
    selector: "article.Box-row"

digest:
  title: "Morning Brief"
  system_prompt: |
    You are a sharp executive analyst. Format the output as:
    1. 2-3 sentence overview of today's themes
    2. 5-8 bullets of the most important items
    3. "What to watch" — 2-3 forward-looking notes
```

## Use cases

- Morning brief for founders / operators / busy execs
- Daily distilled news for traders (custom RSS list)
- Weekly digest of GitHub repo activity
- Industry intelligence summary for sales teams
- Any "summarize my world" workflow

## Architecture

```
┌──────────────────────┐
│ GitHub Actions cron  │   daily at 7am ET (configurable)
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐    ┌────────────────┐
│ digest.py            │───►│ feedparser     │
│  • load sources.yaml │    │ requests + bs4 │
│  • gather all sources│    └────────────────┘
│  • call Claude API   │    ┌────────────────┐
│  • format brief      │───►│ Anthropic API  │
│  • send notifications│    │ (Claude Sonnet)│
└──────────┬───────────┘    └────────────────┘
           │
   ┌───────┴────────┐
   ▼                ▼
Telegram        Discord
```

## Features

- Multi-source aggregation (RSS feeds + scraped webpages)
- Tunable system prompt — change voice, format, or focus per use case
- Anthropic prompt caching enabled (free if cadence stays daily; saves
  ~90% on system prompt tokens at higher frequencies)
- Telegram + Discord delivery (independent, use either or both)
- Token-aware truncation so messages fit channel limits
- Adjustable cadence via standard cron syntax
- Roughly $0.55/month at daily cadence

## Quick start

1. Fork or clone this repo
2. Edit `sources.yaml` with your RSS feeds, pages, and system prompt
3. Set repo secrets:
   - `ANTHROPIC_API_KEY` — from [console.anthropic.com](https://console.anthropic.com)
   - `TELEGRAM_BOT_TOKEN` — from [@BotFather](https://t.me/BotFather)
   - `TELEGRAM_CHAT_ID` — your chat ID
   - `DISCORD_WEBHOOK_URL` — optional
4. Commit and push. The workflow runs every morning at 7am ET.

## Configuration

`sources.yaml` accepts three top-level keys:

| Key       | Type            | Notes                                              |
|-----------|-----------------|----------------------------------------------------|
| `rss`     | list of feeds   | Each: `name`, `url`, optional `max_items`          |
| `pages`   | list of pages   | Each: `name`, `url`, optional `selector`           |
| `digest`  | object          | `title`, `system_prompt`                           |

The system prompt is the full lever for output quality. Tune it for tone,
format, length, and focus.

## Cost

At daily cadence:
- Input: ~3,000 tokens (aggregated content)
- Output: ~500 tokens (summary)
- Per run: ~$0.018
- Per month: ~$0.55

Anthropic prompt caching is wired in via `cache_control` so the system
prompt stays cached if you run more frequently than once per 5 minutes.
Daily runs don't benefit from the cache (cold each time), but the pattern
is in place for higher-cadence use.

## Custom builds

Need this extended — multi-recipient routing, persistent threading, custom
post-processing, integration with internal tools, or a different LLM
provider? I build production AI workflows for traders, operators, and
businesses.

**Built by [Stillrun Lab](https://github.com/stillrun-lab)** — automation systems built to run themselves.

- 💼 Hire me on Upwork: *(link coming soon)*
- 🐦 [@trade_4l on X](https://x.com/trade_4l)
- 📧 *(email coming soon)*
