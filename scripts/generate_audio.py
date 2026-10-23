#!/usr/bin/env python3
"""
Generate TTS audio for flashcard vocabulary using edge-tts or Piper.

Reads master.csv and generates audio for cards that have no recording yet.
Audio files are written to data/audio/ and registered in data/tts_audio.csv
(a join table keyed by card ID + lang), so make master never overwrites them.

build_deck.py loads tts_audio.csv and uses it to fill in missing audio.

Usage:
    # Sinhala TTS for everflip cards (no human recording) — default
    python scripts/generate_audio.py

    # German TTS for side 1
    python scripts/generate_audio.py --text-column german --lang de \\
        --voice de-DE-ConradNeural

    # Use Piper instead of edge-tts
    python scripts/generate_audio.py --engine piper --model models/si_LK-sinhala-medium.onnx

    # Regenerate everything
    python scripts/generate_audio.py --force

edge-tts voices:
    Sinhala: si-LK-SameeraNeural (male, recommended), si-LK-ThiliniNeural (female)
    German:  de-DE-ConradNeural, de-DE-KatjaNeural

Piper model setup:
    Sinhala: download si_LK-sinhala-medium.onnx + .onnx.json from
             https://huggingface.co/chan4lk/piper-tts-sinhala
    German:  download de_DE-thorsten-high.onnx + .onnx.json from
             https://huggingface.co/rhasspy/piper-voices (de/de_DE/thorsten/high/)
"""

import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path


def sanitize(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', text.lower()).strip('_')


def load_existing(tts_csv: Path) -> set:
    """Return set of (id, lang) already in tts_audio.csv."""
    if not tts_csv.exists():
        return set()
    with open(tts_csv, newline='', encoding='utf-8') as f:
        return {(row['id'], row['lang']) for row in csv.DictReader(f)}


def load_translations(path: Path) -> dict:
    """Return {english: german} from translations join table."""
    if not path.exists():
        return {}
    with open(path, newline='', encoding='utf-8') as f:
        return {row['english']: row['german'] for row in csv.DictReader(f)}


def load_cards(master_csv: Path, text_column: str, source_deck: str | None,
               translations: dict) -> list:
    """Return list of {id, text, audio_file} dicts from master.csv."""
    cards = []
    with open(master_csv, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if source_deck and row.get('source_deck') != source_deck:
                continue
            # Respect status column (review CSVs): only process approved cards
            status = row.get('status', '').strip().lower()
            if status and status != 'ok':
                continue
            # Apply hand-curated fixes
            if row.get('sinhala_fix', '').strip():
                row['sinhala'] = row['sinhala_fix'].strip()
            if row.get('english_fix', '').strip():
                row['english'] = row['english_fix'].strip()
            text = row.get(text_column, '').strip()
            if not text and translations:
                text = translations.get(row.get('english', '').strip(), '')
            if not text:
                continue
            cards.append({
                'id':         row.get('id', ''),
                'english':    row.get('english', '').strip(),
                'text':       text,
                'audio_file': row.get('audio_file', '').strip(),
            })
    return cards


def synthesize_edge(text: str, voice: str, out_file: Path) -> bool:
    """Run edge-tts to synthesize text to out_file. Returns True on success."""
    try:
        result = subprocess.run(
            ['edge-tts', '--voice', voice, '--text', text, '--write-media', str(out_file)],
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0:
            print(f'    edge-tts error: {result.stderr.decode().strip()}')
            return False
        return out_file.exists()
    except FileNotFoundError:
        print('ERROR: edge-tts not found. Install with: pip install edge-tts')
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print('    edge-tts timed out')
        return False


def synthesize_piper(text: str, model: Path, out_file: Path) -> bool:
    """Run piper to synthesize text to out_file. Returns True on success."""
    try:
        result = subprocess.run(
            ['piper', '--model', str(model), '--output_file', str(out_file)],
            input=text.encode('utf-8'),
            capture_output=True,
            timeout=60,
        )
        if result.returncode != 0:
            print(f'    piper error: {result.stderr.decode().strip()}')
            return False
        return out_file.exists()
    except FileNotFoundError:
        print('ERROR: piper not found. Install with: pip install piper-tts')
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print('    piper timed out')
        return False


def main():
    parser = argparse.ArgumentParser(description='Generate TTS audio via edge-tts or Piper')
    parser.add_argument('--engine',      default='edge-tts', choices=['edge-tts', 'piper'],
                        help='TTS engine to use (default: edge-tts)')
    parser.add_argument('--voice',       default='si-LK-SameeraNeural',
                        help='edge-tts voice (default: si-LK-SameeraNeural)')
    parser.add_argument('--model',       default=None,
                        help='Piper .onnx model path (required when --engine piper)')
    parser.add_argument('--source',      default='data/master.csv',
                        help='Cards CSV to read from (default: data/master.csv)')
    parser.add_argument('--text-column', default='sinhala',
                        help='CSV column to synthesize (default: sinhala)')
    parser.add_argument('--lang',        default='si',
                        help='Language tag for the join table, e.g. si or de (default: si)')
    parser.add_argument('--audio-dir',   default='data/tts',
                        help='Directory to write audio files (default: data/tts)')
    parser.add_argument('--tts-csv',     default='data/tts_audio.csv',
                        help='Join table for generated audio (default: data/tts_audio.csv)')
    parser.add_argument('--translations', default='data/translations.csv',
                        help='EN→DE join table to fill missing text (default: data/translations.csv)')
    parser.add_argument('--source-deck', default=None,
                        help='Only process cards from this source deck')
    parser.add_argument('--force',       action='store_true',
                        help='Regenerate audio even if already in tts_audio.csv')
    args = parser.parse_args()

    if args.engine == 'piper' and not args.model:
        print('ERROR: --model is required when using --engine piper')
        sys.exit(1)
    if args.engine == 'piper' and not Path(args.model).exists():
        print(f'ERROR: model not found: {args.model}')
        sys.exit(1)

    audio_dir = Path(args.audio_dir)
    tts_csv   = Path(args.tts_csv)
    audio_dir.mkdir(parents=True, exist_ok=True)

    translations = load_translations(Path(args.translations))
    existing     = set() if args.force else load_existing(tts_csv)
    cards        = load_cards(Path(args.source), args.text_column, args.source_deck, translations)

    ext = 'mp3' if args.engine == 'edge-tts' else 'wav'

    # For Sinhala: skip cards that already have a human recording
    # For other langs: generate for all cards (side 1 audio is always TTS)
    if args.text_column == 'sinhala':
        to_generate = [c for c in cards
                       if not c['audio_file'] and (c['id'], args.lang) not in existing]
    else:
        to_generate = [c for c in cards
                       if (c['id'], args.lang) not in existing]

    if not to_generate:
        print(f'Nothing to generate ({len(cards)} cards, all already done).')
        return

    print(f'{len(cards)} cards total, {len(to_generate)} need {args.lang} audio.')

    write_header = not tts_csv.exists() or args.force
    mode = 'w' if args.force else 'a'

    ok = failed = 0
    with open(tts_csv, mode, newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'lang', 'audio_file'])
        if write_header:
            writer.writeheader()

        for card in to_generate:
            filename = f"{sanitize(card['english'] or card['text'])}_{args.lang}.{ext}"
            out_file = audio_dir / filename
            print(f"  {card['text']!r}", end=' → ', flush=True)

            if args.engine == 'edge-tts':
                success = synthesize_edge(card['text'], args.voice, out_file)
            else:
                success = synthesize_piper(card['text'], Path(args.model), out_file)

            if success:
                print(filename)
                writer.writerow({'id': card['id'], 'lang': args.lang, 'audio_file': filename})
                f.flush()
                ok += 1
            else:
                print('FAILED')
                failed += 1

    print(f'\nDone: {ok} generated, {failed} failed.')
    if failed:
        print('Rerun to retry failed cards.')


if __name__ == '__main__':
    main()
