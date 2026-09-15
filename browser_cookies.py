"""
browser_cookies.py — find claude.ai logins (the `sessionKey` cookie) in the
browsers installed on this Mac.

  Firefox family   cookies.sqlite, values stored in plain text
  Chromium family  Cookies, values encrypted with a key kept in the login
                   Keychain ("<Browser> Safe Storage"), so macOS asks for
                   permission the first time a key is decrypted
  Safari           not supported (its cookie file needs Full Disk Access)
"""

import hashlib, shutil, sqlite3, subprocess, tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

AS = Path.home() / "Library/Application Support"

FIREFOX_FAMILY = {
    "zen":       AS / "zen/Profiles",
    "firefox":   AS / "Firefox/Profiles",
    "librewolf": AS / "librewolf/Profiles",
    "floorp":    AS / "Floorp/Profiles",
}

CHROMIUM_FAMILY = {  # name: (user data dir, Keychain service holding the cookie key)
    "chrome":   (AS / "Google/Chrome",               "Chrome Safe Storage"),
    "arc":      (AS / "Arc/User Data",               "Arc Safe Storage"),
    "brave":    (AS / "BraveSoftware/Brave-Browser", "Brave Safe Storage"),
    "edge":     (AS / "Microsoft Edge",              "Microsoft Edge Safe Storage"),
    "vivaldi":  (AS / "Vivaldi",                     "Vivaldi Safe Storage"),
    "chromium": (AS / "Chromium",                    "Chromium Safe Storage"),
}

BROWSERS = [*FIREFOX_FAMILY, *CHROMIUM_FAMILY]

CHROMIUM_EPOCH_OFFSET = 11644473600  # seconds between 1601-01-01 and 1970-01-01


@dataclass
class Session:
    browser: str
    profile: str
    last_used: float                                  # unix seconds
    _read: Callable[[], "str | None"] = field(repr=False)
    needs_keychain: bool = False                      # reading it shows a macOS password dialog

    def session_key(self) -> str | None:
        """Chromium values are decrypted only here, so Keychain prompts happen only when needed."""
        return self._read()


def _query(db: Path, sql: str) -> list:
    """Query a copy of the DB — browsers keep theirs locked while running."""
    tmp = Path(tempfile.mkdtemp())
    try:
        copy = tmp / db.name
        shutil.copy2(db, copy)
        wal = db.with_name(db.name + "-wal")
        if wal.exists():
            shutil.copy2(wal, tmp / wal.name)
        con = sqlite3.connect(copy)
        try:
            return con.execute(sql).fetchall()
        finally:
            con.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ── Firefox family ────────────────────────────────────────────────────────────

def _firefox_sessions(name: str, root: Path) -> list[Session]:
    out = []
    for db in root.glob("*/cookies.sqlite"):
        try:
            rows = _query(db, "SELECT value, lastAccessed FROM moz_cookies "
                              "WHERE host LIKE '%claude.ai' AND name = 'sessionKey'")
        except (sqlite3.Error, OSError):
            continue
        for value, last in rows:
            out.append(Session(name, db.parent.name, last / 1e6, lambda v=value: v))
    return out


# ── Chromium family ───────────────────────────────────────────────────────────

_keys: dict[str, "bytes | None"] = {}

def _chromium_key(service: str) -> bytes | None:
    if service not in _keys:
        r = subprocess.run(["security", "find-generic-password", "-w", "-s", service],
                           capture_output=True, text=True)
        _keys[service] = (hashlib.pbkdf2_hmac("sha1", r.stdout.strip().encode(), b"saltysalt", 1003, 16)
                          if r.returncode == 0 else None)
    return _keys[service]

def _chromium_decrypt(blob: bytes, host: str, service: str) -> str | None:
    if blob[:3] != b"v10":
        return None
    key = _chromium_key(service)
    if not key:
        return None
    r = subprocess.run(["openssl", "enc", "-d", "-aes-128-cbc", "-K", key.hex(), "-iv", "20" * 16],
                       input=blob[3:], capture_output=True)
    if r.returncode != 0:
        return None
    plain = r.stdout
    # Chromium 130+ prefixes the value with sha256(host) before encrypting
    if plain[:32] == hashlib.sha256(host.encode()).digest():
        plain = plain[32:]
    return plain.decode("utf-8", "replace")

def _chromium_sessions(name: str, root: Path, service: str) -> list[Session]:
    out = []
    for db in [*root.glob("*/Network/Cookies"), *root.glob("*/Cookies")]:
        try:
            rows = _query(db, "SELECT host_key, value, encrypted_value, last_access_utc FROM cookies "
                              "WHERE host_key LIKE '%claude.ai' AND name = 'sessionKey'")
        except (sqlite3.Error, OSError):
            continue
        profile = db.parents[1].name if db.parent.name == "Network" else db.parent.name
        for host, value, blob, last in rows:
            read = (lambda v=value: v) if value else (lambda b=blob, h=host: _chromium_decrypt(b, h, service))
            out.append(Session(name, profile, last / 1e6 - CHROMIUM_EPOCH_OFFSET, read,
                               needs_keychain=not value))
    return out


# ── Public API ────────────────────────────────────────────────────────────────

def find_sessions(browser: str | None = None) -> list[Session]:
    """Every claude.ai login found, most recently used first. `browser` limits the search to one."""
    if browser and browser not in BROWSERS:
        raise ValueError(f"Unknown browser '{browser}'. Choose from: {', '.join(BROWSERS)}")
    found = []
    for name, root in FIREFOX_FAMILY.items():
        if browser in (None, name):
            found += _firefox_sessions(name, root)
    for name, (root, service) in CHROMIUM_FAMILY.items():
        if browser in (None, name):
            found += _chromium_sessions(name, root, service)
    return sorted(found, key=lambda s: s.last_used, reverse=True)
