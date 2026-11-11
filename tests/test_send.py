import json
import os
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = ROOT
sys.path.insert(0, os.path.join(SKILL, "scripts"))

from tgwidget.cli import main  # noqa: E402

TOKEN = "123456789:AAH-secret-token-value-0123456789"
EXAMPLE = os.path.join(SKILL, "examples", "checklist.html")
STATE = os.path.join(SKILL, "examples", "checklist.json")


class FakeBotApi:
    """Records calls; answers like the Bot API."""

    def __init__(self):
        self.calls = []
        self.reply = None  # (status, body) to force an answer
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length) or b"{}")
                method = self.path.rsplit("/", 1)[-1]
                outer.calls.append((self.path, method, body))
                if outer.reply:
                    status, payload = outer.reply
                elif method == "sendWidget":
                    status, payload = 200, {"ok": True, "result": {
                        "message_id": 42, "chat": {"id": body["chat_id"], "type": "private"}}}
                else:
                    status, payload = 200, {"ok": True, "result": True}
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:%d" % self.server.server_address[1]

    def close(self):
        self.server.shutdown()


@pytest.fixture
def api(monkeypatch):
    fake = FakeBotApi()
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    monkeypatch.setenv("TG_WIDGETS_API_BASE", fake.base)
    monkeypatch.delenv("TG_WIDGETS_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TG_WIDGETS_ALLOWED_LINKS", raising=False)
    for name in ("TG_WIDGETS_CHAT_ID", "HERMES_SESSION_PLATFORM", "HERMES_SESSION_CHAT_ID",
                 "HERMES_SESSION_THREAD_ID", "OPENCLAW_CHANNEL_CONTEXT"):
        monkeypatch.delenv(name, raising=False)
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    yield fake
    fake.close()


def run(capsys, *argv):
    code = main(list(argv))
    out = capsys.readouterr()
    assert TOKEN not in out.out and TOKEN not in out.err
    assert "secret-token" not in out.out and "secret-token" not in out.err
    return code, json.loads(out.out)


def test_send_ok(api, capsys):
    code, out = run(capsys, "send", EXAMPLE, "--chat-id", "1001", "--caption", "Release v1.2: 3 of 5 done",
                    "--chat-data", "@" + STATE)
    assert code == 0 and out["sent"] and out["message_id"] == 42
    path, method, body = api.calls[0]
    assert method == "sendWidget" and path.endswith("/bot%s/sendWidget" % TOKEN)
    assert body["chat_id"] == 1001 and body["caption"].startswith("Release")
    assert json.loads(body["chat_data"])["t"] == "Release v1.2"
    assert "allow_queries" not in body  # off unless asked for


def test_send_refuses_a_failing_widget_without_calling_telegram(api, capsys, tmp_path):
    bad = tmp_path / "bad.html"
    bad.write_text("<button onclick=\"TelegramWidget.openLink('https://evil.example.net')\">Claim</button>")
    code, out = run(capsys, "send", str(bad), "--chat-id", "1001", "--caption", "x")
    assert code == 1 and out["sent"] is False
    assert {e["rule"] for e in out["errors"]} == {"link-not-allowed"}
    assert api.calls == []


def test_send_refuses_bad_state_and_caption_links(api, capsys):
    code, out = run(capsys, "send", EXAMPLE, "--chat-id", "1001", "--caption", "see https://evil.example.net",
                    "--chat-data", '{"t":"x","i":[]}')
    assert code == 1 and api.calls == []
    code, out = run(capsys, "send", EXAMPLE, "--chat-id", "1001", "--caption", "ok",
                    "--chat-data", "x" * 2000)
    assert code == 1 and "state-invalid" in {e["rule"] for e in out["errors"]}


def test_send_needs_a_caption_and_a_private_chat(api, capsys):
    code, out = run(capsys, "send", EXAMPLE, "--chat-id", "1001")
    assert code == 2 and "caption" in out["errors"][0]["message"]
    code, out = run(capsys, "send", EXAMPLE, "--chat-id", "-100123", "--caption", "x")
    assert code == 2 and "private chat" in out["errors"][0]["message"]
    assert api.calls == []


def test_telegram_error_shows_only_the_description(api, capsys):
    api.reply = (400, {"ok": False, "error_code": 400,
                       "description": "Bad Request: INPUT_MEDIA_WIDGET_TOO_LARGE"})
    code, out = run(capsys, "send", EXAMPLE, "--chat-id", "1001", "--caption", "x")
    assert code == 1
    assert out["telegram_error"] == {"description": "Bad Request: INPUT_MEDIA_WIDGET_TOO_LARGE",
                                     "error_code": 400}


def test_network_error_does_not_leak_the_token(monkeypatch, capsys):
    with socket.socket() as s:  # a port nothing listens on
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    monkeypatch.setenv("TG_WIDGETS_API_BASE", "http://127.0.0.1:%d" % port)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    code, out = run(capsys, "send", EXAMPLE, "--chat-id", "1001", "--caption", "x")
    assert code == 1 and "network error" in out["telegram_error"]["description"]


def test_dry_run_sends_nothing(api, capsys):
    code, out = run(capsys, "send", EXAMPLE, "--chat-id", "1001", "--caption", "x", "--dry-run")
    assert code == 0 and out["dry_run"] and api.calls == []


def test_edit_state_and_not_modified(api, capsys):
    code, out = run(capsys, "edit", "--chat-id", "1001", "--message-id", "42", "--chat-data", '{"t":"x","i":[]}')
    assert code == 0 and out["edited"] == ["state"]
    assert api.calls[-1][1] == "editMessageWidgetData"
    assert api.calls[-1][2] == {"chat_id": 1001, "message_id": 42, "chat_data": '{"t":"x","i":[]}'}
    api.reply = (400, {"ok": False, "error_code": 400, "description": "Bad Request: message is not modified"})
    code, out = run(capsys, "edit", "--chat-id", "1001", "--message-id", "42", "--chat-data", '{"t":"x","i":[]}')
    assert code == 0 and out["edited"] == ["state (unchanged)"]


def test_edit_refuses_links_in_state(api, capsys):
    code, out = run(capsys, "edit", "--chat-id", "1001", "--message-id", "42",
                    "--chat-data", '{"u":"https://evil.example.net"}')
    assert code == 1 and api.calls == []


def test_missing_token(monkeypatch, capsys):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TG_WIDGETS_BOT_TOKEN", raising=False)
    code, out = run(capsys, "send", EXAMPLE, "--chat-id", "1001", "--caption", "x")
    assert code == 2 and "bot token" in out["errors"][0]["message"]


def test_openclaw_style_chat_reference(api, capsys):
    code, out = run(capsys, "send", EXAMPLE, "--chat-id", "telegram:1001:topic:7", "--caption", "x")
    assert code == 0
    body = api.calls[-1][2]
    assert body["chat_id"] == 1001 and body["message_thread_id"] == 7


def test_hermes_session_is_the_default_and_the_only_target(api, capsys, monkeypatch):
    monkeypatch.setenv("HERMES_SESSION_PLATFORM", "telegram")
    monkeypatch.setenv("HERMES_SESSION_CHAT_ID", "1001")
    code, out = run(capsys, "send", EXAMPLE, "--caption", "x")
    assert code == 0 and api.calls[-1][2]["chat_id"] == 1001
    code, out = run(capsys, "send", EXAMPLE, "--chat-id", "2002", "--caption", "x")
    assert code == 2 and "not the current conversation" in out["errors"][0]["message"]
    code, out = run(capsys, "edit", "--chat-id", "2002", "--message-id", "5", "--chat-data", "{}")
    assert code == 2
    assert len(api.calls) == 1


def test_not_telegram(api, capsys, monkeypatch):
    monkeypatch.setenv("HERMES_SESSION_PLATFORM", "discord")
    monkeypatch.setenv("HERMES_SESSION_CHAT_ID", "1001")
    code, out = run(capsys, "send", EXAMPLE, "--caption", "x")
    assert code == 2 and "not Telegram" in out["errors"][0]["message"]
    assert api.calls == []


def test_dedicated_token_variable_wins(api, capsys, monkeypatch):
    monkeypatch.setenv("TG_WIDGETS_BOT_TOKEN", "42:other-token-abcdefgh")
    assert main(["send", EXAMPLE, "--chat-id", "1001", "--caption", "x"]) == 0
    assert "other-token" not in capsys.readouterr().out
    assert "/bot42:other-token-abcdefgh/" in api.calls[-1][0]
