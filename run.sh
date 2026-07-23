#!/usr/bin/env bash
# Run the bot from anywhere:  ~/Downloads/sexresearch-bot/run.sh
# Preview without posting:    ~/Downloads/sexresearch-bot/run.sh --dry-run
# One specific paper:         ~/Downloads/sexresearch-bot/run.sh --pmid 42456031
#
# Any arguments are passed straight through to main.py.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  echo "No virtualenv found. Creating one..."
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi

exec .venv/bin/python main.py "$@"
