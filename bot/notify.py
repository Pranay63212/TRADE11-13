"""
Push notifications to your phone via ntfy (https://ntfy.sh).

Anyone who knows your topic name can read (and send to) it, so pick a long
random topic name and treat it like a password.
"""
from __future__ import annotations

import time
import urllib.request


class Ntfy:
    def __init__(self, topic: str | None, server: str = "https://ntfy.sh", log=print):
        self.topic, self.server, self.log = topic, server.rstrip("/"), log
        self._last: dict[str, float] = {}

    def __call__(self, title: str, message: str, priority: str = "default",
                 tags: str = "", throttle_key: str | None = None, throttle_s: int = 600):
        if not self.topic:
            return
        if throttle_key:                                   # avoid spamming repeated errors
            now = time.time()
            if now - self._last.get(throttle_key, 0) < throttle_s:
                return
            self._last[throttle_key] = now
        req = urllib.request.Request(
            f"{self.server}/{self.topic}", data=message.encode("utf-8"), method="POST",
            headers={"Title": title.encode("ascii", "ignore").decode(),
                     "Priority": priority, "Tags": tags})
        try:
            urllib.request.urlopen(req, timeout=5).read()
        except Exception as e:                             # never let alerts crash trading
            self.log(f"(ntfy send failed: {e})")
