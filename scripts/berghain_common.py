#!/usr/bin/env python3
"""Shared Berghain-digest logic for the daily and weekly cron push scripts.

Two entry scripts import this and call run(mode):
  berghain-daily.py  -> run("daily")   fires every day  (0 9 * * *)
  berghain-weekly.py -> run("weekly")  fires once a week (0 9 * * 1)

daily  : 🔥 Hot today (top/day) + 🆕 New since last run (deduped via seen-file).
weekly : 🔥 Hot this week (top/week) — a weekly roundup, no dedup.

No-agent cron push: prints a Telegram-ready message (clickable markdown-link
titles; the adapter converts markdown -> MarkdownV2). Empty stdout => silent.
Reddit's JSON API is blocked for anonymous clients (403); the .rss endpoint
returns 200, so we use RSS/Atom. Reddit rate-limits hard (~1 req/window), so
feeds are spaced and retried on HTTP 429.
"""
import json
import os
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36")
# Only the Berghain subreddit family. The old global q=berghain search pulled in
# unrelated subs (r/harrystyles, r/BerlinNightlife, r/SearchEnginePodcast, …), so
# it's gone — both Hot and New now come from these subs only.
SUBREDDITS = ["Berghain", "Berghain_Community"]
NEW_URL = "https://www.reddit.com/r/{sub}/new/.rss?limit=25"
HOT_URL = "https://www.reddit.com/r/{sub}/top/.rss?t={window}&limit=15"

MAX_AGE_HOURS = 26          # recency window for the NEW section
TITLE_MAX = 90              # truncate long titles
GAP_SECONDS = 35            # spacing between feeds — Reddit allows ~1 req/window
RETRY_429 = 2               # retries when a feed returns HTTP 429
RETRY_BACKOFF = 40          # seconds to wait before a 429 retry
STATE_FILE = os.path.expanduser("~/.hermes/state/berghain_reddit_seen.json")
NS = {"a": "http://www.w3.org/2005/Atom"}


def load_seen():
    try:
        with open(STATE_FILE) as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_seen(seen):
    ids = list(seen)[-2000:]
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(ids, f)


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return resp.read()


def _parse(raw):
    root = ET.fromstring(raw)
    out = []
    for e in root.findall("a:entry", NS):
        eid = (e.findtext("a:id", default="", namespaces=NS) or "").strip()
        title = (e.findtext("a:title", default="", namespaces=NS) or "").strip()
        updated = (e.findtext("a:updated", default="", namespaces=NS) or "").strip()
        link_el = e.find("a:link", NS)
        link = link_el.get("href") if link_el is not None else ""
        author = (e.findtext("a:author/a:name", default="", namespaces=NS) or "").strip()
        out.append({"id": eid, "title": title, "updated": updated,
                    "link": link, "author": author})
    return out


def fetch_feed(name, url, errors, gap=False):
    """Fetch+parse one feed; retry on HTTP 429; on error note it and return []."""
    if gap:
        time.sleep(GAP_SECONDS)
    for attempt in range(RETRY_429 + 1):
        try:
            return _parse(_fetch(url))
        except urllib.error.HTTPError as ex:
            if ex.code == 429 and attempt < RETRY_429:
                time.sleep(RETRY_BACKOFF)
                continue
            errors.append(f"{name}: HTTP {ex.code}")
            return []
        except Exception as ex:
            errors.append(f"{name}: {type(ex).__name__}")
            return []
    return []


def is_recent(updated, hours):
    if not updated:
        return True
    try:
        dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0
        return age <= hours
    except Exception:
        return True


def clip(title):
    title = " ".join(title.split())
    title = title.replace("[", "(").replace("]", ")")   # keep [text](url) intact
    return title if len(title) <= TITLE_MAX else title[:TITLE_MAX - 1].rstrip() + "…"


def line(it, prefix):
    """One clickable line: '<prefix> [title](url)'. Author/sub/time are omitted to
    keep the single-subreddit-family digest clean."""
    return f"{prefix} [{clip(it['title'])}]({it['link']})"


def _merge_round_robin(per_sub, limit):
    """Interleave each subreddit's top list so neither sub dominates the Hot
    section. RSS carries no score, so cross-sub ranking isn't possible — this at
    least keeps both subs represented instead of front-loading the first one."""
    out, i = [], 0
    while len(out) < limit and any(i < len(lst) for lst in per_sub):
        for lst in per_sub:
            if i < len(lst):
                out.append(lst[i])
                if len(out) >= limit:
                    break
        i += 1
    return out


def _fetch_hot(window, limit, max_age_h, errors, calls):
    per_sub, links = [], set()
    for sub in SUBREDDITS:
        gap = calls[0] > 0
        calls[0] += 1
        picks = []
        for it in fetch_feed(f"r/{sub} (hot)",
                             HOT_URL.format(sub=sub, window=window),
                             errors=errors, gap=gap):
            if not it["link"] or it["link"] in links:
                continue
            if not is_recent(it["updated"], max_age_h):
                continue
            links.add(it["link"])
            picks.append(it)
        per_sub.append(picks)
    return _merge_round_robin(per_sub, limit), links


def header(mode):
    # 🏛 + date + hashtags so the digests are easy to find via Telegram search
    # (e.g. search "#berghain", "#weekly", or "26 Aug").
    today = datetime.now().strftime("%-d %b")
    if mode == "weekly":
        return [f"\U0001F3DB Berghain on Reddit · неделя · {today}",
                "#berghain #weekly", ""]
    return [f"\U0001F3DB Berghain on Reddit · {today}", "#berghain #daily", ""]


def run(mode):
    errors = []
    calls = [0]   # network-call counter for gentle inter-feed spacing

    if mode == "weekly":
        # Weekly roundup: top of the week only, no dedup (does not touch seen).
        hot, _ = _fetch_hot("week", 10, 24 * 10, errors, calls)
        if not hot:
            return   # silent
        lines = header("weekly") + ["\U0001F525 Hot this week"]
        for i, it in enumerate(hot, 1):
            lines.append(line(it, f"{i}."))
        print("\n".join(lines).rstrip())
        return

    # --- daily -------------------------------------------------------------
    seen = load_seen()
    hot, hot_links = _fetch_hot("day", 5, 24 * 2, errors, calls)

    new_items = []
    for sub in SUBREDDITS:
        gap = calls[0] > 0
        calls[0] += 1
        for it in fetch_feed(f"r/{sub} (new)", NEW_URL.format(sub=sub),
                             errors=errors, gap=gap):
            if not it["id"] or it["id"] in seen:
                continue
            seen.add(it["id"])                          # mark seen even if filtered
            if not is_recent(it["updated"], MAX_AGE_HOURS):
                continue
            if it["link"] in hot_links:                 # already shown as hot
                continue
            new_items.append(it)
    save_seen(seen)

    if not hot and not new_items:
        return   # silent tick — nothing to say

    lines = header("daily")
    if hot:
        lines.append("\U0001F525 Hot today")
        for i, it in enumerate(hot, 1):
            lines.append(line(it, f"{i}."))
        lines.append("")
    if new_items:
        lines.append(f"\U0001F195 New ({len(new_items)})")
        for it in new_items:
            lines.append(line(it, "•"))
    print("\n".join(lines).rstrip())
