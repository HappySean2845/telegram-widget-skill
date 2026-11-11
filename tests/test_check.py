import json
import os
import sys
import zlib

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = ROOT
sys.path.insert(0, os.path.join(SKILL, "scripts"))

from tgwidget.check import check_html, check_state  # noqa: E402
from tgwidget.report import Report  # noqa: E402
from tgwidget.urls import parse_allowlist  # noqa: E402

EXAMPLES = os.path.join(SKILL, "examples")
ALLOW = parse_allowlist("example.com t.me/ExampleBot *.docs.example.org")


def rules(html, allow=ALLOW):
    report = check_html(html.encode("utf-8") if isinstance(html, str) else html, allow)
    return {i.rule for i in report.errors}, report


def script(code):
    return "<div id=out></div><script>\n%s\n</script>" % code


# --- good widgets ---------------------------------------------------------

@pytest.mark.parametrize("name", sorted(f for f in os.listdir(EXAMPLES) if f.endswith(".html")))
def test_examples_pass_with_their_state(name):
    with open(os.path.join(EXAMPLES, name), "rb") as f:
        report = check_html(f.read(), [])
    with open(os.path.join(EXAMPLES, name[:-5] + ".json"), encoding="utf-8") as f:
        check_state("chat_data", f.read().strip(), [], report)
    assert report.ok, [i.to_dict() for i in report.errors]
    assert report.stats["compressed_bytes"] < 4096


GOOD = {
    "plain markup": "<h3>Order #1042</h3><p>2 × Margherita</p><p><b>Total: $23.50</b></p>",
    "allowlisted openLink": "<button onclick=\"TelegramWidget.openLink('https://example.com/orders/1')\">Track</button>",
    "allowlisted bot link": script("const TW = window.TelegramWidget;\n"
                                   "document.getElementById('out').onclick = () => "
                                   "TW.openTelegramLink('https://t.me/ExampleBot?start=x');"),
    "wildcard host": "<a href=\"https://api.docs.example.org/x\">docs</a>",
    "fragment link": "<a href=\"#more\">more</a><div id=more>x</div>",
    "data image": "<img src=\"data:image/png;base64,iVBORw0KGgo=\" alt=\"\">",
    "svg namespace": script("const s = document.createElementNS('http://www.w3.org/2000/svg', 'path');\n"
                            "s.setAttribute('d', 'M0 0L1 1');"),
    "inline svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 10 10\">"
                  "<use href=\"#c\"/><defs><circle id=c r=4 /></defs></svg>",
    "modern syntax": script("const a = window.TelegramWidget?.chatData ?? null;\n"
                            "try { JSON.parse(a); } catch { }\nconst b = [1, 2].at(-1);"),
    "guards": script("const TW = window.TelegramWidget;\nif (!TW) { }\n"
                     "if (typeof TW === 'undefined') { }\nconst d = TW && TW.chatData;"),
    "details open": "<details id=d><summary>more</summary>x</details>"
                    "<script>document.getElementById('d').open = true;</script>",
    "regex literal": script("const ok = /^https?:$/.test('x') ? 1 : 2;"),
    "css ok": "<style>@media (max-width:360px){.a{display:grid}}@media (prefers-color-scheme:dark){.a{color:"
              "light-dark(#000,#fff)}}.b{font:600 15px/1.3 system-ui,sans-serif;overflow:hidden;"
              "position:relative;width:50vw}button:disabled{opacity:1}</style><div class=a></div>",
    "data image in css": "<style>.a{background:url(data:image/png;base64,iVBORw0KGgo=)}</style>",
    "timers with functions": script("setTimeout(() => {}, 10); setInterval(function () {}, 1000);"),
    "computed index": script("const a = [1, 2, 3]; let i = 1; const x = a[i] + a[0];"),
}


@pytest.mark.parametrize("label", sorted(GOOD))
def test_good_widgets(label):
    errors, report = rules(GOOD[label])
    assert not errors, [i.to_dict() for i in report.errors]


# --- bad widgets: (html, the rule that must fire) --------------------------

BAD = {
    # links
    "link not on allowlist": ("<button onclick=\"TelegramWidget.openLink('https://evil.example.net/x')\">"
                              "x</button>", "link-not-allowed"),
    "a href elsewhere": ("<a href=\"https://evil.example.net/login\">x</a>", "link-not-allowed"),
    "http link": ("<a href=\"http://example.com/\">x</a>", "link-not-allowed"),
    "userinfo trick": ("<a href=\"https://example.com@evil.example.net/\">x</a>", "link-not-allowed"),
    "t.me other bot": (script("window.TelegramWidget.openTelegramLink('https://t.me/OtherBot');"),
                       "link-not-allowed"),
    "openLink to t.me": (script("window.TelegramWidget.openLink('https://t.me/ExampleBot');"),
                         "link-not-allowed"),
    "dynamic openLink": (script("const u = 'https://example.com/';\nwindow.TelegramWidget.openLink(u);"),
                         "link-dynamic"),
    "openLink concatenated": (script("window.TelegramWidget.openLink('https://example.com/' + x);"),
                              "link-dynamic"),
    "openLink alias": (script("const go = window.TelegramWidget.openLink;\ngo('https://example.com');"),
                       "link-dynamic"),
    "destructured openLink": (script("const { openLink } = window.TelegramWidget;"), "link-dynamic"),
    "window.open variable": (script("window.open(url);"), "link-dynamic"),
    "href assignment": (script("const a = document.createElement('a');\na.href = 'https://example.com';"),
                        "link-dynamic"),
    "setAttribute href": (script("el.setAttribute('href', 'https://example.com');"), "link-dynamic"),
    "setAttribute computed": (script("el.setAttribute(name, value);"), "link-dynamic"),
    "url in a string": (script("const msg = 'go to https://evil.example.net now';"), "link-not-allowed"),
    "escaped url in a string": (script("const u = '\\u0068ttps://evil.example.net';"), "link-not-allowed"),
    "url in text": ("<p>Claim at https://evil.example.net/airdrop</p>", "link-not-allowed"),
    "www in text": ("<p>visit www.evil-example.net today</p>", "link-not-allowed"),
    "javascript url": ("<a href=\"javascript:alert(1)\">x</a>", "link-not-allowed"),
    "img src remote": ("<img src=\"https://example.com/a.png\">", "html-external"),
    # code that hides what it does
    "eval": (script("const r = eval(code);"), "js-dynamic-code"),
    "new Function": (script("const f = new Function('return 1');"), "js-dynamic-code"),
    "atob": (script("const s = atob('aHR0cHM6Ly9ldmls');"), "js-dynamic-code"),
    "fromCharCode": (script("const s = String.fromCharCode(104, 116);"), "js-dynamic-code"),
    "constructor trick": (script("[].constructor.constructor('return 1')();"), "js-dynamic-code"),
    "dynamic import": (script("import('https://example.com/x.js');"), "js-dynamic-code"),
    "unicode escape name": (script("\\u0065val('1');"), "js-dynamic-code"),
    "string splice": (script("const k = 'open' + 'Link';"), "js-string-splice"),
    "computed string key": (script("const x = obj['open' + y];"), "js-computed-access"),
    "computed on widget": (script("const TW = window.TelegramWidget;\nTW[k]('https://example.com');"),
                           "js-computed-access"),
    "computed on window": (script("window[name]();"), "js-computed-access"),
    "widget passed around": (script("const TW = window.TelegramWidget;\nObject.keys(TW);"), "js-widget-escape"),
    "widget spread": (script("const TW = window.TelegramWidget;\nconst c = {...TW};"), "js-widget-escape"),
    "timer string": (script("setTimeout('go()', 10);"), "js-timer-string"),
    "innerHTML": (script("document.body.innerHTML = '<b>x</b>';"), "js-html-injection"),
    "insertAdjacentHTML": (script("el.insertAdjacentHTML('beforeend', s);"), "js-html-injection"),
    "document.write": (script("document.write('x');"), "js-html-injection"),
    "handler from string": (script("el.setAttribute('onclick', 'go()');"), "js-dynamic-code"),
    "script element": (script("const s = document.createElement('script');"), "js-element"),
    # network and navigation
    "fetch": (script("fetch('/api').then(r => r.json());"), "js-network"),
    "xhr": (script("const x = new XMLHttpRequest();"), "js-network"),
    "websocket": (script("new WebSocket('wss://example.com');"), "js-network"),
    "location": (script("window.location = 'https://example.com';"), "js-navigation"),
    "location.href": (script("location.href = 'x';"), "js-navigation"),
    "script src": ("<script src=\"https://cdn.example.com/chart.js\"></script>", "html-external"),
    # out of the widget profile
    "input": ("<input type=text>", "html-form-control"),
    "select": ("<select><option>a</option></select>", "html-form-control"),
    "textarea": ("<textarea></textarea>", "html-form-control"),
    "iframe": ("<iframe></iframe>", "html-unsupported"),
    "video": ("<video></video>", "html-unsupported"),
    "progress": ("<progress value=1></progress>", "html-unsupported"),
    "font tag": ("<font color=red>x</font>", "html-unsupported"),
    "legacy attr": ("<table bgcolor=red><tr><td>x</td></tr></table>", "html-attr-unsupported"),
    "tabindex": ("<div tabindex=0>x</div>", "html-attr-unsupported"),
    "svg data image": ("<img src=\"data:image/svg+xml;base64,PHN2Zz4=\">", "html-unsupported"),
    "svg clipPath": ("<svg><clipPath id=c></clipPath></svg>", "svg-unsupported"),
    "svg animate": ("<svg><circle r=1><animate attributeName=r /></circle></svg>", "svg-unsupported"),
    "svg foreignObject": ("<svg><foreignObject></foreignObject></svg>", "svg-unsupported"),
    "vh unit": ("<style>.a{height:50vh}</style>", "css-unsupported"),
    "dvh unit inline": ("<div style=\"min-height:100dvh\"></div>", "css-unsupported"),
    "sticky": ("<style>.a{position:sticky;top:0}</style>", "css-unsupported"),
    "overflow scroll": ("<style>.a{overflow-y:auto}</style>", "css-unsupported"),
    "display contents": ("<style>.a{display:contents}</style>", "css-unsupported"),
    "logical property": ("<style>.a{margin-inline:4px}</style>", "css-unsupported"),
    "columns": ("<style>.a{column-count:2}</style>", "css-unsupported"),
    "oklch": ("<style>.a{color:oklch(70% .1 200)}</style>", "css-unsupported"),
    "color-mix": ("<style>.a{color:color-mix(in srgb, red, blue)}</style>", "css-unsupported"),
    "text-shadow": ("<style>.a{text-shadow:0 1px 2px #000}</style>", "css-unsupported"),
    "line clamp": ("<style>.a{-webkit-line-clamp:2}</style>", "css-unsupported"),
    "3d transform": ("<style>.a{transform:rotateY(30deg)}</style>", "css-unsupported"),
    "grayscale": ("<style>.a{filter:grayscale(1)}</style>", "css-unsupported"),
    "clip-path": ("<style>.a{clip-path:circle(50%)}</style>", "css-unsupported"),
    "blend": ("<style>.a{mix-blend-mode:multiply}</style>", "css-unsupported"),
    "font-face": ("<style>@font-face{font-family:X;src:url(x.woff)}</style>", "css-unsupported"),
    "import": ("<style>@import url(https://fonts.example.com/x.css);</style>", "css-unsupported"),
    "container query": ("<style>@container (min-width:300px){.a{color:red}}</style>", "css-unsupported"),
    "hover media": ("<style>@media (hover:hover){.a{color:red}}</style>", "css-unsupported"),
    "print media": ("<style>@media print{.a{color:red}}</style>", "css-unsupported"),
    "has selector": ("<style>.a:has(.b){color:red}</style>", "css-unsupported"),
    "focus selector": ("<style>button:focus-visible{outline:0}</style>", "css-unsupported"),
    "nesting": ("<style>.a{color:red;.b{color:blue}}</style>", "css-unsupported"),
    "named font only": ("<style>.a{font-family:'Inter'}</style>", "css-unsupported"),
    "remote css url": ("<style>.a{background:url(https://example.com/bg.png)}</style>", "html-external"),
    "env name": ("<style>.a{padding:env(keyboard-inset-height)}</style>", "css-unsupported"),
    "alert": (script("alert('hi');"), "js-unsupported"),
    "clipboard": (script("navigator.clipboard.writeText('x');"), "js-unsupported"),
    "getImageData": (script("ctx.getImageData(0, 0, 1, 1);"), "js-unsupported"),
    "webgl": (script("canvas.getContext('webgl');"), "js-unsupported"),
    "keydown": (script("document.addEventListener('keydown', f);"), "js-event-unsupported"),
    "touch handler attr": ("<div ontouchstart=\"go()\">x</div>", "js-event-unsupported"),
    "sendMessage": (script("window.TelegramWidget.sendMessage('x');"), "js-unsupported"),
    # syntax and limits
    "syntax error": (script("const a = ;"), "js-syntax"),
    "unterminated string": (script("const a = 'x;"), "js-syntax"),
    "handler syntax error": ("<button onclick=\"go(\">x</button>", "js-syntax"),
    "nul": ("<p>a\x00b</p>", "html-invalid"),
    "big attribute": ("<img src=\"data:image/png;base64,%s\">" % ("A" * 9000), "limits"),
}


@pytest.mark.parametrize("label", sorted(BAD))
def test_bad_widgets(label):
    html, rule = BAD[label]
    errors, report = rules(html)
    assert rule in errors, (rule, [i.to_dict() for i in report.issues])


def test_empty_allowlist_refuses_every_link():
    errors, _ = rules("<a href=\"https://example.com/\">x</a>", allow=[])
    assert errors == {"link-not-allowed"}


def test_sizes_are_counted_like_the_server():
    # random text barely compresses: 8000 characters of it are well over 4096 bytes after zlib
    import random
    rnd = random.Random(1)
    text = "".join(rnd.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(8000))
    html = "<p>%s</p>" % text
    errors, report = rules(html)
    assert report.stats["compressed_bytes"] == len(zlib.compress(html.encode(), 9))
    assert "size-compressed" in errors
    errors, _ = rules("<p>%s</p>" % ("a" * 33000))
    assert "size-raw" in errors and "size-compressed" not in errors


def test_invalid_utf8():
    errors, _ = rules(b"<p>\xff\xfe</p>")
    assert "html-invalid" in errors


def test_state_checks():
    report = Report()
    check_state("chat_data", "x" * 1025, ALLOW, report)
    check_state("public_data", json.dumps({"u": "https://evil.example.net"}), ALLOW, report)
    found = {i.rule for i in report.errors}
    assert found == {"state-invalid", "link-not-allowed"}
    ok = Report()
    check_state("chat_data", json.dumps({"p": 1.5, "u": "https://example.com/x"}), ALLOW, ok)
    assert ok.ok


def test_requests_are_flagged_as_warning():
    _, report = rules(script("const TW = window.TelegramWidget;\nTW.request('refresh');"))
    assert report.ok
    assert any(w.rule == "js-requests" for w in report.warnings)
    assert report.stats["uses_requests"] is True


def test_findings_have_lines_and_hints():
    _, report = rules("<p>ok</p>\n<style>\n.a{\n  height: 40vh;\n}\n</style>")
    issue = next(i for i in report.errors if i.rule == "css-unsupported")
    assert issue.line == 4
    assert "hint" in issue.to_dict()


def test_alias_chains_and_returns_are_tracked():
    errors, _ = rules(script("const TW = window.TelegramWidget;\nconst X = TW;\nX[k]('https://example.com');"))
    assert "js-computed-access" in errors
    errors, _ = rules(script("const TW = window.TelegramWidget;\nfunction g() { return TW; }"))
    assert "js-widget-escape" in errors
