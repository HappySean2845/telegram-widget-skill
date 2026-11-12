# Security policy

This project exists to stop an AI agent from sending a Telegram widget it should not send. A way
around that is a security bug, and reports are very welcome.

## What to report

- A widget that passes `check` or `send` but opens, links to or shows a URL whose host is not on
  `TG_WIDGETS_ALLOWED_LINKS`, or that assembles a URL at runtime.
- A widget that passes `check` but runs code the validator says it refuses, such as `eval`,
  `Function` or `innerHTML`.
- Text in a caption, `chat_data` or `public_data` that gets a URL past the scan.
- Any output, error message or log line of the CLI that contains the bot token.

## Out of scope

- An agent that calls the Bot API directly from its own shell with the bot token. The README's
  [security model](README.md#security-model) explains this boundary.
- Differences between `render` (headless Chromium) and how the Telegram apps draw a widget.
- Bugs in Telegram's apps or servers. Please report those to Telegram.

## How to report

Please report privately: open the repository's **Security** tab and choose **Report a
vulnerability**. Include the smallest widget or command that shows the problem and the output you
got. Please do not open a public issue for a bypass before a fix is released.

Every fixed bypass gets a regression sample in [`tests/test_check.py`](tests/test_check.py).

## Supported versions

Fixes land on `main`. Install from `main` (or the latest release) to get them.
