#!/usr/bin/env python3
"""
Merge parsed cards CSVs into data/master.csv.

Rules:
  - Duplicates (same sinhala text) are resolved by preferring the row with audio

Note: this script is a legacy intermediate step and will be removed once
all pipeline scripts read from parsed/ directly.

Usage:
    python scripts/merge.py [--parsed parsed/] [--out data/master.csv]
"""

import argparse
import csv
from pathlib import Path

FIELDNAMES = ['id', 'source_deck', 'category', 'sinhala', 'english', 'romanized', 'audio_file', 'german']


def derive_category(source_deck: str) -> str:
    if source_deck.startswith('everflip-sinhala-'):
        return source_deck.replace('everflip-sinhala-', '')
    return ''


def main():
    parser = argparse.ArgumentParser(description='Merge parsed cards CSVs into master.csv')
    parser.add_argument('--parsed', default='parsed',          help='Parsed directory')
    parser.add_argument('--out',    default='data/master.csv', help='Output master CSV')
    args = parser.parse_args()

    parsed_root = Path(args.parsed)
    out_path    = Path(args.out)

    cards_files = sorted(parsed_root.glob('*/cards.csv'))
    if not cards_files:
        print('No parsed cards files found.')
        return

    all_rows = []
    counts = {}
    for cards_csv in cards_files:
        n = 0
        with open(cards_csv, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                row.setdefault('german', '')
                row['category'] = derive_category(row['source_deck'])
                all_rows.append(row)
                n += 1
        counts[cards_csv.parent.name] = n

    # Deduplicate on sinhala: prefer rows with audio
    seen = {}
    for row in all_rows:
        key = row['sinhala']
        if key not in seen or (not seen[key]['audio_file'] and row['audio_file']):
            seen[key] = row

    deduped = list(seen.values())
    deduped.sort(key=lambda r: (r['source_deck'], r['id']))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(deduped)

    total_in  = len(all_rows)
    total_out = len(deduped)
    print(f'Merged {total_in} cards from {len(counts)} decks')
    for name, n in counts.items():
        print(f'  {name}: {n}')
    if total_in != total_out:
        print(f'  {total_in - total_out} duplicates removed')
    print(f'→ {out_path}: {total_out} cards')


if __name__ == '__main__':
    main()
