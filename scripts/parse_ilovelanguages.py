#!/usr/bin/env python3
"""
Parse ilovelanguages lesson HTMLs → data/ilovelanguages/cards.csv

Reads all Sinhala Lesson*.html files from raw/html/ilovelanguages/ and
produces a single deduplicated cards CSV.

Audio files are only referenced if they exist in raw/audio/ilovelanguages/
(103 files are genuinely absent from the server and were never downloaded).

Run once, then `make review` to create parsed/ilovelanguages/cards.csv.

Usage:
    python scripts/parse_ilovelanguages.py
"""

import csv
from pathlib import Path

from bs4 import BeautifulSoup

HTML_DIR  = Path('raw/html/ilovelanguages')
AUDIO_DIR = Path('raw/audio/ilovelanguages')
OUT_CSV   = Path('data/ilovelanguages/cards.csv')


def parse_lessons() -> list[dict]:
    seen: set[tuple] = set()  # (english, sinhala) dedup key
    rows = []

    for html_file in sorted(HTML_DIR.glob('Sinhala Lesson*.html')):
        soup = BeautifulSoup(html_file.read_text(encoding='utf-8'), 'html.parser')
        for table in soup.find_all('table', id=lambda x: x and x.startswith('lesson-table-')):
            for tr in table.find('tbody').find_all('tr'):
                tds = tr.find_all('td')
                if len(tds) < 3:
                    continue

                english = tds[0].get_text(strip=True)
                if not english:
                    continue

                strong = tds[1].find('strong')
                if not strong:
                    continue
                parts = [s.strip() for s in strong.strings if s.strip()]
                if len(parts) < 1:
                    continue
                sinhala    = parts[0]
                romanized  = parts[1] if len(parts) > 1 else ''

                if not sinhala:
                    continue

                key = (english, sinhala)
                if key in seen:
                    continue
                seen.add(key)

                btn = tds[2].find('button', attrs={'data-audio': True})
                if btn:
                    filename = Path(btn['data-audio']).name
                    audio_file = filename if (AUDIO_DIR / filename).exists() else ''
                else:
                    audio_file = ''

                rows.append({
                    'english':    english,
                    'sinhala':    sinhala,
                    'romanized':  romanized,
                    'audio_file': audio_file,
                })

    return rows


def main():
    rows = parse_lessons()
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['english', 'sinhala', 'romanized', 'audio_file'])
        w.writeheader()
        w.writerows(rows)

    no_audio = sum(1 for r in rows if not r['audio_file'])
    print(f'{len(rows)} cards → {OUT_CSV}  ({no_audio} without audio)')


if __name__ == '__main__':
    main()
