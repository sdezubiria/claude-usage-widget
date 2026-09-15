#!/usr/bin/env python3
"""
Claude Code Usage Widget
Floating desktop widget with terminal-art aesthetic showing Claude Code usage.
- Drag to move
- Double-click to refresh
- Right-click to quit
"""

import tkinter as tk
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path

DATA_FILE = Path(__file__).parent / "usage_data.json"

# ── Claude Code color palette ──────────────────────────────────────────────
C = {
    "bg":         "#0D0D0D",
    "surface":    "#111111",
    "border":     "#D97706",   # Claude orange
    "title":      "#F59E0B",   # Amber
    "text":       "#E5E7EB",
    "dim":        "#6B7280",
    "bar_fill":   "#3B82F6",   # Blue progress
    "bar_bg":     "#1E293B",
    "bar_warn":   "#F59E0B",   # Amber at 75%+
    "bar_crit":   "#EF4444",   # Red at 90%+
    "green":      "#10B981",
    "separator":  "#1F2937",
}

W, H = 440, 442
FONT = "SF Mono"
REFRESH_INTERVAL = 300  # seconds


def load_data():
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "session":  {"percent": 0, "resets_in": "—"},
        "weekly":   {"percent": 0, "resets_in": "—"},
        "fable":    {"percent": 0, "resets_in": "—", "available": False},
        "extra":   {"spent": 0.0, "percent": 0, "limit": 20.0, "resets": "—", "enabled": False},
        "plan":     "—",
        "updated":  None,
    }


def bar_color(pct):
    if pct >= 90:
        return C["bar_crit"]
    if pct >= 75:
        return C["bar_warn"]
    return C["bar_fill"]


def format_ago(iso_str):
    if not iso_str:
        return "never  ·  run  fetch_usage.py"
    try:
        dt = datetime.fromisoformat(iso_str)
        secs = (datetime.now() - dt).total_seconds()
        if secs < 60:
            return "just now"
        if secs < 3600:
            m = int(secs / 60)
            return f"{m} min ago"
        h = int(secs / 3600)
        return f"{h}h ago"
    except Exception:
        return "—"


class UsageWidget:
    def __init__(self):
        self.data = load_data()
        self._drag_x = 0
        self._drag_y = 0

        self.root = tk.Tk()
        self._setup_window()

        self.canvas = tk.Canvas(
            self.root, width=W, height=H,
            bg=C["bg"], highlightthickness=0,
        )
        self.canvas.pack()
        self._bind_events()
        self.redraw()
        self._start_refresh()

    # ── Window setup ──────────────────────────────────────────────────────

    def _setup_window(self):
        r = self.root
        r.overrideredirect(True)
        r.attributes("-alpha", 0.94)
        r.configure(bg=C["bg"])

        # macOS: float above desktop but below normal windows
        try:
            r.tk.call(
                "::tk::unsupported::MacWindowStyle",
                "style", r._w, "help", "noActivates",
            )
        except Exception:
            pass

        sw = r.winfo_screenwidth()
        sh = r.winfo_screenheight()
        x = sw - W - 24
        y = sh - H - 80
        r.geometry(f"{W}x{H}+{x}+{y}")

    # ── Events ────────────────────────────────────────────────────────────

    def _bind_events(self):
        cv = self.canvas
        cv.bind("<Button-1>",    self._on_press)
        cv.bind("<B1-Motion>",   self._on_drag)
        cv.bind("<Double-1>",    lambda e: self._manual_refresh())
        cv.bind("<Button-2>",    lambda e: self.root.destroy())
        cv.bind("<Button-3>",    lambda e: self.root.destroy())

    def _on_press(self, e):
        self._drag_x = e.x
        self._drag_y = e.y

    def _on_drag(self, e):
        dx = e.x - self._drag_x
        dy = e.y - self._drag_y
        self.root.geometry(f"+{self.root.winfo_x()+dx}+{self.root.winfo_y()+dy}")

    def _manual_refresh(self):
        self.data = load_data()
        self.redraw()

    # ── Auto-refresh ──────────────────────────────────────────────────────

    def _start_refresh(self):
        def loop():
            while True:
                time.sleep(REFRESH_INTERVAL)
                self.data = load_data()
                self.root.after(0, self.redraw)
        threading.Thread(target=loop, daemon=True).start()

    # ── Drawing helpers ───────────────────────────────────────────────────

    def _text(self, x, y, s, color=None, size=10, anchor="w", bold=False):
        self.canvas.create_text(
            x, y, text=s,
            fill=color or C["text"],
            font=(FONT, size, "bold" if bold else "normal"),
            anchor=anchor,
        )

    def _bar(self, x, y, w, h, pct):
        cv = self.canvas
        # background track
        cv.create_rectangle(x, y, x + w, y + h, fill=C["bar_bg"], outline="")
        # rounded-ish ends via small inset
        fill_w = max(4, int(w * min(pct, 100) / 100))
        fill_color = bar_color(pct)
        cv.create_rectangle(x, y, x + fill_w, y + h, fill=fill_color, outline="")

    def _hline(self, y, color=None, pad=14):
        self.canvas.create_line(
            pad, y, W - pad, y,
            fill=color or C["separator"], width=1,
        )

    # ── Main draw ─────────────────────────────────────────────────────────

    def redraw(self):
        cv = self.canvas
        cv.delete("all")
        d = self.data

        pad = 16
        bar_w = W - pad * 2 - 72   # leave room for "xx% used"

        # ── outer border ──
        cv.create_rectangle(1, 1, W - 1, H - 1,
                            outline=C["border"], width=1)

        # ── title bar ──
        cv.create_rectangle(1, 1, W - 1, 34,
                            fill=C["surface"], outline="")
        self._text(pad,      17, "◆",               color=C["border"], size=11, bold=True)
        self._text(pad + 18, 17, "CLAUDE CODE",      color=C["title"],  size=10, bold=True)
        self._text(pad + 112,17, "·  USAGE MONITOR", color=C["dim"],    size=9)

        plan = d.get("plan", "—")
        self._text(W - pad, 17, plan, color=C["dim"], size=9, anchor="e")

        cv.create_line(1, 34, W - 1, 34, fill=C["border"], width=1)

        y = 50

        # ── SESSION ──────────────────────────────────────────────────────
        self._text(pad, y, "SESSION", color=C["title"], size=9, bold=True)
        y += 16

        sp = d["session"]["percent"]
        self._bar(pad, y, bar_w, 7, sp)
        self._text(W - pad, y + 3, f"{sp}% used", color=C["text"], size=9, anchor="e")
        y += 16

        self._text(pad, y, f"Resets in {d['session']['resets_in']}", color=C["dim"], size=9)
        y += 18

        self._hline(y)
        y += 12

        # ── WEEKLY ───────────────────────────────────────────────────────
        self._text(pad, y, "WEEKLY", color=C["title"], size=9, bold=True)
        y += 16

        wp = d["weekly"]["percent"]
        self._bar(pad, y, bar_w, 7, wp)
        self._text(W - pad, y + 3, f"{wp}% used", color=C["text"], size=9, anchor="e")
        y += 16

        self._text(pad, y, f"Resets in {d['weekly']['resets_in']}", color=C["dim"], size=9)
        y += 18

        self._hline(y)
        y += 12

        # ── FABLE (weekly, model-scoped) ─────────────────────────────────
        fable = d.get("fable") or {}
        self._text(pad, y, "FABLE", color=C["title"], size=9, bold=True)
        y += 16

        fp = fable.get("percent", 0)
        self._bar(pad, y, bar_w, 7, fp)
        self._text(W - pad, y + 3, f"{fp}% used", color=C["text"], size=9, anchor="e")
        y += 16

        if fable.get("available"):
            self._text(pad, y, f"Weekly  ·  Resets in {fable.get('resets_in', '—')}", color=C["dim"], size=9)
        else:
            self._text(pad, y, "No Fable limit on this plan", color=C["dim"], size=9)
        y += 18

        self._hline(y)
        y += 12

        # ── EXTRA USAGE ──────────────────────────────────────────────────
        self._text(pad, y, "EXTRA USAGE", color=C["title"], size=9, bold=True)

        extra = d.get("extra", {})
        enabled = extra.get("enabled", False)
        status = "ON" if enabled else "OFF"
        status_color = C["green"] if enabled else C["dim"]
        self._text(W - pad, y, status, color=status_color, size=9, anchor="e", bold=True)
        y += 16

        spent   = extra.get("spent", 0.0)
        ep      = extra.get("percent", 0)
        limit   = extra.get("limit", 20.0)
        resets_e = extra.get("resets", "—")

        self._text(pad, y, f"${spent:.2f} spent  ·  ${limit:.0f} monthly limit", color=C["text"], size=9)
        y += 14

        self._bar(pad, y, bar_w, 7, ep)
        self._text(W - pad, y + 3, f"{ep}% used", color=C["text"], size=9, anchor="e")
        y += 16

        self._text(pad, y, f"Resets {resets_e}", color=C["dim"], size=9)
        y += 20

        # ── footer ───────────────────────────────────────────────────────
        cv.create_line(1, H - 26, W - 1, H - 26, fill=C["border"], width=1)
        ago = format_ago(d.get("updated"))
        self._text(pad,     H - 13, f"↻  {ago}", color=C["dim"], size=8)
        self._text(W - pad, H - 13, "dbl-click refresh  ·  right-click quit",
                   color=C["dim"], size=7, anchor="e")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    UsageWidget().run()
