#!/usr/bin/env bash
#
# "Maintainer mode": symlink a Hermes profile's scripts/ and config.yaml to
# THIS repo clone, so the live bot always reflects the checkout. Then:
#   git pull   -> updates the running bot (scripts are re-read each cron run)
#   edit + git push -> publishes your changes
#
# Unlike setup.sh (which COPIES for a fresh install), this LINKS for the machine
# that maintains the bot. Idempotent.
#
#   ./link.sh            # profile "berghain"
#   ./link.sh myname     # custom profile
#
set -euo pipefail

PROFILE="${1:-berghain}"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
P="$HOME/.hermes/profiles/$PROFILE"

[ -d "$P" ] || { echo "Profile '$PROFILE' not found at $P — run ./setup.sh first."; exit 1; }

for target in scripts config.yaml; do
  dest="$P/$target"
  if [ -L "$dest" ]; then
    rm "$dest"                                  # replace an existing symlink
  elif [ -e "$dest" ]; then
    mv "$dest" "$dest.prelink.$(date +%s)"      # keep a backup of real files
  fi
  ln -s "$REPO_DIR/$target" "$dest"
  echo "linked  $dest -> $REPO_DIR/$target"
done

echo
echo "Done. The live bot now follows this checkout:"
echo "  update:   (cd $REPO_DIR && git pull)"
echo "  publish:  edit files here, then git add/commit/push"
echo "  test now: hermes -p $PROFILE cron run bh_daily"
