#!/usr/bin/env python3
"""
set_usage.py — manually set usage values for the widget.
Run this whenever you want to update the displayed numbers.

Usage:  python3 set_usage.py
"""
import json
from datetime import datetime
from pathlib import Path

DATA_FILE = Path(__file__).parent / "usage_data.json"

def ask(prompt, default=None, cast=int):
    suffix = f" [{default}]" if default is not None else ""
    while True:
        raw = input(f"  {prompt}{suffix}: ").strip()
        if not raw and default is not None:
            return default
        try:
            return cast(raw)
        except ValueError:
            print(f"  → enter a valid {cast.__name__}")

def ask_str(prompt, default="—"):
    suffix = f" [{default}]" if default else ""
    raw = input(f"  {prompt}{suffix}: ").strip()
    return raw or default

print()
print("╭─────────────────────────────────────────────────╮")
print("│  Claude Code Usage Widget — manual data entry   │")
print("╰─────────────────────────────────────────────────╯")
print()

# Load existing for defaults
try:
    existing = json.load(open(DATA_FILE))
except Exception:
    existing = {}

s = existing.get("session", {})
w = existing.get("weekly", {})
f = existing.get("fable", {})
e = existing.get("extra", {})

print("SESSION")
sess_pct    = ask("percent used (0-100)",  s.get("percent", 0))
sess_resets = ask_str("resets in",         s.get("resets_in", "3h 55m"))

print()
print("WEEKLY")
week_pct    = ask("percent used (0-100)",  w.get("percent", 0))
week_resets = ask_str("resets in",         w.get("resets_in", "13h 55m"))

print()
print("FABLE (weekly)")
fable_pct    = ask("percent used (0-100)", f.get("percent", 0))
fable_resets = ask_str("resets in",        f.get("resets_in", "—"))

print()
print("EXTRA USAGE")
extra_en    = ask_str("enabled? (y/n)",    "y" if e.get("enabled") else "n")
extra_spent = ask("$ spent (e.g. 4)",      int(e.get("spent", 0)), cast=float)
extra_pct   = ask("percent used (0-100)",  e.get("percent", 0))
extra_limit = ask("monthly limit $",       int(e.get("limit", 20)), cast=float)
extra_reset = ask_str("resets date",       e.get("resets", "May 1"))

print()
plan = ask_str("Plan (Pro/Max/etc.)", existing.get("plan", "Pro"))

data = {
    "plan": plan,
    "session": {"percent": sess_pct,  "resets_in": sess_resets},
    "weekly":  {"percent": week_pct,  "resets_in": week_resets},
    "fable":   {"percent": fable_pct, "resets_in": fable_resets, "available": True},
    "extra": {
        "enabled": extra_en.lower().startswith("y"),
        "spent":   extra_spent,
        "percent": extra_pct,
        "limit":   extra_limit,
        "resets":  extra_reset,
    },
    "updated": datetime.now().isoformat(),
}

with open(DATA_FILE, "w") as f:
    json.dump(data, f, indent=2)

print(f"✓ Saved to {DATA_FILE}")
print("  Refresh All Widgets in Übersicht to update the display.")
