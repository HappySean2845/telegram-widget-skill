# Verification record

What has been tested, how, and what has not. Newest results first.

## ClawHub (2026-11-12)

| Version | Result |
|---|---|
| 1.0.0 | ClawScan `suspicious`: `edit` did not limit itself to private chats, a Hermes topic could be overridden, and `TG_WIDGETS_API_BASE` could send the token to any host. All three fixed in 1.0.1. |
| 1.0.1 | ClawScan `suspicious`: `const w = window; w.open(url)` passed the validator. Fixed in 1.0.2, with 17 bypass forms as regression tests. |
| 1.0.2 | ClawScan `benign`, security audit [Safe](https://clawhub.ai/happysean2845/skills/telegram-widget-skill/security-audit?version=1.0.2). Installs from ClawHub verified in OpenClaw 2026.11.3 (`openclaw skills install @happysean2845/telegram-widget-skill`, ready) and Hermes Agent v0.23.1 (`hermes skills install clawhub/telegram-widget-skill`, scan `SAFE`, allowed). |

The remaining SkillSpector notes on 1.0.2 describe what the tool is for, not defects: the bot token
reaches the network (it is sent to `api.telegram.org`, which is the point), the CLI reads environment
variables and writes a temporary file for `node --check`, it runs `node` with an argument list (no
shell), and an error message contains the words "allowlist is empty".

## Real Telegram (2026-11-11)

A test bot in a private chat, against Telegram's production servers.

| Check | Result |
|---|---|
| `send` (`sendWidget`) with the price template and live NVDA data | Accepted; the widget displays correctly in the Telegram app |
| `edit` (`editMessageWidgetData` + `editMessageCaption`) with a newer quote | Accepted by the server |
| Size limit, sent straight to the API around the boundary | 4,096 bytes after `zlib.compress(html, 9)` accepted, 4,097 refused with `INPUT_MEDIA_WIDGET_TOO_LARGE`; the validator draws the line at the same byte |

## Agent frameworks

Both installs ran from this GitHub repository in an isolated home directory.

| Framework | Verified | Not yet verified |
|---|---|---|
| Hermes Agent v0.23.1 | `hermes skills install HappySean2845/telegram-widget-skill/` passes the install scan (`safe`); the skill loads with its directory and required variable; after `hermes config set`, `TG_WIDGETS_BOT_TOKEN` reaches terminal subprocesses while `TELEGRAM_BOT_TOKEN` does not | A full agent turn that ends in a sent widget; `widget_query` never reaches Hermes |
| OpenClaw 2026.11.3 | `openclaw skills install git:…` succeeds; `skills info` shows the skill ready, gated on `python3`, primary env `TG_WIDGETS_BOT_TOKEN`; the installed CLI runs on macOS's Python 3.9 and resolves `telegram:<id>` chat references | A full agent turn that ends in a sent widget; `widget_query` is not routed to skills |

## Automated tests

Run in CI on every push (Python 3.9, 3.11, 3.12, 3.13; plus a job with no JavaScript engine and a
render job in headless Chromium).

| Suite | Coverage |
|---|---|
| Validator | Every template, a set of valid widgets, and one invalid widget per rule: links, dynamic code, the widget profile, sizes, state |
| `send` / `edit` | Against a local fake Bot API: payloads, refusal before any request, Telegram errors, network errors, and the bot token never appearing in output |
| Render | Every template in headless Chromium (dark theme) runs without errors and stays within 560 px at 320 px wide; runtime errors, network attempts and overflowing height are caught; screenshots are uploaded as CI artifacts |
| JavaScript engines | QuickJS, Node and the structural fallback each reject a syntax error on the right line and accept valid code; a QuickJS-only gap (newer syntax Node accepts) is reported as a warning, not an error |
