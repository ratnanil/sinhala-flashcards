#!/usr/bin/env python3
"""
Merge approved review CSVs into data/master.csv.

Rules:
  - Only rows with status='ok' are included
  - sinhala_fix / english_fix override the original fields when non-empty
  - Duplicates (same sinhala text) are resolved by preferring the row with audio

Usage:
    python scripts/merge.py [--review review/] [--out data/master.csv]
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
    parser = argparse.ArgumentParser(description='Merge approved review CSVs into master.csv')
    parser.add_argument('--review', default='review',          help='Review directory')
    parser.add_argument('--out',    default='data/master.csv', help='Output master CSV')
    args = parser.parse_args()

    review_root = Path(args.review)
    out_path    = Path(args.out)

    review_files = sorted(review_root.glob('*.csv'))
    if not review_files:
        print('No review files found.')
        return

    all_rows = []
    counts = {}
    for review_csv in review_files:
        n = 0
        with open(review_csv, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                if row['status'].strip().lower() != 'ok':
                    continue
                if row['sinhala_fix'].strip():
                    row['sinhala'] = row['sinhala_fix'].strip()
                if row['english_fix'].strip():
                    row['english'] = row['english_fix'].strip()
                row.setdefault('german', '')
                row['category'] = derive_category(row['source_deck'])
                all_rows.append(row)
                n += 1
        counts[review_csv.name] = n

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
    print(f'Merged {total_in} approved cards from {len(counts)} decks')
    for name, n in counts.items():
        print(f'  {name}: {n} ok')
    if total_in != total_out:
        print(f'  {total_in - total_out} duplicates removed')
    print(f'→ {out_path}: {total_out} cards')


if __name__ == '__main__':
    main()
