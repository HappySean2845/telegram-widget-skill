import os
import shutil
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skills", "telegram-widgets", "scripts"))

from tgwidget import jssyntax  # noqa: E402

BROKEN = "const a = 1;\nconst b = ;\n"
FINE = "const a = window.TelegramWidget?.chatData ?? null;\ntry { JSON.parse(a); } catch { }\n"


@pytest.mark.skipif(jssyntax.quickjs is None, reason="quickjs not installed")
def test_quickjs_engine(monkeypatch):
    monkeypatch.setattr(jssyntax.shutil, "which", lambda name: None)
    assert jssyntax.available_engine() == "quickjs"
    msg, line, severity, engine = jssyntax.check_syntax(BROKEN)
    assert "SyntaxError" in msg and line == 2 and severity == "error"
    assert jssyntax.check_syntax(FINE) is None


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_node_engine(monkeypatch):
    monkeypatch.setattr(jssyntax, "quickjs", None)
    assert jssyntax.available_engine() == "node"
    msg, line, severity, engine = jssyntax.check_syntax(BROKEN)
    assert "SyntaxError" in msg and line == 2 and engine == "node"
    assert jssyntax.check_syntax(FINE) is None


def test_basic_engine(monkeypatch):
    monkeypatch.setattr(jssyntax, "quickjs", None)
    monkeypatch.setattr(jssyntax.shutil, "which", lambda name: None)
    assert jssyntax.available_engine() == "basic"
    assert jssyntax.check_syntax("const a = 'x;")[1] == 1
    assert jssyntax.check_syntax("if (a) {\n  b(\n}")[0].startswith("SyntaxError")
    assert jssyntax.check_syntax(FINE) is None


@pytest.mark.skipif(jssyntax.quickjs is None or shutil.which("node") is None, reason="needs quickjs and node")
def test_old_quickjs_gap_is_only_a_warning():
    # class static blocks: newer than the bundled QuickJS, accepted by Node
    msg, line, severity, engine = jssyntax.check_syntax("class A { static { this.x = 1; } }")
    assert severity == "warning"
