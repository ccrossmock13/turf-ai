#!/usr/bin/env python3
"""Download all weed photos from GreenCast weed guide."""
import json
import os
import urllib.request
import urllib.error
from pathlib import Path

PHOTO_DIR = Path("static/weed-photos")
PHOTO_DIR.mkdir(parents=True, exist_ok=True)

with open("weed_photo_urls.json") as f:
    photo_map = json.load(f)

total = sum(len(urls) for urls in photo_map.values())
downloaded = 0
failed = []

for slug, urls in photo_map.items():
    for url in urls:
        filename = url.split("/")[-1].lower()
        dest = PHOTO_DIR / filename
        if dest.exists():
            downloaded += 1
            print(f"[{downloaded}/{total}] SKIP (exists): {filename}")
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
            dest.write_bytes(data)
            downloaded += 1
            print(f"[{downloaded}/{total}] OK: {filename} ({len(data)//1024}KB)")
        except Exception as e:
            downloaded += 1
            failed.append((slug, url, str(e)))
            print(f"[{downloaded}/{total}] FAIL: {filename} - {e}")

print(f"\nDone! Downloaded {total - len(failed)}/{total} photos.")
if failed:
    print(f"Failed ({len(failed)}):")
    for slug, url, err in failed:
        print(f"  {slug}: {url} - {err}")
