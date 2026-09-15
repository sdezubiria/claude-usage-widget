# Claude Usage Widget

A macOS desktop widget that shows your [claude.ai](https://claude.ai) plan limits at a glance, so you see a limit coming before you hit it.

- **Session**: the rolling 5-hour limit
- **Weekly**: the 7-day limit across all models
- **Fable**: the separate weekly Fable limit (shown only if your plan has one)
- **Extra usage**: credits spent against your monthly cap

Bars turn **amber at 75%** and **red at 90%**. A pixel-art mascot reacts to your session usage: calm when you're idle, sweating at 75%, panicking at 90%, asleep once you hit the limit.

Works with **Chrome, Arc, Brave, Edge, Vivaldi, Chromium, Firefox, Zen, LibreWolf and Floorp**. On any other browser, you paste your login key once.

> **Unofficial.** This project is not affiliated with Anthropic. It reads the same internal endpoint the claude.ai settings page uses, which can change without notice.

---

## How it works

```
Browser cookies (Chrome, Arc, Firefox, Zen, …) ──┐
                                                ├─▶ fetch_usage.py ──▶ claude.ai usage API
macOS Keychain (saved login) ───────────────────┘         │
                                                          ▼
                                                   usage_data.json
                                                          │
                                           ┌──────────────┴──────────────┐
                                           ▼                             ▼
                                Übersicht widget (JSX)          widget.py (tkinter)
```

1. The only thing `fetch_usage.py` needs is your claude.ai login cookie (`sessionKey`).
2. It uses the copy saved in your macOS Keychain. When that login expires, it finds the most recently used claude.ai login in your browsers and saves that one instead. Firefox-family logins are picked up silently; Chromium logins are only read during `--setup`, because reading them shows a macOS password dialog.
3. Every 5 minutes it calls the usage API, using [`curl_cffi`](https://github.com/lexiforest/curl_cffi) to look like a real browser so Cloudflare lets it through, and writes the result to `usage_data.json`.
4. A widget reads that file and draws it. Use **Übersicht** (it sits on your desktop) or **widget.py** (a floating window, nothing else to install).

Your login never leaves your machine except to talk to claude.ai.

---

## Requirements

| | |
|---|---|
| **macOS** | Uses Keychain and launchd |
| **Python 3.10+** | Check with `python3 --version` |
| **A browser logged in to claude.ai** | See [Supported browsers](#supported-browsers) |
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

Log in to claude.ai in your browser, then run:

```bash
python3 fetch_usage.py --setup
```

It lists the claude.ai logins it found, tests the most recent one, and saves it to your Keychain:

```
claude.ai logins found in your browsers:
  chrome     Profile 4                    last used 2026-09-15 13:10
  zen        yr00ybqc.Default (release)   last used 2026-09-12 09:02

Testing…
  session=55%  weekly=54%
Setup complete. Saved to the macOS Keychain.
```

If your login is in Chrome, Arc, Brave, Edge, Vivaldi or Chromium, macOS asks for your **login keychain password** so setup can read "*Browser* Safe Storage". This only happens during `--setup`. The background fetcher never shows this dialog.

If no login is found (Safari, for example), setup asks you to paste your `sessionKey` instead. See [Other browsers](#other-browsers-safari-etc).

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

## Supported browsers

| Family | Browsers | Notes |
|---|---|---|
| **Chromium** | Chrome, Arc, Brave, Edge, Vivaldi, Chromium | Cookies are encrypted with a key in your Keychain, so macOS asks for your password. Read only during `--setup`: when the login expires, log in again and re-run `--setup` |
| **Firefox** | Firefox, Zen, LibreWolf, Floorp | Read directly with no prompts. Expired logins renew automatically |
| **Other** | Safari, Orion, anything else | Paste your key once (below) |

Every profile in every supported browser is checked, and the most recently used claude.ai login wins. To use only one browser:

```bash
python3 fetch_usage.py --setup --browser chrome
```

For the background fetcher, set `CLAUDE_BROWSER=chrome` instead. To see where logins were found without reading them:

```bash
python3 fetch_usage.py --browsers
```

### Other browsers (Safari, etc.)

1. Open claude.ai and open the developer tools. In Safari, first turn on **Settings → Advanced → Show features for web developers**.
2. Go to **Storage** (Safari) or **Application** (Chromium), then **Cookies → claude.ai**.
3. Copy the value of `sessionKey`.
4. Run `python3 fetch_usage.py --setup` and paste it when asked.

Pasted keys can't be renewed automatically. When the widget says your session expired, repeat these steps.

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
| **Use one browser only** | `--browser NAME` on the command line, or `CLAUDE_BROWSER=NAME`. Names: `chrome arc brave edge vivaldi chromium firefox zen librewolf floorp` |
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

- `Session expired`: log in to claude.ai in your browser again. Firefox-family logins are picked up on the next run. For Chromium browsers, also run `python3 fetch_usage.py --setup`.
- `Blocked by Cloudflare`: usually temporary. It clears up on a later run.
- `No claude.ai login found`: run `python3 fetch_usage.py --browsers` to see what was detected. If your browser isn't listed, paste your key (see [Other browsers](#other-browsers-safari-etc)).

**The "Chrome Safe Storage" password dialog rejects your password or keeps coming back**

This dialog only appears during `--setup`, once per Chromium browser, and each approval covers that single read.

If your Mac password is rejected, your *login keychain* password no longer matches your Mac password. That's common after a password reset. Click **Cancel**: setup skips that browser and moves on. Then either:
- log in to claude.ai in a Firefox-family browser, or
- paste your key (see [Other browsers](#other-browsers-safari-etc)).

**Always Allow** would stop future prompts, but it also lets any program that uses the `security` tool read that browser's key.

**The Übersicht widget is blank**

Open `http://127.0.0.1:41416` in a browser and check the console for build errors. If that page doesn't load at all, quit and reopen Übersicht.

**The Fable bar is missing**

The row only appears when the API reports a Fable limit for your plan.

**Restart the background fetcher**

```bash
launchctl kickstart -k gui/$(id -u)/com.claudeusagewidget.fetch
```

---

## Project layout

```
fetch_usage.py      fetches usage and writes usage_data.json
browser_cookies.py  finds claude.ai logins in installed browsers
widget.py           floating tkinter widget
set_usage.py        enter values by hand
start.sh            run the fetcher without launchd
launchd/            login agent template
ubersicht/          Übersicht desktop widget, with the mascot
extension/          experimental Zen/Firefox extension (needs a local receiver on :8765, not included)
```

---

## License

[MIT](LICENSE)
