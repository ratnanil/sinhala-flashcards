#!/usr/bin/env python3
"""
Generate emoji images for vocabulary words using Ollama + Twemoji PNGs.

For each English word in a cards CSV, asks Ollama to suggest an emoji, then
downloads the corresponding Twemoji PNG. Already-existing images are skipped.

Images are saved as images/<sanitized_word>.png and named by the English keyword,
making them reusable across decks.

Usage:
    # ensure ollama is running first: ollama serve
    python scripts/generate_images.py
    python scripts/generate_images.py --source data/ankiweb-vocab/cards.csv
    python scripts/generate_images.py --model qwen3.5 --images images/
"""

import argparse
import csv
import json
import re
import sys
import time
import urllib.request
from pathlib import Path


OLLAMA_URL    = 'http://localhost:11434/api/generate'
TWEMOJI_URL   = 'https://cdn.jsdelivr.net/gh/jdecked/twemoji@latest/assets/72x72/{codepoints}.png'
EMOJI_RE      = re.compile(r'[0-9*#]\uFE0F\u20E3|[\U00010000-\U0010FFFF]|[\u2600-\u27BF]|[\uFE00-\uFE0F]')


def sanitize(word: str) -> str:
    """Turn an English word into a safe filename stem."""
    return re.sub(r'[^a-z0-9]+', '_', word.lower()).strip('_')


def check_ollama() -> bool:
    try:
        urllib.request.urlopen(f'http://localhost:11434/api/tags', timeout=2)
        return True
    except Exception:
        return False


def ask_ollama(word: str, model: str) -> str:
    """Ask Ollama for a single emoji representing the word. Returns emoji char or ''."""
    prompt = (
        f"Reply with a single emoji that best represents the concept '{word}'. "
        f"The emoji must unambiguously represent '{word}' itself, not a homophone or lookalike. "
        f"For days or relative-time words (such as 'tomorrow', 'yesterday', 'today', "
        f"'morning', 'afternoon', 'evening'), use a calendar or clock emoji, not a "
        f"sunrise or sunset. "
        f"Reply with ONLY the emoji character, nothing else."
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
            text = data.get('response', '').strip()
            # Extract first emoji from response
            matches = EMOJI_RE.findall(text)
            return matches[0] if matches else ''
    except Exception as e:
        print(f'    Ollama error: {e}')
        return ''


def emoji_to_url(emoji_char: str) -> str:
    """Convert an emoji character to its Twemoji CDN PNG URL."""
    codepoints = '-'.join(
        f'{ord(c):x}' for c in emoji_char if ord(c) != 0xfe0f
    )
    if not codepoints:
        return ''
    return TWEMOJI_URL.format(codepoints=codepoints)


def download_png(url: str, dest: Path) -> bool:
    """Download a PNG from url to dest. Returns True on success."""
    try:
        urllib.request.urlretrieve(url, dest)
        return True
    except Exception as e:
        print(f'    Download failed ({url}): {e}')
        if dest.exists():
            dest.unlink()
        return False


def main():
    parser = argparse.ArgumentParser(description='Generate emoji images for vocabulary words')
    parser.add_argument('--source', default=None,
                        help='cards.csv to read words from (default: all B_parsed/*/cards.csv)')
    parser.add_argument('--model',  default='qwen3.5', help='Ollama model to use')
    parser.add_argument('--images', default=None, help='Output image directory (default: C_enriched/<source>/images/)')
    args = parser.parse_args()

    sources = [Path(args.source)] if args.source else sorted(Path('B_parsed').glob('*/cards.csv'))

    if args.images:
        images_dir = Path(args.images)
    elif args.source:
        images_dir = Path('C_enriched') / Path(args.source).parent.name / 'images'
    else:
        print('ERROR: --images required when no --source given (no single source to default to)')
        sys.exit(1)
    images_dir.mkdir(parents=True, exist_ok=True)
    cards = {}  # card_id → english word
    for src in sources:
        with open(src, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                cid  = row.get('id', '').strip()
                word = row.get('english', '').strip()
                if cid and word:
                    cards[cid] = word

    # Filter to only missing images
    missing = {cid: word for cid, word in cards.items() if not (images_dir / f'{cid}.png').exists()}

    if not missing:
        print(f'All {len(cards)} images already exist. Nothing to do.')
        return

    print(f'{len(cards)} cards total, {len(missing)} images missing.')

    if not check_ollama():
        print('ERROR: Ollama is not running. Start it with: ollama serve')
        sys.exit(1)

    emoji_cache: dict[str, str] = {}  # english → emoji (avoids double-querying same word)
    ok = skipped = failed = 0
    for cid, word in sorted(missing.items(), key=lambda x: x[1]):
        dest = images_dir / f'{cid}.png'
        print(f'  {word!r}', end=' → ', flush=True)

        if word in emoji_cache:
            emoji = emoji_cache[word]
        else:
            emoji = ask_ollama(word, args.model)
            if emoji:
                emoji_cache[word] = emoji
        if not emoji:
            print('no emoji returned, skipping')
            skipped += 1
            continue

        url = emoji_to_url(emoji)
        if not url:
            print(f'{emoji} → no Twemoji URL, skipping')
            skipped += 1
            continue
        print(f'{emoji} → {dest.name}', end=' ', flush=True)

        if download_png(url, dest):
            print('✓')
            ok += 1
        else:
            print('✗')
            failed += 1

        time.sleep(0.1)  # be polite to the CDN

    print(f'\nDone: {ok} downloaded, {skipped} skipped (no emoji), {failed} failed.')
    if failed:
        print('Tip: delete failed entries and rerun to retry.')


if __name__ == '__main__':
    main()
