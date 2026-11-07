#!/usr/bin/env python3
"""
Generate TTS audio for flashcard vocabulary using edge-tts or Piper.

Reads a parsed cards.csv and generates audio for cards that don't have a file
yet. Audio files are written to C_enriched/<source>/audio/ named <card_id>_<lang>.mp3.
Existence of the file is the source of truth — no registry needed.

Usage:
    # German TTS for side 1
    python scripts/generate_audio.py --text-column german --lang de \\
        --voice de-DE-KatjaNeural --source B_parsed/ankiweb-vocab/cards.csv

    # Sinhala TTS for cards without a human recording
    python scripts/generate_audio.py --source B_parsed/ankiweb-vocab/cards.csv

    # Regenerate everything
    python scripts/generate_audio.py --force

edge-tts voices:
    Sinhala: si-LK-SameeraNeural (male, recommended), si-LK-ThiliniNeural (female)
    German:  de-DE-KatjaNeural, de-DE-ConradNeural
"""

import argparse
import csv
import subprocess
import sys
from pathlib import Path


def load_translations(path: Path) -> dict:
    """Return {card_id: german} from translations join table."""
    if not path.exists():
        return {}
    with open(path, newline='', encoding='utf-8') as f:
        return {row['id']: row['german'] for row in csv.DictReader(f)}


def load_cards(source: Path, text_column: str, source_deck: str | None,
               translations: dict) -> list:
    """Return list of {id, text, audio_file} dicts from a cards CSV."""
    cards = []
    with open(source, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if source_deck and row.get('source_deck') != source_deck:
                continue
            text = row.get(text_column, '').strip()
            if not text and translations:
                text = translations.get(row.get('id', '').strip(), '')
            if not text:
                continue
            cards.append({
                'id':         row.get('id', ''),
                'text':       text,
                'audio_file': row.get('audio_file', '').strip(),
            })
    return cards


def synthesize_edge(text: str, voice: str, out_file: Path) -> bool:
    """Run edge-tts to synthesize text to out_file. Returns True on success."""
    # Use SSML with explicit xml:lang to prevent the voice from applying the
    # wrong phoneme set (e.g. de-DE-KatjaNeural reading German as English).
    lang = '-'.join(voice.split('-')[:2])  # "de-DE-KatjaNeural" → "de-DE"
    ssml = (f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis"'
            f' xml:lang="{lang}"><voice name="{voice}">'
            f'<lang xml:lang="{lang}">{text}</lang></voice></speak>')
    try:
        result = subprocess.run(
            ['edge-tts', '--voice', voice, '--ssml', ssml, '--write-media', str(out_file)],
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
    parser.add_argument('--engine',      default='edge-tts', choices=['edge-tts', 'piper'])
    parser.add_argument('--voice',       default='si-LK-SameeraNeural',
                        help='edge-tts voice (default: si-LK-SameeraNeural)')
    parser.add_argument('--model',       default=None,
                        help='Piper .onnx model path (required when --engine piper)')
    parser.add_argument('--source',      default='B_parsed/ankiweb-vocab/cards.csv')
    parser.add_argument('--text-column', default='sinhala',
                        help='CSV column to synthesize (default: sinhala)')
    parser.add_argument('--lang',        default='si',
                        help='Language tag used in output filename, e.g. si or de (default: si)')
    parser.add_argument('--audio-dir',   default=None,
                        help='Output directory (default: C_enriched/<source>/audio/)')
    parser.add_argument('--source-deck', default=None)
    parser.add_argument('--force',       action='store_true',
                        help='Regenerate audio even if the file already exists')
    args = parser.parse_args()

    if args.engine == 'piper' and not args.model:
        print('ERROR: --model is required when using --engine piper')
        sys.exit(1)
    if args.engine == 'piper' and not Path(args.model).exists():
        print(f'ERROR: model not found: {args.model}')
        sys.exit(1)

    source_name       = Path(args.source).parent.name
    enriched          = Path('C_enriched') / source_name
    audio_dir         = Path(args.audio_dir) if args.audio_dir else enriched / 'audio'
    translations_path = enriched / 'translations' / 'translations.csv'

    audio_dir.mkdir(parents=True, exist_ok=True)
    translations = load_translations(translations_path)
    cards        = load_cards(Path(args.source), args.text_column, args.source_deck, translations)
    ext          = 'mp3' if args.engine == 'edge-tts' else 'wav'

    # Skip cards that already have a human recording (Sinhala only)
    # For other langs (German side 1), generate for all cards
    if args.text_column == 'sinhala':
        to_generate = [c for c in cards
                       if not c['audio_file'] and
                       (args.force or not (audio_dir / f"{c['id']}_{args.lang}.{ext}").exists())]
    else:
        to_generate = [c for c in cards
                       if args.force or not (audio_dir / f"{c['id']}_{args.lang}.{ext}").exists()]

    if not to_generate:
        print(f'Nothing to generate ({len(cards)} cards, all already done).')
        return

    print(f'{len(cards)} cards total, {len(to_generate)} need {args.lang} audio.')

    ok = failed = 0
    for card in to_generate:
        filename = f"{card['id']}_{args.lang}.{ext}"
        out_file = audio_dir / filename
        print(f"  {card['text']!r}", end=' → ', flush=True)

        if args.engine == 'edge-tts':
            success = synthesize_edge(card['text'], args.voice, out_file)
        else:
            success = synthesize_piper(card['text'], Path(args.model), out_file)

        if success:
            print(filename)
            ok += 1
        else:
            print('FAILED')
            failed += 1

    print(f'\nDone: {ok} generated, {failed} failed.')
    if failed:
        print('Rerun to retry failed cards.')


if __name__ == '__main__':
    main()
