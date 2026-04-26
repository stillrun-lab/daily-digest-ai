"""
Daily-digest-ai — aggregates RSS feeds and webpages, summarizes via Claude,
delivers the brief to Telegram and Discord.

Designed for once-daily cron. Anthropic prompt caching is wired in via
cache_control so the system prompt stays cached if the cadence increases
(hourly/twice-daily). At daily cadence the cache is cold each run, but the
pattern is correct.
"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import requests
import yaml
from anthropic import Anthropic
from bs4 import BeautifulSoup

BASE = Path(__file__).parent
SOURCES_FILE = BASE / "sources.yaml"

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT = os.getenv("TELEGRAM_CHAT_ID")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")

USER_AGENT = (
    "Mozilla/5.0 (compatible; DailyDigest/1.0; "
    "+https://github.com/stillrun-lab/daily-digest-ai)"
)

DEFAULT_SYSTEM_PROMPT = (
    "You are a sharp executive analyst preparing a daily brief. "
    "Format as: 2-3 sentence overview, 5-8 bullets cited by source, "
    "and a short 'what to watch' section. Be direct. Skip filler."
)

MODEL = "claude-sonnet-4-5"


def load_config() -> dict:
    with SOURCES_FILE.open() as f:
        return yaml.safe_load(f) or {}


def fetch_rss(url: str, max_items: int = 10) -> list[dict]:
    feed = feedparser.parse(url)
    items = []
    for entry in feed.entries[:max_items]:
        items.append({
            "title": entry.get("title", ""),
            "summary": (entry.get("summary", "") or
                        entry.get("description", ""))[:300],
            "link": entry.get("link", ""),
        })
    return items


def fetch_page(url: str, selector: str | None = None,
               max_chars: int = 3000) -> str:
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    if selector:
        elements = soup.select(selector)
        text = "\n".join(el.get_text(" ", strip=True) for el in elements)
    else:
        text = soup.get_text(" ", strip=True)
    text = " ".join(text.split())
    return text[:max_chars]


def gather_content(config: dict) -> str:
    parts = []

    for feed in (config.get("rss") or []):
        name = feed.get("name", feed["url"])
        try:
            items = fetch_rss(feed["url"], feed.get("max_items", 10))
            parts.append(f"## {name} (RSS)\n")
            for item in items:
                parts.append(f"- **{item['title']}**: {item['summary']}")
            parts.append("")
        except Exception as e:
            print(f"  ! {name}: rss fetch failed ({e})", file=sys.stderr)

    for page in (config.get("pages") or []):
        name = page.get("name", page["url"])
        try:
            content = fetch_page(page["url"], page.get("selector"))
            parts.append(f"## {name} (page)\n{content}\n")
        except Exception as e:
            print(f"  ! {name}: page fetch failed ({e})", file=sys.stderr)

    return "\n".join(parts)


def summarize(content: str, system_prompt: str) -> str:
    """Call Claude with cache_control on the system prompt."""
    client = Anthropic(api_key=ANTHROPIC_KEY)

    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{
            "role": "user",
            "content": (
                f"Today's aggregated content:\n\n{content}\n\n"
                "Write the daily brief now."
            ),
        }],
    )

    # Log token usage for cost visibility
    usage = response.usage
    print(f"  • tokens: in={usage.input_tokens} out={usage.output_tokens}",
          file=sys.stderr)
    if hasattr(usage, "cache_read_input_tokens"):
        print(f"    cache_read={usage.cache_read_input_tokens} "
              f"cache_create={usage.cache_creation_input_tokens}",
              file=sys.stderr)

    return response.content[0].text


def send_telegram(msg: str) -> None:
    if not (TELEGRAM_TOKEN and TELEGRAM_CHAT):
        return
    msg = msg[:4000]   # Telegram caps at 4096
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={
                "chat_id": TELEGRAM_CHAT,
                "text": msg,
                "disable_web_page_preview": "true",
            },
            timeout=15,
        )
    except Exception as e:
        print(f"  ! telegram failed: {e}", file=sys.stderr)


def send_discord(msg: str) -> None:
    if not DISCORD_WEBHOOK:
        return
    msg = msg[:1900]   # Discord caps at 2000
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg}, timeout=15)
    except Exception as e:
        print(f"  ! discord failed: {e}", file=sys.stderr)


def main() -> int:
    if not ANTHROPIC_KEY:
        print("ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 1

    config = load_config()
    digest_cfg = config.get("digest") or {}
    title = digest_cfg.get("title", "Daily Brief")
    system_prompt = digest_cfg.get("system_prompt") or DEFAULT_SYSTEM_PROMPT

    now = datetime.now(timezone.utc)
    print(f"[{now.isoformat()}] Daily-digest-ai — gathering sources")

    content = gather_content(config)
    if not content.strip():
        print("No content gathered — skipping summary", file=sys.stderr)
        return 0

    print(f"  • gathered {len(content)} chars")
    print(f"  • summarizing with {MODEL}...")

    try:
        summary = summarize(content, system_prompt)
    except Exception as e:
        print(f"  ! Claude failed: {e}", file=sys.stderr)
        return 1

    header = f"📰 {title} — {now.strftime('%a %b %d')}\n\n"
    full_msg = header + summary

    print(full_msg)
    send_telegram(full_msg)
    send_discord(full_msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
