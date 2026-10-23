#!/usr/bin/env python3
"""
Generate review CSVs from exported deck CSVs.

Existing review files are never overwritten — only new rows are appended,
identified by a stable ID derived from the sinhala text.

Usage:
    python scripts/prepare_review.py [--data data/] [--review review/]
"""

import argparse
import csv
import hashlib
import re
from pathlib import Path

PAREN_RE = re.compile(r'^(.*?)\s*\(([^)]+)\)\s*$')
DIACRITIC_RE = re.compile(r'[āēīōūňṁṃḍṭḷṅñÀ-öø-ÿ]', re.IGNORECASE)
ENGLISH_PARENS = {'singular', 'plural', 'turn on', 'digit is 0', 'the everyday spoken form'}

FIELDNAMES = ['id', 'source_deck', 'sinhala', 'english', 'romanized',
              'audio_file', 'status', 'sinhala_fix', 'english_fix', 'notes']


def looks_like_romanization(s: str) -> bool:
    """True if s looks like a romanized Sinhala word rather than an English note."""
    if DIACRITIC_RE.search(s):
        return True
    words = s.lower().split()
    # Single short word not obviously English
    if len(words) <= 2 and s.lower() not in ENGLISH_PARENS and not s[0].isupper():
        return True
    return False


def extract_romanized(english: str) -> tuple:
    """Split 'word (romanized; notes)' → (clean_english, romanized).
    Returns (original, '') when no romanization is detected."""
    m = PAREN_RE.match(english.strip())
    if not m:
        return english.strip(), ''
    base = m.group(1).strip()
    paren = m.group(2).strip()
    candidate = paren.split(';')[0].strip()
    if looks_like_romanization(candidate):
        return base, candidate
    return english.strip(), ''


def card_id(deck_name: str, sinhala: str) -> str:
    h = hashlib.md5(sinhala.encode()).hexdigest()[:8]
    short = (deck_name
             .replace('everflip-sinhala-', '')
             .replace('Sinhala_to_English_vocab', 'vocab'))
    return f'{short}_{h}'


def load_existing_ids(review_path: Path) -> set:
    if not review_path.exists():
        return set()
    with open(review_path, newline='', encoding='utf-8') as f:
        return {row['id'] for row in csv.DictReader(f)}


def main():
    parser = argparse.ArgumentParser(description='Generate review CSVs from exported decks')
    parser.add_argument('--data',   default='data',   help='Root data directory')
    parser.add_argument('--review', default='review', help='Output review directory')
    args = parser.parse_args()

    data_root   = Path(args.data)
    review_root = Path(args.review)
    review_root.mkdir(exist_ok=True)

    for cards_csv in sorted(data_root.glob('*/cards.csv')):
        deck_name   = cards_csv.parent.name
        review_path = review_root / f'{deck_name}.csv'
        existing    = load_existing_ids(review_path)

        new_rows = []
        with open(cards_csv, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                cid = card_id(deck_name, row['sinhala'])
                if cid in existing:
                    continue
                english, romanized = extract_romanized(row['english'])
                # If source CSV already has a romanized column, prefer it
                if not romanized:
                    romanized = row.get('romanized', '').strip()
                new_rows.append({
                    'id':          cid,
                    'source_deck': deck_name,
                    'sinhala':     row['sinhala'],
                    'english':     english,
                    'romanized':   romanized,
                    'audio_file':  row['audio_file'],
                    'status':      'pending',
                    'sinhala_fix': '',
                    'english_fix': '',
                    'notes':       row.get('notes', ''),
                })

        if not new_rows:
            print(f'  {deck_name}: no new cards')
            continue

        write_header = not review_path.exists()
        with open(review_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            if write_header:
                writer.writeheader()
            writer.writerows(new_rows)

        status = 'created' if write_header else 'appended'
        print(f'  {deck_name}: {status} {len(new_rows)} cards → {review_path}')


if __name__ == '__main__':
    main()
