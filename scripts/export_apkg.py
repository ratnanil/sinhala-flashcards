#!/usr/bin/env python3
"""
Export an Anki .apkg deck to CSV + media files.

Usage:
    python scripts/export_apkg.py <deck.apkg> <output_dir>

Output:
    <output_dir>/cards.csv   -- columns: sinhala, english, audio_file (original filename)
    <output_dir>/audio/      -- media files renamed to their original filenames
"""

import argparse
import csv
import json
import re
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path


SOUND_RE = re.compile(r'\[sound:([^\]]+)\]')
FIELD_SEP = '\x1f'


def extract_apkg(apkg_path: Path, dest: Path) -> None:
    with zipfile.ZipFile(apkg_path) as z:
        z.extractall(dest)


def load_media_map(extracted: Path) -> dict:
    """Return mapping of numbered filename -> original filename."""
    media_file = extracted / 'media'
    if not media_file.exists():
        return {}
    with open(media_file, encoding='utf-8') as f:
        return json.load(f)


def parse_notes(db_path: Path) -> list:
    """Return list of {sinhala, audio_file, english} dicts from notes table."""
    con = sqlite3.connect(db_path)
    rows = con.execute('SELECT flds FROM notes').fetchall()
    con.close()

    cards = []
    for (flds,) in rows:
        fields = flds.split(FIELD_SEP)
        front = fields[0] if len(fields) > 0 else ''
        back  = fields[1] if len(fields) > 1 else ''

        audio_match = SOUND_RE.search(front)
        audio_ref = audio_match.group(1) if audio_match else ''
        sinhala = SOUND_RE.sub('', front).strip()

        cards.append({
            'sinhala':    sinhala,
            'english':    back.strip(),
            'audio_file': audio_ref,
        })
    return cards


def copy_media(extracted: Path, media_map: dict, audio_out: Path, cards: list) -> None:
    """Copy audio files to audio_out using their original filenames."""
    audio_out.mkdir(parents=True, exist_ok=True)
    inv = {v: k for k, v in media_map.items()}  # original_name -> numbered_name

    for card in cards:
        orig = card['audio_file']
        if not orig:
            continue
        numbered = inv.get(orig)
        if numbered is None:
            print(f'  WARNING: no media mapping for {orig!r}')
            continue
        src = extracted / numbered
        dst = audio_out / orig
        if src.exists():
            shutil.copy2(src, dst)
        else:
            print(f'  WARNING: media file missing: {src}')


def write_csv(cards: list, out_path: Path) -> None:
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['sinhala', 'english', 'audio_file'])
        writer.writeheader()
        writer.writerows(cards)


def main():
    parser = argparse.ArgumentParser(description='Export Anki .apkg to CSV + media')
    parser.add_argument('apkg',       help='Path to .apkg file')
    parser.add_argument('output_dir', help='Output directory for cards.csv')
    parser.add_argument('--audio-out', default=None,
                        help='Directory for audio files (default: <output_dir>/audio)')
    args = parser.parse_args()

    apkg_path = Path(args.apkg)
    out_dir   = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    audio_out = Path(args.audio_out) if args.audio_out else out_dir / 'audio'

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        print(f'Extracting {apkg_path.name}...')
        extract_apkg(apkg_path, tmp_path)

        print('Loading media map...')
        media_map = load_media_map(tmp_path)
        print(f'  {len(media_map)} media files')

        print('Parsing notes...')
        cards = parse_notes(tmp_path / 'collection.anki2')
        print(f'  {len(cards)} cards')

        print('Copying audio...')
        copy_media(tmp_path, media_map, audio_out, cards)

        csv_path = out_dir / 'cards.csv'
        print(f'Writing {csv_path}...')
        write_csv(cards, csv_path)

    print('Done.')


if __name__ == '__main__':
    main()
