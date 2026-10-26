#!/usr/bin/env python3
"""
Download Sinhala audio files from the I Love Languages lesson HTML pages.

Parses all Sinhala Lesson*.html files in A_raw/ilovelanguages/html/ and downloads
the corresponding MP3s to A_raw/ilovelanguages/audio/.

HTML files were saved manually from https://ilovelanguages.org/sinhala/
Audio served from https://ilovelanguages.org/audio/sinhala/<filename>.mp3

Idempotent — already-downloaded files are skipped.

Usage:
    python scripts/acquire/download_ilovelanguages.py
    python scripts/acquire/download_ilovelanguages.py --html-dir A_raw/ilovelanguages/html --audio-out A_raw/ilovelanguages/audio
"""

import argparse
import time
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup

BASE_URL = 'https://ilovelanguages.org/'
HEADERS  = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0',
    'Accept':     'audio/webm,audio/ogg,audio/wav,audio/*;q=0.9,*/*;q=0.5',
    'Referer':    'https://ilovelanguages.org/sinhala/',
}


def collect_audio_urls(html_dir: Path) -> dict[str, str]:
    """Return {filename: full_url} for all unique audio buttons across all lesson HTMLs."""
    files = sorted(html_dir.glob('Sinhala Lesson*.html'))
    if not files:
        raise SystemExit(f'No lesson HTML files found in {html_dir}')
    urls: dict[str, str] = {}
    for html_file in files:
        with open(html_file, encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')
        for btn in soup.find_all('button', attrs={'data-audio': True}):
            rel = btn['data-audio']
            filename = Path(rel).name
            urls[filename] = BASE_URL + rel
    return urls


def main():
    parser = argparse.ArgumentParser(description='Download ilovelanguages Sinhala audio')
    parser.add_argument('--html-dir',  default='A_raw/ilovelanguages/html',
                        help='Directory containing lesson HTML files')
    parser.add_argument('--audio-out', default='A_raw/ilovelanguages/audio',
                        help='Directory to write MP3 files')
    args = parser.parse_args()

    html_dir  = Path(args.html_dir)
    audio_out = Path(args.audio_out)
    audio_out.mkdir(parents=True, exist_ok=True)

    urls = collect_audio_urls(html_dir)
    print(f'{len(urls)} unique audio files found across all lessons')

    downloaded = skipped = failed = 0
    for filename, url in sorted(urls.items()):
        dest = audio_out / filename
        if dest.exists():
            skipped += 1
            continue
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp, open(dest, 'wb') as out:
                out.write(resp.read())
            print(f'  OK  {filename}')
            downloaded += 1
            time.sleep(0.3)
        except Exception as e:
            print(f'  ERR {filename}: {e}')
            failed += 1

    print(f'\nDone: {downloaded} downloaded, {skipped} skipped, {failed} failed')


if __name__ == '__main__':
    main()
