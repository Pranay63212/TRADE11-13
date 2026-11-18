"""ntfy client sends the right HTTP request (tested against a local fake server)."""
import os, sys, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from bot.notify import Ntfy  # noqa: E402

got = []


class H(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"])).decode()
        got.append((self.path, self.headers["Title"], self.headers["Priority"], body))
        self.send_response(200); self.end_headers(); self.wfile.write(b"{}")

    def log_message(self, *a):
        pass


def test_ntfy_post_and_throttle():
    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    n = Ntfy("my-topic", server=f"http://127.0.0.1:{srv.server_port}")
    n("QQQ LONG entered", "10 @ 500.00", priority="high")
    n("err", "x", throttle_key="k"); n("err", "x", throttle_key="k")   # 2nd is throttled
    srv.shutdown()
    assert got[0] == ("/my-topic", "QQQ LONG entered", "high", "10 @ 500.00")
    assert len(got) == 2


def test_ntfy_disabled_and_failure_safe():
    Ntfy(None)("t", "m")                                   # no topic: silently off
    Ntfy("t", server="http://127.0.0.1:9", log=lambda *_: None)("t", "m")   # unreachable: no crash


def test_curl_fallback_when_python_https_fails(monkeypatch):
    """If urllib fails (e.g. certificate error), alerts go out via curl instead."""
    import shutil
    import pytest
    if not shutil.which("curl"):
        pytest.skip("curl not installed")
    import bot.notify as nm

    def boom(*a, **k):
        raise OSError("certificate verify failed: certificate has expired")
    monkeypatch.setattr(nm.urllib.request, "urlopen", boom)
    got.clear()
    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    ok = Ntfy("t2", server=f"http://127.0.0.1:{srv.server_port}")("Bot test", "line1\nline2")
    srv.shutdown()
    assert ok and got[0] == ("/t2", "Bot test", "default", "line1\nline2")
