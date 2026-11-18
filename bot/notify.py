"""
Push notifications to your phone via ntfy (https://ntfy.sh).

Anyone who knows your topic name can read (and send to) it, so pick a long
random topic name and treat it like a password.
"""
from __future__ import annotations

import shutil
import ssl
import subprocess
import time
import urllib.request

try:                                    # use the same up-to-date CA bundle as requests/alpaca-py
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:                       # certifi missing: fall back to the system store
    _SSL_CTX = ssl.create_default_context()


class Ntfy:
    def __init__(self, topic: str | None, server: str = "https://ntfy.sh", log=print):
        self.topic, self.server, self.log = topic, server.rstrip("/"), log
        self._last: dict[str, float] = {}

    def __call__(self, title: str, message: str, priority: str = "default",
                 tags: str = "", throttle_key: str | None = None, throttle_s: int = 600) -> bool:
        """Returns True only if ntfy accepted the message."""
        if not self.topic:
            return False
        if throttle_key:                                   # avoid spamming repeated errors
            now = time.time()
            if now - self._last.get(throttle_key, 0) < throttle_s:
                return False
            self._last[throttle_key] = now
        req = urllib.request.Request(
            f"{self.server}/{self.topic}", data=message.encode("utf-8"), method="POST",
            headers={"Title": title.encode("ascii", "ignore").decode(),
                     "Priority": priority, "Tags": tags})
        try:
            urllib.request.urlopen(req, timeout=5, context=_SSL_CTX).read()
            return True
        except Exception as e:                             # never let alerts crash trading
            if self._send_with_curl(title, message, priority, tags):
                return True                                # e.g. Windows certificate issues
            self.log(f"(ntfy send failed: {e})")
            return False

    def _send_with_curl(self, title, message, priority, tags) -> bool:
        """Fallback: Windows' built-in curl.exe uses the Windows certificate store."""
        curl = shutil.which("curl")
        if not curl:
            return False
        try:
            r = subprocess.run(
                [curl, "-s", "-f", "-m", "10",
                 "-H", f"Title: {title.encode('ascii', 'ignore').decode()}",
                 "-H", f"Priority: {priority}", "-H", f"Tags: {tags}",
                 "--data-binary", message, f"{self.server}/{self.topic}"],
                capture_output=True, timeout=15)
            return r.returncode == 0
        except Exception:
            return False
