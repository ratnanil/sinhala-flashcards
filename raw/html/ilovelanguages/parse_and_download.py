#!/usr/bin/env python3
"""Parse ilovelanguages HTML and download MP3s."""

import csv
import json
import os
import time
import urllib.request
from bs4 import BeautifulSoup

HTML_FILE = "Sinhala Lesson 2_ Adjectives & food _ I Love Languages.html"
BASE_URL = "https://ilovelanguages.org/"
AUDIO_DIR = "audio"
OUTPUT_CSV = "lesson2.csv"
OUTPUT_JSON = "lesson2.json"

os.makedirs(AUDIO_DIR, exist_ok=True)

with open(HTML_FILE, encoding="utf-8") as f:
    soup = BeautifulSoup(f, "html.parser")

tables = soup.find_all("table", id=lambda x: x and x.startswith("lesson-table-"))

rows = []
for table in tables:
    header_el = table.find_previous("h3", class_="box-title")
    section = header_el.get_text(strip=True) if header_el else "Unknown"
    for tr in table.find("tbody").find_all("tr"):
        tds = tr.find_all("td")
        english = tds[0].get_text(strip=True)
        sinhala_el = tds[1].find("strong")
        parts = list(sinhala_el.strings)
        sinhala_script = parts[0].strip() if parts else ""
        romanization = parts[-1].strip() if len(parts) > 1 else ""
        audio_btn = tds[2].find("button", attrs={"data-audio": True})
        audio_rel = audio_btn["data-audio"] if audio_btn else ""
        rows.append({
            "section": section,
            "english": english,
            "sinhala": sinhala_script,
            "romanization": romanization,
            "audio_file": os.path.basename(audio_rel) if audio_rel else "",
            "audio_url": BASE_URL + audio_rel if audio_rel else "",
        })

# Write CSV
with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["section", "english", "sinhala", "romanization", "audio_file", "audio_url"])
    writer.writeheader()
    writer.writerows(rows)
print(f"Wrote {len(rows)} rows to {OUTPUT_CSV}")

# Write JSON
with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(rows, f, ensure_ascii=False, indent=2)
print(f"Wrote {OUTPUT_JSON}")

# Download MP3s
headers = {"User-Agent": "Mozilla/5.0"}
downloaded = 0
skipped = 0
failed = 0

for row in rows:
    if not row["audio_url"]:
        continue
    dest = os.path.join(AUDIO_DIR, row["audio_file"])
    if os.path.exists(dest):
        skipped += 1
        continue
    try:
        req = urllib.request.Request(row["audio_url"], headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp, open(dest, "wb") as out:
            out.write(resp.read())
        print(f"  OK  {row['audio_file']}")
        downloaded += 1
        time.sleep(0.3)
    except Exception as e:
        print(f"  ERR {row['audio_file']}: {e}")
        failed += 1

print(f"\nDone: {downloaded} downloaded, {skipped} skipped, {failed} failed")
