# bh-10243-bot

[![ci](https://github.com/Tuch/bh-10243-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/Tuch/bh-10243-bot/actions/workflows/ci.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A tiny, self-contained **Telegram push-bot** that delivers a Berghain digest from
public Reddit RSS feeds — no LLM, no API keys, no always-on process required.
It runs as a dedicated [Hermes](https://hermes-agent.nousresearch.com) profile.

Two scheduled jobs deliver to the bot:

| Job | Schedule | Content |
|-----|----------|---------|
| `bh_daily`  | every day, 09:00       | 🔥 **Hot today** (top of the last 24h) + 🆕 **New** (since yesterday) |
| `bh_weekly` | Mondays, 09:00         | 🔥 **Hot this week** (top of the last 7 days) |

Titles are clickable markdown links (raw URLs hidden), link previews are
suppressed, and a run with nothing new stays silent (no message).

## Example message

The daily job delivers something like this (titles are clickable links; the raw
URLs stay hidden, and Telegram's link previews are suppressed):

```
Berghain on Reddit

🔥 Hot today
• The new bouncers of Berghain
  r/Berghain_Community · u/MainCard3207
• Door nerves despite going many times
  r/berghain · u/90smikemc

🆕 New (3)
• Saule Ticket Refund
  r/berghain · u/Many_Resource_3744
• Klubnacht 15/16 August — queue live updates
  r/Berghain_Community · u/BerghAnon
• Berghain-like scenes in Los Angeles County?
  r/AskLosAngeles · u/meihoneysk
```

Nothing new since the last run → no message is sent.

## How it works

- **Source:** Reddit's public `.rss` feeds (the JSON API is blocked for anonymous
  clients; RSS returns 200). Global search for `berghain` + `r/Berghain`.
- **No LLM:** the cron jobs run in `--no-agent` mode — the script's stdout *is*
  the message. Zero tokens, works even with no model configured.
- **Dedup:** the daily job records shown post IDs in
  `~/.hermes/state/berghain_reddit_seen.json` so mornings only surface new posts.
- **Rate-limit safe:** feeds are spaced (35s) and retried on HTTP 429 — Reddit
  throttles hard, so a run can take a couple of minutes (fine for a daily cron).

## Files

```
config.yaml                     # profile config: no cron header, no link previews
scripts/berghain_common.py      # shared fetch/render logic
scripts/berghain-daily.py       # entry: run("daily")
scripts/berghain-weekly.py      # entry: run("weekly")
launchd/…plist.template         # macOS timer for the no-gateway setup
.env.example                    # bot token + chat id (fill in, never commit)
setup.sh                        # one-command install into a Hermes profile
```

## Quick start

```bash
git clone git@github.com:Tuch/bh-10243-bot.git
cd bh-10243-bot
./setup.sh                      # creates the 'berghain' profile, installs files
# edit the printed .env path with your @BotFather token + chat id, then:
./setup.sh                      # re-run to create the cron jobs
```

Then pick a scheduler (the script prints both):

- **Any OS:** `hermes -p berghain gateway start` — the profile gateway has a
  built-in cron ticker.
- **macOS, no daemon:** install the launchd template — it fires
  `hermes -p berghain cron tick` at 09:00 (the tick runs whichever job is due).

### Where it delivers

This is a **one-way push bot**, not an interactive one. It never listens for
messages and does **not** post to whatever chat it happens to be added to — it
pushes only to the chat id configured on each job (`--deliver`) and in
`TELEGRAM_HOME_CHANNEL`. Adding the bot to another group changes nothing until
you point a job at that group's id.

**Find the target chat id** — message the bot (DM) or add it to the group and
send any message there, then:

```bash
curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates" \
  | grep -oE '"chat":\{"id":-?[0-9]+' | sort -u
```

- **Private chat:** a positive id (e.g. `123456789`).
- **Group / supergroup:** a **negative** id (e.g. `-1001234567890`). The bot must
  be a **member** of the group to post there (membership is enough — it doesn't
  need admin, and the group doesn't need to message it first).

Put the id in `.env` as `TELEGRAM_HOME_CHANNEL`, or target it explicitly:

```bash
hermes -p berghain cron edit <job_id> --deliver telegram:-1001234567890
```

To post the same digest to several chats, add one job per target (or a second
`--deliver`), each pointing at its own chat id.

## Keep the live bot in sync with git (maintainer mode)

On the machine that maintains the bot you can symlink the profile's `scripts/`
and `config.yaml` straight to a clone of this repo, so git *is* the source of
truth — no copy step:

```bash
git clone git@github.com:Tuch/bh-10243-bot.git ~/code/bh-10243-bot
cd ~/code/bh-10243-bot
./setup.sh          # first-time: create profile, .env, cron jobs
./link.sh           # symlink profile scripts/ + config.yaml -> this clone
```

From then on:

- **Update the running bot:** `git pull` — the next cron run reads the new
  scripts automatically (no restart).
- **Publish local edits:** edit files here, then `git add/commit/push`.

`link.sh` is idempotent and backs up any real files it replaces. Hermes' cron
guard resolves the symlinked `scripts/` dir, so scripts still pass the
"must live under the profile scripts dir" check. Edit `config.yaml` via git
rather than `hermes config set`, which would replace the symlink with a file.

## Customizing

- **Topic:** edit the feed URLs / `q=berghain` in `scripts/berghain_common.py`.
- **Times:** `hermes -p berghain cron edit <job_id> --schedule "0 8 * * *"`.
- **Counts:** `HOT_LIMIT` and the `_fetch_hot(...)` limits in `berghain_common.py`.
- **Test a job now:** `hermes -p berghain cron run bh_daily`.
