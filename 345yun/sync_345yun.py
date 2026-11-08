#!/usr/bin/env python3
# Sync one day's scripts from https://script.345yun.cn into this repo.
# Usage: python3 sync_345yun.py [--date YYYY-MM-DD] [--out DIR]
# Default date is yesterday (Asia/Shanghai). Default out is ./<date> next to this script.
import argparse
import datetime
import hashlib
import json
import os
import sys
import urllib.request

API = "https://script.345yun.cn/api/scripts"
DIRECT = "https://script.345yun.cn/api/download/direct/{id}"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def verify(data, api_hash):
    if not api_hash:
        return "no_api_hash"
    if sha256(data) == api_hash:
        return "full_match"
    lines = data.splitlines(keepends=True)
    for head in range(0, 16):
        for tail in range(0, 16):
            end = len(lines) - tail if tail else len(lines)
            if hashlib.sha256(b"".join(lines[head:end])).hexdigest() == api_hash:
                return "strip_match_head%d_tail%d" % (head, tail)
    return "mismatch"


def safe_name(name):
    name = name.replace("/", "_").replace("\\", "_").strip()
    return name or "unnamed"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    if args.date:
        day = args.date
    else:
        tz = datetime.timezone(datetime.timedelta(hours=8))
        day = (datetime.datetime.now(tz) - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    base = os.path.dirname(os.path.abspath(__file__))
    out_dir = args.out or os.path.join(base, day)
    os.makedirs(out_dir, exist_ok=True)

    raw = fetch(API)
    payload = json.loads(raw.decode("utf-8"))
    items = payload.get("data") or []
    todays = [it for it in items if str(it.get("upload_time", "")).startswith(day)]
    todays.sort(key=lambda it: str(it.get("upload_time", "")))

    results = []
    for it in todays:
        sid = it.get("id")
        fname = safe_name(str(it.get("filename", "")))
        data = fetch(DIRECT.format(id=sid))
        with open(os.path.join(out_dir, fname), "wb") as fh:
            fh.write(data)
        results.append({
            "id": sid,
            "filename": fname,
            "upload_time": it.get("upload_time"),
            "api_hash": it.get("file_hash"),
            "download_sha256": sha256(data),
            "verify": verify(data, it.get("file_hash")),
            "bytes": len(data),
        })

    manifest = {"date": day, "count": len(results), "scripts": results}
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    print(json.dumps(manifest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
