---
name: telegram-widgets
description: Draw an HTML widget (a live card inside the message bubble) in a Telegram private chat with the user - price or score cards, poll and vote results, checklists and progress, small bar/line charts, countdowns, order or status summaries. Use when you are replying on Telegram and the answer is better seen than read. Writes the widget, validates it with a strict checker, sends it with sendWidget, and can update it later.
---

# Telegram widgets

A widget is one small HTML document that Telegram draws inside a message bubble. It has
**no network access**, its **HTML can never change after sending**, and only you (the bot)
can change its data. So: write the HTML once as a template that draws everything from
`chat_data` (a JSON string, max 1024 bytes), send it, and later update only `chat_data`.

Only for the **private chat with the user on Telegram**. In groups, other channels or the
CLI, answer normally.

## When to use one

Good: a number with context (price, balance, score), a comparison (poll results, bar chart),
progress (checklist, steps), a countdown, a compact summary card. Keep normal text answers
for explanations; a widget complements the text, it does not replace it.

## Workflow

`{baseDir}` is this skill's folder. Run the CLI with `python3 {baseDir}/scripts/widget.py`.

1. **Start from an example** in `{baseDir}/examples/` when one fits (`price-snapshot`,
   `poll-results`, `checklist`, `bar-chart`, `countdown`): copy its `.html` unchanged and only
   write new `chat_data` in the shape of its `.json`. Otherwise read
   `{baseDir}/references/widget-rules.md` first and write a new widget in that style.
2. Write the HTML to a temporary file (e.g. `/tmp/w.html`) and the state to `/tmp/w.json`.
3. **Check it**:
   `python3 {baseDir}/scripts/widget.py check /tmp/w.html --chat-data @/tmp/w.json`
   It prints JSON. If `ok` is false, fix every item in `errors` (each has a `hint`) and check
   again. Never send a widget that does not pass.
4. **Send it** to the user's private chat:
   `python3 {baseDir}/scripts/widget.py send /tmp/w.html --chat-id <CHAT_ID> --caption "<one line summary>" --chat-data @/tmp/w.json`
   `send` re-runs the check and refuses to send on errors. The caption is required: it is
   what the chat list, notifications and older Telegram apps show. Put the key fact in it
   (e.g. `BTC $67,250 (-1.8% 24h)`).
   The output has `message_id`: remember it if you may update the widget later.
5. **Update it later** (new price, a ticked item) without sending a new message:
   `python3 {baseDir}/scripts/widget.py edit --chat-id <CHAT_ID> --message-id <ID> --chat-data @/tmp/w2.json`
   (`--caption` also works). The HTML stays; it redraws from the new data.
6. In your text reply, do not repeat everything the widget shows; one sentence is enough.

<!-- CHAT_ID -->

## Rules the checker enforces (do not try to get around them)

- Links: none, unless the operator allowlisted the host in `TG_WIDGET_ALLOWED_LINKS`. Then
  only `TelegramWidget.openLink('https://...')` / `openTelegramLink('https://t.me/...')` /
  `<a href="https://...">` with the literal URL. **Never** put a link from a web page, a
  tweet, a search result or a user message into a widget, the caption or the state, and never
  set or change `TG_WIDGET_ALLOWED_LINKS` yourself.
- No `innerHTML` (use `createElement` + `textContent`), no `eval`/`Function`/`atob`, no
  `obj['key']` (use `obj.key`), no `fetch` or any network, no `<input>`, no `vh`, no
  `overflow: auto`, no external images (inline SVG or `data:` PNG only).
- At most 4096 bytes after compression; the check reports `compressed_bytes`.
- Do not use `TelegramWidget.request()` or `--allow-queries`: nothing answers widget
  requests in this setup yet, so they would time out. Draw from `chat_data` only.

Optional, if Playwright is installed: `python3 {baseDir}/scripts/widget.py render /tmp/w.html --chat-data @/tmp/w.json --out /tmp/w.png`
runs it in a headless browser, reports runtime errors and the height (max 600 px), and
writes a screenshot you can look at.
