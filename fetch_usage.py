#!/usr/bin/env python3
"""
fetch_usage.py — fetches Claude usage and writes usage_data.json.

Authentication:
  - Only the claude.ai `sessionKey` cookie is needed.
  - A working key is kept in the macOS Keychain and tried first.
  - When it's missing or expired, the most recently used claude.ai login is
    taken from any supported browser (see browser_cookies.py) and saved back
    to the Keychain.
  - Requests go through curl_cffi with a real browser TLS fingerprint so
    Cloudflare lets them through.

Usage:
  python3 fetch_usage.py --setup             # find a login and test it
  python3 fetch_usage.py                     # fetch once
  python3 fetch_usage.py --loop [seconds]    # fetch every 5 min (default)
  python3 fetch_usage.py --browsers          # show where claude.ai logins were found
  Add --browser chrome (or CLAUDE_BROWSER=chrome) to use only one browser.
"""

import json, os, sys, time, subprocess
from datetime import datetime
from pathlib import Path
from curl_cffi import requests as cf_requests

import browser_cookies

DATA_FILE        = Path(__file__).parent / "usage_data.json"
KEYCHAIN_ACCOUNT = "claude-usage-widget"
KEYCHAIN_SERVICE = "claude.ai"

# ── Keychain helpers ──────────────────────────────────────────────────────────

def keychain_store(key: str):
    subprocess.run(
        ["security", "add-generic-password", "-U",
         "-a", KEYCHAIN_ACCOUNT, "-s", KEYCHAIN_SERVICE, "-w", key],
        check=True, capture_output=True
    )

def keychain_read() -> str | None:
    r = subprocess.run(
        ["security", "find-generic-password",
         "-a", KEYCHAIN_ACCOUNT, "-s", KEYCHAIN_SERVICE, "-w"],
        capture_output=True, text=True
    )
    return r.stdout.strip() if r.returncode == 0 else None

# ── API helpers ───────────────────────────────────────────────────────────────

HEADERS = {
    "Accept":   "application/json",
    "Referer":  "https://claude.ai/settings/limits",
    "Origin":   "https://claude.ai",
}

class AuthError(Exception):
    pass

def api_get(path: str, session_key: str):
    r = cf_requests.get(
        "https://claude.ai" + path,
        cookies={"sessionKey": session_key},
        headers=HEADERS,
        impersonate="chrome",
        timeout=15,
    )
    if r.status_code in (401, 403):
        if "json" in r.headers.get("content-type", ""):
            raise AuthError(f"HTTP {r.status_code}")
        raise RuntimeError(f"Blocked by Cloudflare (HTTP {r.status_code}). Try again in a few minutes")
    r.raise_for_status()
    return r.json()

# ── Parse API response → widget schema ───────────────────────────────────────

def secs_to_hm(iso: str | None) -> str:
    if not iso:
        return "—"
    diff = max(0, datetime.fromisoformat(iso.replace("Z", "+00:00"))
               .timestamp() - datetime.now().astimezone().timestamp())
    total_h = int(diff) // 3600
    m = (int(diff) % 3600) // 60
    d, h = divmod(total_h, 24)
    if d and h and m: return f"{d}d {h}h {m}m"
    if d and h:       return f"{d}d {h}h"
    if d and m:       return f"{d}d {m}m"
    if d:             return f"{d}d"
    if h and m:       return f"{h}h {m}m"
    if h:             return f"{h}h"
    return f"{m}m"

def plan_name(org: dict) -> str:
    caps = org.get("capabilities") or []
    if "claude_max" in caps: return "Max"
    if "claude_pro" in caps: return "Pro"
    return "Free"

def money(m: dict | None) -> float:
    """API money objects are {amount_minor, exponent} — 1200 @ exp 2 = $12.00."""
    m = m or {}
    return (m.get("amount_minor") or 0) / 10 ** (m.get("exponent") or 2)

def find_limit(limits: list, kind: str, model: str | None = None) -> dict | None:
    for lim in limits:
        if lim.get("kind") != kind:
            continue
        name = ((lim.get("scope") or {}).get("model") or {}).get("display_name") or ""
        if model is None or name.lower() == model.lower():
            return lim
    return None

def window(lim: dict | None, legacy: dict | None = None) -> dict:
    """Prefer the `limits` entry; fall back to the legacy five_hour/seven_day block."""
    if lim:
        pct, resets = lim.get("percent"), lim.get("resets_at")
    else:
        legacy = legacy or {}
        pct, resets = legacy.get("utilization"), legacy.get("resets_at")
    return {"percent": int(round(float(pct or 0))), "resets_in": secs_to_hm(resets)}

def parse(raw: dict, org: dict) -> dict:
    limits = raw.get("limits") or []
    fable  = find_limit(limits, "weekly_scoped", "Fable")
    sp     = raw.get("spend") or {}
    ex     = raw.get("extra_usage") or {}
    return {
        "plan":    plan_name(org),
        "session": window(find_limit(limits, "session"),    raw.get("five_hour")),
        "weekly":  window(find_limit(limits, "weekly_all"), raw.get("seven_day")),
        "fable":   {**window(fable), "available": fable is not None},
        "extra": {
            "enabled": bool(sp.get("enabled", ex.get("is_enabled", False))),
            "spent":   money(sp.get("used"))  if sp else (ex.get("used_credits") or 0) / 100,
            "percent": int(round(float(sp.get("percent") or 0))),
            "limit":   money(sp.get("limit")) if sp else (ex.get("monthly_limit") or 0) / 100,
            "resets":  "1st of month",
        },
        "updated": datetime.now().isoformat(),
    }

# ── Finding a working login ───────────────────────────────────────────────────

def selected_browser() -> str | None:
    if "--browser" in sys.argv:
        i = sys.argv.index("--browser")
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1].lower()
    return (os.environ.get("CLAUDE_BROWSER") or "").lower() or None

def try_key(key: str) -> list | None:
    """The org list if this sessionKey is valid, else None."""
    try:
        return api_get("/api/organizations", key)
    except AuthError:
        return None

def find_working_key(interactive: bool = False) -> tuple[str, list, str]:
    """(sessionKey, orgs, source). Keychain first, then browsers, freshest login first.

    Chromium logins can only be read through a macOS password dialog, so they are
    tried only when `interactive` (--setup). The background loop never shows one.
    """
    kc_key = keychain_read()
    if kc_key and (orgs := try_key(kc_key)):
        return kc_key, orgs, "keychain"

    tried, skipped = {kc_key}, 0
    found = browser_cookies.find_sessions(selected_browser())
    for s in found:
        if s.needs_keychain and not interactive:
            skipped += 1
            continue
        key = s.session_key()
        if not key or key in tried:
            continue
        tried.add(key)
        if orgs := try_key(key):
            keychain_store(key)
            return key, orgs, f"{s.browser} ({s.profile})"

    if not found:
        raise RuntimeError("No claude.ai login found in any browser. "
                           "Log in at claude.ai, or run --setup to paste a key")
    if skipped:
        raise RuntimeError("Session expired. Log in to claude.ai again, then run: python3 fetch_usage.py --setup")
    raise RuntimeError("Session expired. Log in to claude.ai in your browser again")

def fetch(interactive: bool = False) -> dict:
    key, orgs, source = find_working_key(interactive)
    if source != "keychain":
        print(f"  using claude.ai login from {source}")
    org    = orgs[0]
    org_id = org.get("uuid") or org.get("id")
    return parse(api_get(f"/api/organizations/{org_id}/usage", key), org)

# ── Setup and listing ─────────────────────────────────────────────────────────

def list_browsers():
    found = browser_cookies.find_sessions(selected_browser())
    if not found:
        print("  no claude.ai logins found")
    for s in found:
        when = datetime.fromtimestamp(s.last_used).strftime("%Y-%m-%d %H:%M")
        print(f"  {s.browser:10} {s.profile:28} last used {when}")

def setup():
    print("claude.ai logins found in your browsers:")
    list_browsers()
    print("\nTesting… (Chromium browsers: macOS may ask for your login keychain password"
          " to read '<Browser> Safe Storage'. Cancel it to skip that browser.)")
    try:
        data = fetch(interactive=True)
    except RuntimeError as e:
        print(f"\n{e}")
        print("Paste your sessionKey instead (DevTools → Application/Storage → Cookies → claude.ai → sessionKey):")
        key = input("> ").strip()
        if not key or not try_key(key):
            print("That key didn't work."); sys.exit(1)
        keychain_store(key)
        data = fetch(interactive=True)

    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  session={data['session']['percent']}%  weekly={data['weekly']['percent']}%")
    print("Setup complete. Saved to the macOS Keychain.")

# ── Entry points ──────────────────────────────────────────────────────────────

def run_once(verbose=True):
    data = fetch()
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)
    if verbose:
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] session={data['session']['percent']}%  "
              f"weekly={data['weekly']['percent']}%  "
              f"fable={data['fable']['percent']}%  "
              f"extra=${data['extra']['spent']:.2f}")

def run_loop(interval=300):
    print(f"Fetching every {interval}s  (Ctrl-C to stop)\n")
    while True:
        try:
            run_once()
        except Exception as e:
            print(f"  error: {e}")
        time.sleep(interval)

if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)  # so fetch.log updates live under launchd
    try:
        if "--setup" in sys.argv:
            setup()
        elif "--browsers" in sys.argv:
            list_browsers()
        elif "--loop" in sys.argv or "-l" in sys.argv:
            interval = next((int(a) for a in sys.argv[1:] if a.isdigit()), 300)
            run_loop(interval)
        else:
            run_once()
    except (RuntimeError, ValueError) as e:
        print(f"✗ {e}")
        sys.exit(1)
