# telegram-widget-skill

**English** | [简体中文](README.zh-CN.md)

Let your Telegram AI agent draw **HTML widgets** inside the chat: price cards, poll results,
checklists, small charts, countdowns. The agent writes the widget, a strict checker validates
it, and only then is it sent with Telegram's `sendWidget`.

Works as a skill for **[Hermes Agent](https://github.com/NousResearch/hermes-agent)** and
**[OpenClaw](https://github.com/openclaw/openclaw)** (both read the same `SKILL.md`), and as a
plain CLI for any other bot.

<p align="center"><img src="docs/examples.png" width="680" alt="The five example widgets, light and dark"></p>

## Why

On November 9, 2026 Telegram shipped [Bot API 10.4](https://core.telegram.org/bots/api-changelog):
bots can now send a widget, one self-contained HTML document that runs inside the message
bubble on every Telegram app. Models write HTML well, but widgets have sharp edges:

- the app **silently removes** everything outside the "widget profile" (no `vh`, no inputs,
  no `position: sticky`, no network, no external images, ...), so a widget that looks fine in a
  browser comes out broken in Telegram;
- the server refuses anything over **4096 bytes after zlib**, and the HTML can **never be
  changed** after sending;
- a model that read a web page or a tweet can be talked into putting a **phishing link** into a
  pretty card that the user then taps.

This skill gives the agent the rules, a checker that returns machine-readable errors it can fix,
and a sender that refuses to send anything the checker rejects.

## What is in the skill

The repository root is the skill folder (OpenClaw installs from git need `SKILL.md` there).

```
SKILL.md                    when and how the agent should use widgets
references/widget-rules.md  the widget rules, condensed for a model
examples/*.html, *.json     five widgets drawn from chat_data, with sample state
scripts/widget.py           the CLI (Python 3.9+, standard library only)
scripts/tgwidget/           its code
```

```bash
python3 scripts/widget.py check  card.html --chat-data @state.json   # validate, JSON out
python3 scripts/widget.py render card.html --out card.png             # optional: headless Chromium
python3 scripts/widget.py send   card.html --chat-id 123 --caption "BTC $67,250" --chat-data @state.json
python3 scripts/widget.py edit   --chat-id 123 --message-id 456 --chat-data @new-state.json
```

The bot token comes from `TG_WIDGETS_BOT_TOKEN`, else `TELEGRAM_BOT_TOKEN`. No output ever
contains it: errors carry only Telegram's `description`, never an HTTP library's message
(which includes the request URL, and the URL includes the token).

## The checker

`check` prints one JSON object: `ok`, `errors`, `warnings` (each with `rule`, `message`,
`line` and a `hint` telling the model how to fix it) and `stats` (sizes, budget left).
`send` runs the same check (plus the state and the caption) and sends nothing unless it passes.

| Area | What it enforces |
|---|---|
| Size | ≤ 32768 bytes of UTF-8, ≤ 4096 bytes after `zlib.compress(html, 9)` (counted exactly like the server), no NUL, valid UTF-8; `chat_data`/`public_data` ≤ 1024 bytes |
| HTML / SVG | no form controls, media, iframes, `<script src>`, remote images, `data:` SVG images, presentational or focus attributes, `clipPath`/`mask`/SMIL/`foreignObject`, ... |
| CSS | no `vh`-family units, `overflow: auto/scroll`, `position: sticky`, logical properties, multi-column, `oklch()`/`color-mix()`, `text-shadow`, line clamp, 3D transforms, filters other than blur/brightness/drop-shadow, `clip-path`, masks, blend modes, named fonts, `@font-face`/`@import`/`@container`/`@layer`, nesting, `:has()`/`:focus`, `@media (hover/pointer/print)`, remote `url()` |
| JavaScript | syntax (QuickJS, else Node, else a structural check); no network APIs, navigation, dialogs, clipboard, canvas read-back, WebGL, touch/keyboard/scroll events |
| **Links** | see below |
| Limits | 2000 nodes, 400 CSS rules, 32 `@keyframes`, 8 K characters per attribute (this includes `data:` image URLs) |

### Links: if the checker cannot prove where a link goes, it refuses the widget

- Links may only be opened with **one literal URL** in one of four forms:
  `TelegramWidget.openLink('https://…')`, `TelegramWidget.openTelegramLink('https://t.me/…')`,
  `window.open('https://…')` or `<a href="https://…">`.
- The host must be on the **operator's allowlist**, `TG_WIDGETS_ALLOWED_LINKS`
  (`example.com`, `*.example.com`, `t.me/YourBot`). **Empty by default: no links at all.**
  There is no command-line flag for it, because the model writes the command line.
- Any URL-looking text anywhere (strings, attributes, text, CSS, state, caption) must pass the
  same allowlist, after decoding escapes (`'https://…'` is `https://…`).
- Everything that could assemble a name or a URL out of pieces is refused: `eval`, `Function`,
  `.constructor`, `atob`, `String.fromCharCode`, `import()`, string-argument timers, unicode
  escapes in identifiers, `'a' + 'b'` literal splicing, computed access with string keys or on
  `window`/`document`/`TelegramWidget`, passing `TelegramWidget` around, `innerHTML` and every
  other HTML-from-string API, setting `href`/`src`/`on*` from code.

**Threat model.** This is a guardrail for an agent that follows its skill, so that content it
read cannot steer it into shipping a phishing card. It is not a sandbox against the agent
itself: an agent with an unrestricted shell and the bot token can call the Bot API directly.
If you need that guarantee, keep the token out of the agent's shell and expose `send` as the
only way to reach Telegram.

## Install

Both frameworks read the same `SKILL.md`. The skill needs `python3` (3.9+) on the machine
where the agent runs its shell commands, and the token of the bot your agent already uses.
`quickjs` (`pip install quickjs`) makes the JavaScript syntax check exact; without it the
checker falls back to `node --check`, then to a structural check.

### Hermes Agent

```bash
hermes skills install HappySean2845/telegram-widget-skill/
hermes config set TG_WIDGETS_BOT_TOKEN <the same token as TELEGRAM_BOT_TOKEN>
hermes config set TG_WIDGETS_ALLOWED_LINKS "example.com t.me/YourBot"   # optional: hosts widgets may link to
```

- Hermes removes `TELEGRAM_BOT_TOKEN` from the environment of every tool subprocess, on
  purpose, and a skill cannot ask for it back. So the skill declares its own variable,
  `TG_WIDGETS_BOT_TOKEN`, which Hermes passes to the terminal once the skill is loaded.
- The chat comes from the session: Hermes puts the current chat id into the terminal's
  environment (`HERMES_SESSION_CHAT_ID`), and `send` uses it. A `--chat-id` naming another
  chat is refused.
- Hermes scans community skills on install; this one gets a `safe` verdict. The install
  downloads the repository file by file through the GitHub API, which takes a minute; if it
  stops on the API rate limit, set `GITHUB_TOKEN` or log in with `gh`.
- The skill shows up as `telegram-widgets` (its folder is named after the repository).

### OpenClaw

```bash
openclaw skills install git:HappySean2845/telegram-widget-skill@main
```

Then give the skill the bot token, either as the skill's key in `openclaw.json`:

```json
{ "skills": { "entries": { "telegram-widgets": { "apiKey": "<bot token>" } } } }
```

(`apiKey` also takes a SecretRef such as `{"source": "env", "provider": "default", "id": "TELEGRAM_BOT_TOKEN"}`),
or nothing at all if the gateway already gets `TELEGRAM_BOT_TOKEN` from its environment:
`exec` on the gateway host inherits it. A token that is only in `channels.telegram.botToken`
is not visible to commands, so then set `apiKey`. Optional link allowlist:
`skills.entries.telegram-widgets.env.TG_WIDGETS_ALLOWED_LINKS`.

- The model passes the chat from the turn's conversation info as is
  (`--chat-id telegram:123456789`); `send` understands that form.
- With `exec` in a Docker sandbox, neither the token nor `python3` from the host are there.
- OpenClaw's `main` branch (not yet in a release as of 2026-11-11) has its own `show_widget`
  tool behind `channels.telegram.widgets: true`, which also routes taps back to the agent.
  There, the skill tells the model to `check` with this skill and send with `show_widget`.

### Any other bot

The CLI is plain Python: `pip install "git+https://github.com/HappySean2845/telegram-widget-skill"`
gives you `tgwidget check|render|send|edit`, or run `scripts/widget.py` from a checkout.

## Limits and roadmap

- **Production widgets only work in the private chat with the bot.** Groups, inline mode and
  forwards are test-server only for now; `send` refuses non-private chat ids unless
  `--test-env` is given.
- **No interactive requests yet.** A widget can call `TelegramWidget.request()`, which reaches
  the bot as a `widget_query` update that must be answered within 15 seconds. No skill can
  answer it today: Hermes never receives the update (it subscribes to python-telegram-bot's
  list of update types, which predates widgets), OpenClaw releases up to 2026.11.3 do not
  subscribe to it, and OpenClaw's `main` answers every `widget_query` itself, with no data,
  forwarding taps on its own `show_widget` widgets to the agent. So v1 widgets are snapshots
  drawn from `chat_data`, and the agent updates them with `edit` (`editMessageWidgetData`).
  `--allow-queries` exists for bots that do handle `widget_query`. Next: a Hermes plugin that
  subscribes to `widget_query` and answers it, and the same hook for OpenClaw.
- The render check approximates Telegram's default styles; a browser draws things Telegram
  removes, so `render` complements `check`, it does not replace it.
- Which Telegram app versions support widgets is not published; apps without support show
  "unsupported message" plus the caption, which is why `send` requires a caption.

## What has been tested

| | Status |
|---|---|
| Checker and CLI | 149 tests: every example, a set of good widgets, and one bad widget per rule (links, dynamic code, profile, sizes) |
| `send` / `edit` | against a local fake Bot API: payloads, refusal before any request, Telegram errors, network errors, the token never in the output |
| Render | the examples in headless Chromium, light and dark, under 560 px at 320 px width |
| OpenClaw 2026.11.3 | `skills install git:…` from this repository, `skills info` shows it ready, gated on `python3`, primary env `TG_WIDGETS_BOT_TOKEN`; the installed CLI runs with macOS's Python 3.9 |
| Hermes Agent v0.23.1 | `skills install HappySean2845/telegram-widget-skill/` passes the install scan (`safe`); the skill loads with its directory and required variable; after `hermes config set`, `TG_WIDGETS_BOT_TOKEN` reaches terminal subprocesses while `TELEGRAM_BOT_TOKEN` does not |
| The real Bot API | 2026-11-11, private chat with a test bot: `send` and `edit` accepted by Telegram (`sendWidget`, `editMessageWidgetData`, `editMessageCaption`); the size limit matches the checker to the byte: 4096 bytes after `zlib` level 9 accepted, 4097 refused with `INPUT_MEDIA_WIDGET_TOO_LARGE` |
| A real Telegram app | 2026-11-11: the price-snapshot example, drawn from live NVDA data, displays correctly in the chat |
| A full agent turn in either framework | not yet |

## Development

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev,render]"
.venv/bin/python -m playwright install chromium
.venv/bin/pytest
```

## Credits

The widget rules are adapted from Telegram's guide
[Telegram Widgets](https://core.telegram.org/bots/widgets.md), section "Writing widgets with
an LLM". This project is not affiliated with Telegram, Nous Research or OpenClaw.

MIT License.
