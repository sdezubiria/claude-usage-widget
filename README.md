# Claude Usage Widget

A macOS desktop widget that shows your [claude.ai](https://claude.ai) plan limits at a glance, so you see a limit coming before you hit it.

- **Session**: the rolling 5-hour limit
- **Weekly**: the 7-day limit across all models
- **Fable**: the separate weekly Fable limit (shown only if your plan has one)
- **Extra usage**: credits spent against your monthly cap

Bars turn **amber at 75%** and **red at 90%**. A pixel-art mascot reacts to your session usage: calm when you're idle, sweating at 75%, panicking at 90%, asleep once you hit the limit.

> **Unofficial.** This project is not affiliated with Anthropic. It reads the same internal endpoint the claude.ai settings page uses, which can change without notice.

---

## How it works

```
Zen Browser cookies ──┐
                      ├─▶ fetch_usage.py ──▶ claude.ai/api/organizations/{id}/usage
macOS Keychain ───────┘         │
                                ▼
                         usage_data.json
                                │
                 ┌──────────────┴──────────────┐
                 ▼                             ▼
      Übersicht widget (JSX)          widget.py (tkinter)
```

1. `fetch_usage.py` takes your claude.ai login cookie from Zen Browser, with a copy saved in the macOS Keychain as backup.
2. Every 5 minutes it calls the usage API, using [`curl_cffi`](https://github.com/lexiforest/curl_cffi) to look like a real browser so Cloudflare lets it through.
3. It writes the result to `usage_data.json`.
4. A widget reads that file and draws it. Use **Übersicht** (it sits on your desktop) or **widget.py** (a floating window, nothing else to install).

Your cookies never leave your machine except to talk to claude.ai.

---

## Requirements

| | |
|---|---|
| **macOS** | Uses Keychain and launchd |
| **Python 3.10+** | Check with `python3 --version` |
| **[Zen Browser](https://zen-browser.app)** | Logged in to claude.ai. Other browsers: see [Configuration](#configuration) |
| **[Übersicht](https://tracesof.net/uebersicht/)** | Optional, only for the desktop widget |

---

## Quick start

### 1. Install

```bash
git clone https://github.com/sdezubiria/claude-usage-widget.git ~/claude-usage-widget
cd ~/claude-usage-widget
pip3 install -r requirements.txt
```

### 2. Connect your account

Make sure you're logged in to claude.ai in Zen, then run:

```bash
python3 fetch_usage.py --setup
```

This copies your session key into the Keychain and runs one test fetch. You should see something like:

```
session=55%  weekly=54%
Setup complete.
```

### 3. Keep the data fresh

Install the background fetcher as a launchd agent. It starts at login and refreshes every 5 minutes:

```bash
sed -e "s|__PYTHON__|$(which python3)|" -e "s|__REPO__|$PWD|g" \
  launchd/com.claudeusagewidget.fetch.plist \
  > ~/Library/LaunchAgents/com.claudeusagewidget.fetch.plist
launchctl load ~/Library/LaunchAgents/com.claudeusagewidget.fetch.plist
```

If you'd rather not install a login agent, run `./start.sh` instead. The fetcher then runs until you log out.

### 4. Show the widget

**Option A: Übersicht (desktop widget)**

1. If you cloned somewhere other than `~/claude-usage-widget`, open `ubersicht/claude-usage.widget/index.jsx` and set `DATA_FILE` to your `usage_data.json` path.
2. Link the widget into Übersicht:
   ```bash
   ln -s "$PWD/ubersicht/claude-usage.widget" \
     ~/Library/Application\ Support/Übersicht/widgets/claude-usage.widget
   ```
3. In the Übersicht menu bar icon, choose **Refresh All Widgets**.

**Option B: floating window**

```bash
python3 widget.py
```

Drag the window to move it, double-click to reload, right-click to quit.

---

## The mascot

The Übersicht widget has a pixel-art robot whose mood follows your **session** usage:

| Session | Mood | Animation |
|---|---|---|
| under 25% | idle | Slow breathing, blinking |
| 25–74% | working | Walks in place, swings arms |
| 75–89% | hustling | Double speed, sweat drop |
| 90–99% | panicking | Frantic, shaking, sweating |
| 100% | resting | Eyes shut, floating z's |

Animations turn off if **Reduce motion** is on in macOS settings. To change the thresholds, edit `moodFor()` in `index.jsx`.

---

## Configuration

| What | How |
|---|---|
| **Zen profile** | Found automatically (the most recently used profile). To pick one, set `ZEN_COOKIES_DB=/path/to/cookies.sqlite`. |
| **Other Firefox-based browsers** | Point `ZEN_COOKIES_DB` at that browser's `cookies.sqlite`. |
| **Chrome / Safari** | Their cookies are encrypted, so they aren't read automatically. Copy `sessionKey` from DevTools → Application → Cookies and paste it when `--setup` asks. |
| **Fetch interval** | `python3 fetch_usage.py --loop 120` (seconds). Default is 300. |
| **Colors** | The `C` dict in `widget.py`, or the inline styles in `index.jsx`. |
| **Manual values** | `python3 set_usage.py` asks for each value. Handy for testing the UI. |

### `usage_data.json`

Both widgets read this file:

```json
{
  "plan": "Max",
  "session": { "percent": 55, "resets_in": "1h 18m" },
  "weekly":  { "percent": 54, "resets_in": "7h 18m" },
  "fable":   { "percent": 92, "resets_in": "7h 18m", "available": true },
  "extra":   { "enabled": true, "spent": 0.0, "percent": 0, "limit": 12.0, "resets": "1st of month" },
  "updated": "2026-09-15T11:41:48"
}
```

---

## Troubleshooting

**The widget shows old numbers, or "updated Xh ago" keeps growing**

Check the log:

```bash
tail fetch.log
```

- `Session expired`: log in to claude.ai in Zen again. The fetcher picks up the new cookie on its next run and saves it to the Keychain.
- `HTTP Error 403` without a session message: Cloudflare blocked the request. Open claude.ai in Zen once to refresh the `cf_clearance` cookie.

**The Übersicht widget is blank**

Open `http://127.0.0.1:41416` in a browser and check the console for build errors. If that page doesn't load at all, quit and reopen Übersicht.

**The Fable bar is missing**

The row only appears when the API reports a Fable limit for your plan.

**Keychain asks for permission on every fetch**

In Keychain Access, find the `claude.ai` item for account `claude-usage-widget`, open **Access Control**, and allow `python3`.

**Restart the background fetcher**

```bash
launchctl kickstart -k gui/$(id -u)/com.claudeusagewidget.fetch
```

---

## Project layout

```
fetch_usage.py   fetches usage and writes usage_data.json
widget.py        floating tkinter widget
set_usage.py     enter values by hand
start.sh         run the fetcher without launchd
launchd/         login agent template
ubersicht/       Übersicht desktop widget, with the mascot
extension/       experimental Zen/Firefox extension (needs a local receiver on :8765, not included)
```

---

## License

[MIT](LICENSE)
