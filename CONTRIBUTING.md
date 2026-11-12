# Contributing

Thanks for helping. The most valuable contributions are new templates, validator rules grounded in
Telegram's specification, and reports of widgets the validator gets wrong.

## Set up

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev,render]"
.venv/bin/python -m playwright install chromium
.venv/bin/pytest
```

## Validator rules

- Base every rule on Telegram's [widget guide](https://core.telegram.org/bots/widgets) or the
  [Widget Sandbox](https://github.com/TelegramMessenger/widget-sandbox) profile, and link the
  section in the pull request.
- Add a sample the rule rejects to [`tests/test_check.py`](tests/test_check.py), and make sure the
  existing valid samples and templates still pass.
- Give the rule a `hint` in `scripts/tgwidget/report.py`: one sentence telling a model how to fix the
  widget.
- When in doubt about a link or dynamic code, refuse. The validator only lets through what it can
  prove.

## Templates

- One HTML file in `examples/` that draws everything from `chat_data`, plus a sample `.json` state.
- It must pass `check`, stay well under the size budget, and render below 560 px at 320 px wide in
  both light and dark (`widget.py render … --scheme dark`).
- Use Telegram's theme variables (`--tg-theme-*`) instead of fixed colors, and add the template to
  the table in both READMEs.

## Pull requests

- Keep each pull request to one change, with tests.
- Update `README.md` and `README.zh-CN.md` together when behavior or usage changes.
- Security issues go through [private reporting](SECURITY.md), not public issues.
