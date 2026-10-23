#!/usr/bin/env python3
"""
Bulk-approve all pending cards in one or more review CSVs.

Rows already set to 'skip' are left untouched.

Usage:
    python scripts/approve_deck.py everflip-sinhala-colors
    python scripts/approve_deck.py --all
    python scripts/approve_deck.py --all --review review/
"""

import argparse
import csv
import sys
from pathlib import Path

FIELDNAMES = ['id', 'source_deck', 'sinhala', 'english', 'romanized',
              'audio_file', 'status', 'sinhala_fix', 'english_fix', 'notes']


def approve(review_path: Path) -> tuple:
    """Set all 'pending' rows to 'ok'. Returns (approved, skipped, already_ok)."""
    rows = []
    with open(review_path, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    approved = skipped = already_ok = 0
    for row in rows:
        s = row['status'].strip().lower()
        if s == 'pending':
            row['status'] = 'ok'
            approved += 1
        elif s == 'skip':
            skipped += 1
        elif s == 'ok':
            already_ok += 1

    with open(review_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)

    return approved, skipped, already_ok


def main():
    parser = argparse.ArgumentParser(description='Bulk-approve pending cards in review CSVs')
    parser.add_argument('deck', nargs='?',
                        help='Deck name (without .csv), e.g. everflip-sinhala-colors')
    parser.add_argument('--all',    action='store_true', help='Approve all decks')
    parser.add_argument('--review', default='review', help='Review directory')
    args = parser.parse_args()

    review_root = Path(args.review)

    if args.all:
        targets = sorted(review_root.glob('*.csv'))
        if not targets:
            print('No review files found.')
            sys.exit(1)
    elif args.deck:
        name = args.deck if args.deck.endswith('.csv') else args.deck + '.csv'
        targets = [review_root / name]
        if not targets[0].exists():
            print(f'Not found: {targets[0]}')
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)

    for path in targets:
        approved, skipped, already_ok = approve(path)
        parts = []
        if approved:   parts.append(f'{approved} approved')
        if skipped:    parts.append(f'{skipped} kept as skip')
        if already_ok: parts.append(f'{already_ok} already ok')
        print(f'  {path.stem}: {", ".join(parts)}')


if __name__ == '__main__':
    main()
