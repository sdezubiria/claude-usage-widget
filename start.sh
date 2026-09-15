#!/usr/bin/env bash
# start.sh — run the usage fetcher in the background without launchd.
# (If you installed the launchd agent, you don't need this.)
DIR="$(cd "$(dirname "$0")" && pwd)"

pkill -f "fetch_usage.py --loop" 2>/dev/null || true

nohup python3 "$DIR/fetch_usage.py" --loop >> "$DIR/fetch.log" 2>&1 &
echo "Fetcher started (PID $!), logging to fetch.log"
echo "Then either open Übersicht, or run: python3 widget.py"
