#!/usr/bin/env python3
"""
Generate English → German translations for vocabulary words using Ollama.

Translations are stored in a separate join table (data/translations.csv) keyed
by English word, so they can be refined independently of the source decks.
Already-translated words are skipped — safe to rerun.

Usage:
    python scripts/generate_translations.py
    python scripts/generate_translations.py --source B_parsed/ankiweb-vocab/cards.csv
    python scripts/generate_translations.py --model qwen3.5 --output C_enriched/ankiweb-vocab/translations.csv
"""

import argparse
import csv
import json
import sys
import time
import urllib.request
from pathlib import Path


OLLAMA_URL = 'http://localhost:11434/api/generate'


def check_ollama() -> bool:
    try:
        urllib.request.urlopen('http://localhost:11434/api/tags', timeout=2)
        return True
    except Exception:
        return False


def translate(english: str, sinhala: str, romanized: str, model: str) -> str:
    """Ask Ollama to translate a Sinhala concept to German. Returns translation or ''."""
    context = f"The Sinhala is '{sinhala}'"
    if romanized:
        context += f" (romanized: '{romanized}')"
    prompt = (
        f"You are building a Sinhala–German flashcard deck. "
        f"The English gloss for this card is '{english}'. {context}. "
        f"Translate the Sinhala concept to German. "
        f"For nouns, include the definite article (der/die/das). "
        f"For verbs, use the infinitive. "
        f"For adjectives such as colors, give the uninflected base form with no article. "
        f"Reply with ONLY the German translation, nothing else."
    )
    payload = json.dumps({
        'model':  model,
        'prompt': prompt,
        'stream': False,
        'think':  False,
        'options': {'temperature': 0},
    }).encode()

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data.get('response', '').strip()
    except Exception as e:
        print(f'    Ollama error: {e}')
        return ''


def load_existing(output_path: Path) -> dict:
    """Load existing translations. Returns {english: german}."""
    if not output_path.exists():
        return {}
    with open(output_path, newline='', encoding='utf-8') as f:
        return {row['english']: row['german'] for row in csv.DictReader(f)}


def collect_words(sources: list, source_deck: str | None = None) -> list:
    """Return sorted list of unique {english, sinhala, romanized} dicts."""
    seen: dict = {}  # english → {english, sinhala, romanized}
    for src in sources:
        with open(src, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                if source_deck and row.get('source_deck', '') != source_deck:
                    continue
                word      = row.get('english', '').strip()
                sinhala   = row.get('sinhala', '').strip()
                romanized = row.get('romanized', '').strip()
                if word and word not in seen:
                    seen[word] = {'english': word, 'sinhala': sinhala, 'romanized': romanized}
    return sorted(seen.values(), key=lambda x: x['english'])


def main():
    parser = argparse.ArgumentParser(description='Generate EN→DE translations via Ollama')
    parser.add_argument('--source', default=None,
                        help='CSV to read English words from (default: all B_parsed/*/cards.csv)')
    parser.add_argument('--model',  default='qwen3.5', help='Ollama model to use')
    parser.add_argument('--output', default=None,
                        help='Output join table (default: C_enriched/translations/<source>.csv)')
    parser.add_argument('--source-deck', default=None,
                        help='Only translate cards from this source_deck')
    parser.add_argument('--force', action='store_true',
                        help='Retranslate all words, overwriting existing entries')
    args = parser.parse_args()

    sources = [Path(args.source)] if args.source else sorted(Path('B_parsed').glob('*/cards.csv'))
    if args.output:
        output_path = Path(args.output)
    elif args.source:
        source_name = Path(args.source).parent.name
        output_path = Path('C_enriched') / source_name / 'translations.csv'
    else:
        print('ERROR: --output required when no --source given (no single source to default to)')
        import sys; sys.exit(1)

    existing = {} if args.force else load_existing(output_path)
    words    = collect_words(sources, args.source_deck)
    missing  = [w for w in words if w['english'] not in existing]

    if not missing:
        print(f'All {len(words)} words already translated. Nothing to do.')
        return

    print(f'{len(words)} words total, {len(missing)} translations missing.')

    if not check_ollama():
        print('ERROR: Ollama is not running. Start it with: ollama serve')
        sys.exit(1)

    # Append mode — write header only if file is new; force overwrites
    write_header = args.force or not output_path.exists()
    mode = 'w' if args.force else 'a'
    with open(output_path, mode, newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['english', 'german'])
        if write_header:
            writer.writeheader()

        ok = failed = 0
        for entry in missing:
            print(f"  {entry['english']!r}", end=' → ', flush=True)
            german = translate(entry['english'], entry['sinhala'], entry['romanized'], args.model)
            if german:
                print(german)
                writer.writerow({'english': entry['english'], 'german': german})
                f.flush()
                ok += 1
            else:
                print('(no result, skipped)')
                failed += 1
            time.sleep(0.05)

    print(f'\nDone: {ok} translated, {failed} failed.')
    if failed:
        print('Tip: rerun to retry failed words.')


if __name__ == '__main__':
    main()
