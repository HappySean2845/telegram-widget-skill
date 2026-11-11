import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "skills", "telegram-widgets")
sys.path.insert(0, os.path.join(SKILL, "scripts"))

pytest.importorskip("playwright.sync_api")

from tgwidget.render import render  # noqa: E402

EXAMPLES = os.path.join(SKILL, "examples")


@pytest.mark.parametrize("name", sorted(f[:-5] for f in os.listdir(EXAMPLES) if f.endswith(".html")))
def test_examples_render_cleanly(name, tmp_path):
    with open(os.path.join(EXAMPLES, name + ".html"), encoding="utf-8") as f:
        html = f.read()
    with open(os.path.join(EXAMPLES, name + ".json"), encoding="utf-8") as f:
        state = f.read().strip()
    out = tmp_path / (name + ".png")
    result = render(html, str(out), chat_data=state, scheme="dark")
    assert result["ok"], result
    assert 50 <= result["stats"]["height"] <= 560
    assert out.stat().st_size > 1000


def test_runtime_error_network_and_height_are_caught():
    result = render("<script>fetch('https://example.com/x').catch(() => {}); undefinedFn();</script>"
                    "<div style='height:900px'></div>", None)
    rules = {e["rule"] for e in result["errors"]}
    assert rules == {"render-error", "render-network", "render-height"}


def test_state_reaches_the_widget():
    result = render("<p id=o></p><script>document.getElementById('o').textContent = "
                    "JSON.parse(TelegramWidget.chatData).x; TelegramWidget.ready();</script>",
                    None, chat_data='{"x":"hello"}')
    assert result["ok"] and ["ready", None] in result["stats"]["calls_at_start"]
