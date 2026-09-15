#!/usr/bin/env python3
"""
fetch_usage.py — fetches Claude usage and writes usage_data.json.

Authentication strategy (standard macOS app pattern):
  - Session key stored once in macOS Keychain (never re-entered)
  - cf_clearance read from Zen Browser's cookie DB (refreshed automatically)
  - Requests made with curl_cffi impersonating Firefox (bypasses Cloudflare)

First-time setup (auto-reads from Zen, stores in Keychain):
  python3 fetch_usage.py --setup

Normal use:
  python3 fetch_usage.py           # fetch once
  python3 fetch_usage.py --loop    # fetch every 5 min (background)
"""

import json, sys, time, sqlite3, shutil, tempfile, os, subprocess
from datetime import datetime
from pathlib import Path
from curl_cffi import requests as cf_requests
from curl_cffi.requests.exceptions import HTTPError

DATA_FILE   = Path(__file__).parent / "usage_data.json"
ZEN_PROFILES = Path.home() / "Library/Application Support/zen/Profiles"
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

# ── Cookie helpers ────────────────────────────────────────────────────────────

def find_zen_cookies_db() -> Path | None:
    """ZEN_COOKIES_DB env var wins; otherwise the most recently used Zen profile."""
    override = os.environ.get("ZEN_COOKIES_DB")
    if override:
        return Path(override).expanduser()
    dbs = sorted(ZEN_PROFILES.glob("*/cookies.sqlite"),
                 key=lambda p: p.stat().st_mtime, reverse=True)
    return dbs[0] if dbs else None

def read_zen_cookies(names: set) -> dict:
    """Read specific cookies from Zen Browser's SQLite DB."""
    db = find_zen_cookies_db()
    if not db or not db.exists():
        return {}
    tmp = tempfile.mktemp(suffix=".sqlite")
    shutil.copy2(db, tmp)
    try:
        con = sqlite3.connect(tmp)
        rows = con.execute(
            "SELECT name, value FROM moz_cookies WHERE host LIKE '%claude.ai'"
        ).fetchall()
        con.close()
    finally:
        os.unlink(tmp)
    return {n: v for n, v in rows if n in names}

def build_cookies(session_key: str) -> dict:
    """Combine stored session key with fresh cf_clearance from Zen."""
    cookies = read_zen_cookies({"cf_clearance", "anthropic-device-id"})
    cookies["sessionKey"] = session_key
    return cookies

# ── API helpers ───────────────────────────────────────────────────────────────

HEADERS = {
    "Accept":   "application/json",
    "Referer":  "https://claude.ai/settings/limits",
    "Origin":   "https://claude.ai",
}

def api_get(path: str, cookies: dict) -> dict:
    r = cf_requests.get(
        "https://claude.ai" + path,
        cookies=cookies,
        headers=HEADERS,
        impersonate="firefox",
        timeout=15,
    )
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

# ── Main fetch ────────────────────────────────────────────────────────────────

def fetch() -> dict:
    # claude.ai rotates sessionKey, so the Keychain copy goes stale. Try Zen's
    # live cookie first, fall back to Keychain, and re-save whichever works.
    kc_key  = keychain_read()
    zen_key = read_zen_cookies({"sessionKey"}).get("sessionKey")
    keys    = [k for k in dict.fromkeys([zen_key, kc_key]) if k]
    if not keys:
        raise RuntimeError("No session key found. Log in to claude.ai in Zen, or run --setup")

    last_err = None
    for key in keys:
        cookies = build_cookies(key)
        try:
            orgs = api_get("/api/organizations", cookies)
        except HTTPError as e:
            last_err = e
            continue
        if key != kc_key:
            keychain_store(key)
        org    = orgs[0]
        org_id = org.get("uuid") or org.get("id")
        raw    = api_get(f"/api/organizations/{org_id}/usage", cookies)
        return parse(raw, org)

    raise RuntimeError(f"Session expired — log in to claude.ai in Zen again ({last_err})")

# ── Setup: auto-read from Zen Browser DB, store in Keychain ──────────────────

def setup():
    print("Reading session key from Zen Browser…")
    cookies = read_zen_cookies({"sessionKey"})
    key = cookies.get("sessionKey")

    if not key:
        print("Could not find sessionKey in Zen Browser.")
        print("Paste it manually (DevTools → Application → Cookies → claude.ai → sessionKey):")
        key = input("> ").strip()
        if not key:
            print("No key entered."); sys.exit(1)

    keychain_store(key)
    print(f"Stored in macOS Keychain ✓")

    print("Testing…")
    data = fetch()
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  session={data['session']['percent']}%  weekly={data['weekly']['percent']}%")
    print("Setup complete. Run 'python3 fetch_usage.py --loop &' to keep data fresh.")

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
    if "--setup" in sys.argv:
        setup()
    elif "--loop" in sys.argv or "-l" in sys.argv:
        interval = next((int(a) for a in sys.argv[1:] if a.isdigit()), 300)
        run_loop(interval)
    else:
        try:
            run_once()
        except RuntimeError as e:
            print(f"✗ {e}")
