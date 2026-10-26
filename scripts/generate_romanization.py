#!/usr/bin/env python3
"""
Generate IAST romanization for Sinhala text and write it into the romanized
column of a review CSV.

Sinhala is a phonetic abugida — each symbol has a fixed sound — so rule-based
transliteration is accurate. The only caveat is that colloquial spoken Sinhala
can differ from the formal written form; for common vocabulary this is minor.

Output follows IAST (International Alphabet of Sanskrit Transliteration):
  ā ī ū — long vowels
  ṭ ḍ ṇ ḷ — retroflex consonants
  ś ṣ — palatal/retroflex sibilants
  ṃ ḥ — anusvara / visarga

A separate "reading guide" todo will annotate these symbols for German speakers.

Usage:
    python scripts/generate_romanization.py                    # vocab deck
    python scripts/generate_romanization.py --source B_parsed/omniglot-phrases/cards.csv
    python scripts/generate_romanization.py --force            # overwrite existing
"""

import argparse
import csv
import sys
from pathlib import Path


# ── Sinhala Unicode → IAST mapping ──────────────────────────────────────────

# Independent vowels (standalone vowel letters)
VOWELS: dict[str, str] = {
    'අ': 'a',  'ආ': 'ā',  'ඇ': 'æ',  'ඈ': 'ǣ',
    'ඉ': 'i',  'ඊ': 'ī',
    'උ': 'u',  'ඌ': 'ū',
    'ඍ': 'ṛ',  'ඎ': 'ṝ',
    'ඏ': 'ḷ',  'ඐ': 'ḹ',
    'එ': 'e',  'ඒ': 'ē',  'ඓ': 'ai',
    'ඔ': 'o',  'ඕ': 'ō',  'ඖ': 'au',
}

# Consonants — phoneme WITHOUT the inherent 'a' vowel
CONSONANTS: dict[str, str] = {
    'ක': 'k',   'ඛ': 'kh',  'ග': 'g',   'ඝ': 'gh',  'ඞ': 'ṅ',  'ඟ': 'ṅg',
    'ච': 'c',   'ඡ': 'ch',  'ජ': 'j',   'ඣ': 'jh',  'ඤ': 'ñ',
    'ඥ': 'ñj',  'ඦ': 'ñc',
    'ට': 'ṭ',   'ඨ': 'ṭh',  'ඩ': 'ḍ',   'ඪ': 'ḍh',  'ණ': 'ṇ',  'ඬ': 'ṇḍ',
    'ත': 't',   'ථ': 'th',  'ද': 'd',   'ධ': 'dh',  'න': 'n',  'ඳ': 'nd',
    'ප': 'p',   'ඵ': 'ph',  'බ': 'b',   'භ': 'bh',  'ම': 'm',  'ඹ': 'mb',
    'ය': 'y',   'ර': 'r',   'ල': 'l',   'ව': 'v',
    'ශ': 'ś',   'ෂ': 'ṣ',   'ස': 's',   'හ': 'h',
    'ළ': 'ḷ',   'ෆ': 'f',
}

# Vowel diacritics — follow the consonant, replace the inherent 'a'
VOWEL_SIGNS: dict[str, str] = {
    'ා': 'ā',  'ැ': 'æ',  'ෑ': 'ǣ',
    'ි': 'i',  'ී': 'ī',
    'ු': 'u',  'ූ': 'ū',
    'ෘ': 'ṛ',  'ෙ': 'e',  'ේ': 'ē',  'ෛ': 'ai',
    'ො': 'o',  'ෝ': 'ō',  'ෞ': 'au',
    'ෟ': 'ḷ',
}

VIRAMA   = '්'   # U+0DCA — suppresses the inherent vowel
ANUSVARA = 'ං'   # U+0D82 — nasal
VISARGA  = 'ඃ'   # U+0D83 — aspiration


def transliterate(text: str) -> str:
    """Transliterate a Sinhala string to IAST."""
    out = []
    chars = list(text)
    i = 0
    n = len(chars)

    while i < n:
        c = chars[i]

        if c in CONSONANTS:
            base = CONSONANTS[c]
            i += 1
            if i < n and chars[i] == VIRAMA:
                out.append(base)           # no vowel
                i += 1
            elif i < n and chars[i] in VOWEL_SIGNS:
                out.append(base + VOWEL_SIGNS[chars[i]])
                i += 1
            else:
                out.append(base + 'a')     # inherent vowel

        elif c in VOWELS:
            out.append(VOWELS[c])
            i += 1

        elif c == ANUSVARA:
            out.append('ṃ')
            i += 1

        elif c == VISARGA:
            out.append('ḥ')
            i += 1

        elif c in VOWEL_SIGNS:
            # Orphaned sign (shouldn't occur in well-formed text)
            out.append(VOWEL_SIGNS[c])
            i += 1

        else:
            out.append(c)   # spaces, punctuation, digits — pass through
            i += 1

    return ''.join(out)


# ── CSV update ───────────────────────────────────────────────────────────────

FIELDNAMES = ['id', 'source_deck', 'sinhala', 'english', 'romanized',
              'audio_file', 'status', 'sinhala_fix', 'english_fix', 'notes']


def main():
    parser = argparse.ArgumentParser(description='Generate IAST romanization for Sinhala review CSVs')
    parser.add_argument('--source', default='B_parsed/ankiweb-vocab/cards.csv',
                        help='Review CSV to update (default: B_parsed/ankiweb-vocab/cards.csv)')
    parser.add_argument('--force', action='store_true',
                        help='Overwrite existing romanized values')
    args = parser.parse_args()

    path = Path(args.source)
    if not path.exists():
        print(f'ERROR: {path} not found')
        sys.exit(1)

    rows = list(csv.DictReader(open(path, newline='', encoding='utf-8')))

    updated = skipped = 0
    for row in rows:
        if row.get('romanized', '').strip() and not args.force:
            skipped += 1
            continue
        sinhala = (row.get('sinhala_fix') or row.get('sinhala', '')).strip()
        if not sinhala:
            continue
        row['romanized'] = transliterate(sinhala)
        updated += 1

    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)

    print(f'{path.name}: {updated} romanized, {skipped} already had values.')
    if skipped and not args.force:
        print('  Use --force to overwrite existing romanizations.')


if __name__ == '__main__':
    main()
