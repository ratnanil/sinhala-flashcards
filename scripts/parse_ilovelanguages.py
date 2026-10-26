#!/usr/bin/env python3
"""
Parse ilovelanguages lesson HTMLs → parsed/ilovelanguages/cards.csv

Reads all Sinhala Lesson*.html files from raw/ilovelanguages/html/ and
produces a deduplicated cards CSV.

Audio files are only referenced if they exist in raw/ilovelanguages/audio/
(103 files are genuinely absent from the server and were never downloaded).

Append-only: existing cards (matched by stable ID) are never overwritten.

Usage:
    python scripts/parse_ilovelanguages.py
"""

import csv
import hashlib
from pathlib import Path

from bs4 import BeautifulSoup

HTML_DIR   = Path('raw/ilovelanguages/html')
AUDIO_DIR  = Path('raw/ilovelanguages/audio')
OUT_CSV    = Path('parsed/ilovelanguages/cards.csv')
FIELDNAMES = ['id', 'source_deck', 'sinhala', 'english', 'romanized', 'audio_file']
FIX_FIELDS = ['type', 'key', 'value', 'replacement', 'note']


def card_id(sinhala: str) -> str:
    h = hashlib.md5(sinhala.encode()).hexdigest()[:8]
    return f'ilovelanguages_{h}'


def load_existing_ids(path: Path) -> set:
    if not path.exists():
        return set()
    with open(path, newline='', encoding='utf-8') as f:
        return {row['id'] for row in csv.DictReader(f)}


def ensure_fixes_stub(fixes_path: Path) -> None:
    if not fixes_path.exists():
        with open(fixes_path, 'w', newline='', encoding='utf-8') as f:
            csv.DictWriter(f, fieldnames=FIX_FIELDS).writeheader()


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
    existing = load_existing_ids(OUT_CSV)
    raw_rows = parse_lessons()

    new_rows = []
    for r in raw_rows:
        cid = card_id(r['sinhala'])
        if cid in existing:
            continue
        new_rows.append({
            'id':          cid,
            'source_deck': 'ilovelanguages',
            'sinhala':     r['sinhala'],
            'english':     r['english'],
            'romanized':   r['romanized'],
            'audio_file':  r['audio_file'],
        })

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    if not new_rows:
        print('no new cards')
    else:
        write_header = not OUT_CSV.exists()
        with open(OUT_CSV, 'a', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=FIELDNAMES)
            if write_header:
                w.writeheader()
            w.writerows(new_rows)
        no_audio = sum(1 for r in new_rows if not r['audio_file'])
        status = 'created' if write_header else 'appended'
        print(f'{status} {len(new_rows)} cards → {OUT_CSV}  ({no_audio} without audio)')

    ensure_fixes_stub(OUT_CSV.parent / 'fixes.csv')


if __name__ == '__main__':
    main()
