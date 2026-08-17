#!/usr/bin/env bash
#
# Set up the Berghain digest push-bot as a dedicated Hermes profile.
# Idempotent: safe to re-run. Requires Hermes installed (`hermes` on PATH).
#
#   ./setup.sh            # uses profile name "berghain"
#   ./setup.sh myname     # custom profile name
#
set -euo pipefail

PROFILE="${1:-berghain}"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
PROFILE_HOME="$HOME/.hermes/profiles/$PROFILE"

command -v hermes >/dev/null 2>&1 || {
  echo "ERROR: 'hermes' not found on PATH. Install Hermes first: https://hermes-agent.nousresearch.com" >&2
  exit 1
}

echo "==> Creating profile '$PROFILE' (if missing)"
hermes profile create "$PROFILE" --no-skills \
  --description "Berghain Reddit digest push-bot" 2>/dev/null || true

mkdir -p "$PROFILE_HOME/scripts"

echo "==> Installing config + scripts"
cp "$REPO_DIR/config.yaml" "$PROFILE_HOME/config.yaml"
cp "$REPO_DIR/scripts/"*.py "$PROFILE_HOME/scripts/"

echo "==> Checking .env (bot token)"
if [ ! -f "$PROFILE_HOME/.env" ] || ! grep -q '^TELEGRAM_BOT_TOKEN=..*' "$PROFILE_HOME/.env"; then
  cp -n "$REPO_DIR/.env.example" "$PROFILE_HOME/.env" 2>/dev/null || true
  echo ""
  echo "  !! Fill in your bot token + chat id, then re-run:"
  echo "     \$EDITOR $PROFILE_HOME/.env"
  echo ""
  exit 0
fi

echo "==> Creating cron jobs (daily + weekly)"
hermes -p "$PROFILE" cron create "0 9 * * *" --no-agent \
  --script berghain-daily.py  --deliver telegram --name "bh_daily"  2>/dev/null || echo "   (daily job already exists — skipping)"
hermes -p "$PROFILE" cron create "0 9 * * 1" --no-agent \
  --script berghain-weekly.py --deliver telegram --name "bh_weekly" 2>/dev/null || echo "   (weekly job already exists — skipping)"

echo ""
echo "==> Jobs:"
hermes -p "$PROFILE" cron list || true

cat <<EOF

Done. Pick a scheduler:

  A) Simplest, any OS — run the profile's gateway (has a built-in cron ticker):
       hermes -p $PROFILE gateway start

  B) Lightweight, macOS, no persistent process — launchd fires 'cron tick' at 09:00:
       sed "s|__HOME__|\$HOME|g" "$REPO_DIR/launchd/ai.hermes.berghain-push.plist.template" \\
         > ~/Library/LaunchAgents/ai.hermes.berghain-push.plist
       launchctl bootstrap gui/\$(id -u) ~/Library/LaunchAgents/ai.hermes.berghain-push.plist

Test now:  hermes -p $PROFILE cron run bh_daily
EOF
