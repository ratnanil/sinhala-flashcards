#!/usr/bin/env python3
"""
Ingest an Anki .apkg deck into B_parsed/<source>/cards.csv.

Extracts the .apkg, assigns stable card IDs, parses romanized fields out of
the English text, and appends only new cards (existing cards are preserved).
A fixes.csv stub is created alongside cards.csv if it does not exist yet.

Usage:
    python scripts/ingest.py A_raw/<source>/apkg/<source>.apkg B_parsed/<source>
    python scripts/ingest.py A_raw/<source>/apkg/<source>.apkg B_parsed/<source> \
        --audio-out A_raw/<source>/audio
"""

import argparse
import csv
import hashlib
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from export_apkg import extract_apkg, load_media_map, parse_notes, copy_media  # noqa: E402

PAREN_RE       = re.compile(r'^(.*?)\s*\(([^)]+)\)\s*$')
DIACRITIC_RE   = re.compile(r'[āēīōūňṁṃḍṭḷṅñÀ-öø-ÿ]', re.IGNORECASE)
ENGLISH_PARENS = {'singular', 'plural', 'turn on', 'digit is 0', 'the everyday spoken form'}

FIELDNAMES = ['id', 'source_deck', 'sinhala', 'english', 'romanized', 'audio_file']
FIX_FIELDS = ['type', 'key', 'value', 'replacement', 'note']


def looks_like_romanization(s: str) -> bool:
    if DIACRITIC_RE.search(s):
        return True
    words = s.lower().split()
    if len(words) <= 2 and s.lower() not in ENGLISH_PARENS and not s[0].isupper():
        return True
    return False


def extract_romanized(english: str) -> tuple:
    m = PAREN_RE.match(english.strip())
    if not m:
        return english.strip(), ''
    base      = m.group(1).strip()
    paren     = m.group(2).strip()
    candidate = paren.split(';')[0].strip()
    if looks_like_romanization(candidate):
        return base, candidate
    return english.strip(), ''


def card_id(deck_name: str, sinhala: str) -> str:
    h = hashlib.md5(sinhala.encode()).hexdigest()[:8]
    short = (deck_name
             .replace('everflip-sinhala-', '')
             .replace('ankiweb-vocab', 'vocab'))
    return f'{short}_{h}'


def load_existing_ids(cards_path: Path) -> set:
    if not cards_path.exists():
        return set()
    with open(cards_path, newline='', encoding='utf-8') as f:
        return {row['id'] for row in csv.DictReader(f)}


def ensure_fixes_stub(fixes_path: Path) -> None:
    if not fixes_path.exists():
        with open(fixes_path, 'w', newline='', encoding='utf-8') as f:
            csv.DictWriter(f, fieldnames=FIX_FIELDS).writeheader()


def main():
    parser = argparse.ArgumentParser(description='Ingest .apkg into B_parsed/<source>/cards.csv')
    parser.add_argument('apkg',       help='Path to .apkg file')
    parser.add_argument('output_dir', help='Output directory, e.g. B_parsed/<source>')
    parser.add_argument('--audio-out', default=None,
                        help='Directory for audio files (default: A_raw/<source>/audio)')
    args = parser.parse_args()

    apkg_path  = Path(args.apkg)
    out_dir    = Path(args.output_dir)
    deck_name  = out_dir.name
    cards_path = out_dir / 'cards.csv'
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.audio_out:
        audio_out = Path(args.audio_out)
    else:
        # Default: A_raw/<source>/audio (sibling of apkg/)
        audio_out = apkg_path.parent.parent / 'audio'

    existing = load_existing_ids(cards_path)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        print(f'Extracting {apkg_path.name}...')
        extract_apkg(apkg_path, tmp_path)

        media_map = load_media_map(tmp_path)
        cards_raw = parse_notes(tmp_path / 'collection.anki2')
        print(f'  {len(cards_raw)} cards, {len(media_map)} media files')

        copy_media(tmp_path, media_map, audio_out, cards_raw)

    new_rows = []
    for raw in cards_raw:
        cid = card_id(deck_name, raw['sinhala'])
        if cid in existing:
            continue
        english, romanized = extract_romanized(raw['english'])
        if not romanized:
            romanized = raw.get('romanized', '').strip()
        new_rows.append({
            'id':          cid,
            'source_deck': deck_name,
            'sinhala':     raw['sinhala'],
            'english':     english,
            'romanized':   romanized,
            'audio_file':  raw['audio_file'],
        })

    if not new_rows:
        print(f'  {deck_name}: no new cards')
    else:
        write_header = not cards_path.exists()
        with open(cards_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            if write_header:
                writer.writeheader()
            writer.writerows(new_rows)
        status = 'created' if write_header else 'appended'
        print(f'  {deck_name}: {status} {len(new_rows)} cards → {cards_path}')

    ensure_fixes_stub(out_dir / 'fixes.csv')
    print('Done.')


if __name__ == '__main__':
    main()
