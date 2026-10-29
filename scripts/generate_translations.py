#!/usr/bin/env python3
"""
Generate English → German translations for vocabulary words using DeepL.

Translations are stored in C_enriched/<source>/translations/translations.csv,
keyed by card ID (with english included for readability). Already-translated
cards are skipped — safe to rerun.

Requires: DEEPL_API_KEY environment variable (free keys end with :fx).

Usage:
    python scripts/generate_translations.py --source B_parsed/ankiweb-vocab/cards.csv
    python scripts/generate_translations.py --force   # retranslate everything
"""

import argparse
import csv
import json
import os
import sys
import urllib.request
from pathlib import Path


def translate(english: str, api_key: str) -> str:
    """Translate one English vocabulary entry to German via DeepL.

    Verbs ("to go") are sent as-is → DeepL returns the infinitive ("gehen").
    All other words get "the " prepended → DeepL returns the noun with its
    German article ("the mango" → "die Mango", "the pomegranate" → "der Granatapfel").
    """
    text = english if english.lower().startswith('to ') else f'the {english}'

    base = 'https://api-free.deepl.com' if api_key.endswith(':fx') else 'https://api.deepl.com'
    payload = json.dumps({
        'text':        [text],
        'source_lang': 'EN',
        'target_lang': 'DE',
    }).encode()
    req = urllib.request.Request(
        f'{base}/v2/translate',
        data=payload,
        headers={
            'Content-Type':  'application/json',
            'Authorization': f'DeepL-Auth-Key {api_key}',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return data['translations'][0]['text'].strip()
    except Exception as e:
        print(f'    DeepL error: {e}')
        return ''


def load_existing(output_path: Path) -> set:
    """Return set of card IDs already translated."""
    if not output_path.exists():
        return set()
    with open(output_path, newline='', encoding='utf-8') as f:
        return {row['id'] for row in csv.DictReader(f)}


def collect_cards(sources: list) -> list:
    """Return list of {id, english} dicts, deduplicated by card ID."""
    seen: set = set()
    cards: list = []
    for src in sources:
        with open(src, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                card_id = row.get('id', '').strip()
                english = row.get('english', '').strip()
                if card_id and english and card_id not in seen:
                    seen.add(card_id)
                    cards.append({'id': card_id, 'english': english})
    return sorted(cards, key=lambda x: x['english'])


def main():
    parser = argparse.ArgumentParser(description='Generate EN→DE translations via DeepL')
    parser.add_argument('--source', default=None,
                        help='CSV to read cards from (default: all B_parsed/*/cards.csv)')
    parser.add_argument('--output', default=None,
                        help='Output CSV (default: C_enriched/<source>/translations/translations.csv)')
    parser.add_argument('--force', action='store_true',
                        help='Retranslate all cards, overwriting existing entries')
    args = parser.parse_args()

    api_key = os.environ.get('DEEPL_API_KEY', '')
    if not api_key:
        print('ERROR: DEEPL_API_KEY environment variable not set')
        sys.exit(1)

    sources = [Path(args.source)] if args.source else sorted(Path('B_parsed').glob('*/cards.csv'))
    if args.output:
        output_path = Path(args.output)
    elif args.source:
        output_path = Path('C_enriched') / Path(args.source).parent.name / 'translations' / 'translations.csv'
    else:
        print('ERROR: --output required when no --source given')
        sys.exit(1)

    existing = set() if args.force else load_existing(output_path)
    cards    = collect_cards(sources)
    missing  = [c for c in cards if c['id'] not in existing]

    if not missing:
        print(f'All {len(cards)} cards already translated. Nothing to do.')
        return

    print(f'{len(cards)} cards total, {len(missing)} to translate.')

    # Cache API calls — if two cards share the same English gloss, translate once
    cache: dict[str, str] = {}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = args.force or not output_path.exists()
    mode = 'w' if args.force else 'a'
    with open(output_path, mode, newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'english', 'german'])
        if write_header:
            writer.writeheader()

        ok = failed = 0
        for card in missing:
            english = card['english']
            print(f"  {card['id']}  {english!r}", end=' → ', flush=True)
            if english in cache:
                german = cache[english]
                print(f'{german}  (cached)')
            else:
                german = translate(english, api_key)
                if german:
                    cache[english] = german
            if german:
                print(german) if english not in cache else None
                writer.writerow({'id': card['id'], 'english': english, 'german': german})
                f.flush()
                ok += 1
            else:
                print('(failed, skipped)')
                failed += 1

    print(f'\nDone: {ok} translated, {failed} failed.')
    if failed:
        print('Tip: rerun to retry failed cards.')


if __name__ == '__main__':
    main()
