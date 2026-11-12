import json
import os
import sys
from pathlib import Path

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = ROOT
sys.path.insert(0, os.path.join(SKILL, "scripts"))

playwright_api = pytest.importorskip("playwright.sync_api")

from tgwidget.render import _stub, render  # noqa: E402

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


@pytest.mark.parametrize("scheme", ["dark", "light"])
def test_token_comparison_columns_share_text_anchors(scheme):
    html = (Path(EXAMPLES) / "token-comparison.html").read_text(encoding="utf-8")
    state = (Path(EXAMPLES) / "token-comparison.json").read_text(encoding="utf-8")
    rows = json.loads(state)["rows"]
    with playwright_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(color_scheme=scheme)
        page.set_content("<!doctype html>" + _stub(state, None, scheme) + html)
        for width in (280, 320, 428):
            page.set_viewport_size({"width": width, "height": 50})
            measured = page.locator(".row").evaluate_all("""rows => rows.map(row =>
              Array.from(row.children, cell => {
                const range = document.createRange();
                range.selectNodeContents(cell);
                const rect = range.getBoundingClientRect();
                return {text: cell.textContent, left: rect.left, right: rect.right};
              }))""")
            assert len(measured) == 1 + len(rows)
            header = measured[0]
            center = (header[1]["left"] + header[1]["right"]) / 2
            assert abs(center - width / 2) < 1
            assert [cell["text"] for cell in header] == ["", "BTC", "ETH"]
            for (label, left, right), sample in zip(measured[1:], rows):
                assert [label["text"], left["text"], right["text"]] == [
                    sample["metric"], sample["left"] if sample["left"] is not None else "—", sample["right"]]
                assert abs((left["left"] + left["right"]) / 2 - center) < 1
                assert abs(right["right"] - header[2]["right"]) < 1
                assert label["right"] <= left["left"] <= left["right"] <= right["left"]
            assert page.evaluate("document.documentElement.scrollHeight") < 560
        browser.close()
