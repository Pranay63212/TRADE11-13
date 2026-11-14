"""
Download free 1-minute BID candles from Dukascopy's public datafeed.

Files: https://datafeed.dukascopy.com/datafeed/{SYM}/{YYYY}/{MM0}/{DD}/BID_candles_min_1.bi5
  (MM0 = zero-based month). Each file is LZMA-compressed, 24-byte big-endian
  records: seconds-from-day-start(UTC), open, close, low, high (int, /1000), volume (float).

Usage: python3 dukascopy_download.py 2019-01-01 2026-11-13 [USA500IDXUSD,USATECHIDXUSD]
Output: data/duka/{SYM}/{YYYY-MM-DD}.npy (cached per day), then data/{SYM}_1m.parquet-like CSV.
"""
import lzma
import os
import struct
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta

import numpy as np
import pandas as pd

SYMBOLS = ["USA500IDXUSD", "USATECHIDXUSD"]
SCALE = 1000.0
BASE = "https://datafeed.dukascopy.com/datafeed"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def fetch_day(sym: str, d: date) -> np.ndarray:
    url = f"{BASE}/{sym}/{d.year}/{d.month - 1:02d}/{d.day:02d}/BID_candles_min_1.bi5"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    delay = 10
    while True:                      # keep retrying through throttling; never crash
        try:
            raw = urllib.request.urlopen(req, timeout=60).read()
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return np.empty((0, 6))
            print(f"  retry {d} in {delay}s (HTTP {e.code})", flush=True)
        except Exception as e:
            print(f"  retry {d} in {delay}s ({type(e).__name__})", flush=True)
        time.sleep(delay)
        delay = min(delay * 2, 600)
    if not raw:
        return np.empty((0, 6))
    buf = lzma.decompress(raw)
    n = len(buf) // 24
    recs = np.array(struct.unpack(">" + "IIIIIf" * n, buf[: n * 24]), dtype=float).reshape(n, 6)
    return recs


def main(start: str, end: str, symbols: str = ",".join(SYMBOLS)):
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    for sym in symbols.split(","):
        cache = os.path.join(ROOT, "duka", sym)
        os.makedirs(cache, exist_ok=True)
        d = d0
        while d <= d1:
            path = os.path.join(cache, f"{d}.npy")
            if d.weekday() != 5 and not os.path.exists(path):   # skip Saturdays
                np.save(path, fetch_day(sym, d))
                time.sleep(2.0)                                   # be gentle: avoid throttling
            d += timedelta(days=1)
            if d.day == 1:
                print(sym, d, flush=True)
        assemble(sym, d0, d1)


def assemble(sym: str, d0: date, d1: date):
    """Combine cached day files (whatever has been downloaded so far) into one CSV."""
    cache = os.path.join(ROOT, "duka", sym)
    if True:
        frames = []
        for f in sorted(os.listdir(cache)):
            day = date.fromisoformat(f[:10])
            if not (d0 <= day <= d1):
                continue
            a = np.load(os.path.join(cache, f))
            if len(a) == 0:
                continue
            ts = pd.Timestamp(day, tz="UTC") + pd.to_timedelta(a[:, 0], unit="s")
            frames.append(pd.DataFrame({
                "Open": a[:, 1] / SCALE, "High": a[:, 4] / SCALE,
                "Low": a[:, 3] / SCALE, "Close": a[:, 2] / SCALE, "Volume": a[:, 5],
            }, index=ts))
        df = pd.concat(frames).sort_index()
        df = df[df["Volume"] > 0]          # Dukascopy pads closed minutes with flat zero-volume bars
        df.index = df.index.tz_convert("America/New_York")
        out = os.path.join(ROOT, f"{sym}_1m.csv.gz")
        df.to_csv(out)
        print(sym, "saved", len(df), "bars", df.index[0], "->", df.index[-1], flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "--assemble":          # build CSVs from what is cached so far
        for s in SYMBOLS:
            assemble(s, date.fromisoformat(sys.argv[2]), date.fromisoformat(sys.argv[3]))
    else:
        main(*sys.argv[1:4])
