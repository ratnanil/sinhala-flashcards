#!/usr/bin/env python3
"""
Build a Flashcard Deluxe import file from a cards.csv.

Uses the "new import format" with a named header row, supporting text, audio, and categories.
Output is a tab-separated .txt file ready to paste into the Flashcard Deluxe upload page.
Audio files must be uploaded separately via the "Upload Pictures / Sounds" page.

Column mapping (Flashcard Deluxe names):
    Text 1      = side 1 text (question, e.g. german or english)
    Text 2      = side 2 text (answer, i.e. sinhala)
    Sound 2     = audio filename for side 2
    Category 1  = category (optional)

Usage:
    # English → Sinhala with audio
    python scripts/build_deck.py --source data/ankiweb-vocab/cards.csv

    # German → Sinhala with audio (once german column is populated)
    python scripts/build_deck.py --source data/master.csv --side1 german

    # Custom output path
    python scripts/build_deck.py --source data/ankiweb-vocab/cards.csv --out output/vocab.txt
"""

import argparse
import csv
import re
import shutil
from pathlib import Path


def sanitize(word: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', word.lower()).strip('_')


def load_translations(path: Path) -> dict:
    """Return {english: german} from a translations join table CSV."""
    if not path.exists():
        return {}
    with open(path, newline='', encoding='utf-8') as f:
        return {row['english']: row['german'] for row in csv.DictReader(f)}


def load_tts_audio(path: Path, lang: str) -> dict:
    """Return {card_id: audio_filename} for a given lang from tts_audio.csv."""
    if not path.exists():
        return {}
    with open(path, newline='', encoding='utf-8') as f:
        return {row['id']: row['audio_file']
                for row in csv.DictReader(f) if row['lang'] == lang}


def main():
    parser = argparse.ArgumentParser(description='Build Flashcard Deluxe import file')
    parser.add_argument('--source',   required=True,    help='Path to cards CSV')
    parser.add_argument('--side1',    default='english', help='CSV column for side 1 (default: english)')
    parser.add_argument('--side2',    default='sinhala', help='CSV column for side 2 (default: sinhala)')
    parser.add_argument('--side3',    default='',        help='CSV column for side 3, e.g. romanized (default: none)')
    parser.add_argument('--audio',    default='audio_file', help='CSV column for audio filename (default: audio_file)')
    parser.add_argument('--category', default='category',   help='CSV column for category (default: category)')
    parser.add_argument('--out',      default=None,         help='Output file (default: output/<source_dir>.txt)')
    parser.add_argument('--images',       default='images',              help='Directory of pre-generated emoji PNGs (default: images/)')
    parser.add_argument('--source-deck',  default=None,
                        help='Only include cards where source_deck matches this value')
    parser.add_argument('--image-key',    default=None,
                        help='CSV column to use for image lookup (default: same as --side1)')
    parser.add_argument('--translations', default='data/translations.csv',
                        help='EN→DE join table CSV (default: data/translations.csv, skipped if missing)')
    parser.add_argument('--tts-audio',   default='data/tts_audio.csv',
                        help='TTS audio join table CSV (default: data/tts_audio.csv, skipped if missing)')
    parser.add_argument('--audio-root',  default='data',
                        help='Root directory to search for audio (default: data/)')
    args = parser.parse_args()

    source       = Path(args.source)
    images_dir   = Path(args.images)
    audio_root   = Path(args.audio_root)

    # Build a unified audio map: filename → full path.
    # Raw originals come from raw/audio/*/, enhanced from <audio-root>/*/audio_enhanced/.
    # Enhanced is scanned second so it overwrites originals for the same filename.
    audio_map: dict[str, Path] = {}
    for audio_dir in sorted(Path('raw/audio').glob('*')):
        if audio_dir.is_dir():
            for f in audio_dir.iterdir():
                if f.is_file():
                    audio_map[f.name] = f
    for audio_dir in sorted(audio_root.glob('*/audio_enhanced')):
        for f in audio_dir.iterdir():
            if f.is_file():
                audio_map[f.name] = f  # overrides original
    translations = load_translations(Path(args.translations))
    if translations:
        print(f'Loaded {len(translations)} translations from {args.translations}')
    tts_audio_si = load_tts_audio(Path(args.tts_audio), lang='si')
    tts_audio_de = load_tts_audio(Path(args.tts_audio), lang='de')
    if tts_audio_si or tts_audio_de:
        print(f'Loaded TTS audio: {len(tts_audio_si)} Sinhala, {len(tts_audio_de)} German')
    out_path   = Path(args.out) if args.out else Path('output') / f'{source.parent.name}.txt'
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    has_audio    = False
    has_audio_de = False
    has_category = False
    has_image    = False
    has_side3    = False

    with open(source, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if args.source_deck and row.get('source_deck', '') != args.source_deck:
                continue

            # Respect status column (review CSVs): only include approved cards
            status = row.get('status', '').strip().lower()
            if status and status != 'ok':
                continue

            # Apply hand-curated fixes from review CSVs
            if row.get('sinhala_fix', '').strip():
                row['sinhala'] = row['sinhala_fix'].strip()
            if row.get('english_fix', '').strip():
                row['english'] = row['english_fix'].strip()

            # Fill Sinhala audio from TTS join table if not already set in source
            if tts_audio_si and not row.get('audio_file', '').strip():
                row['audio_file'] = tts_audio_si.get(row.get('id', ''), '')

            # Fill german column from join table if not already set in source
            if translations and not row.get('german', '').strip():
                english = row.get('english', '').strip()
                if english in translations:
                    row['german'] = translations[english]

            s1    = row.get(args.side1,    '').strip()
            s2    = row.get(args.side2,    '').strip()
            audio = row.get(args.audio,    '').strip()
            cat   = row.get(args.category, '').strip()

            if not s1 or not s2:
                print(f'  SKIP (empty side): {row}')
                continue

            # Look for a pre-generated image keyed by the image-key column (default: side1)
            img_key  = row.get(args.image_key or args.side1, s1).strip()
            img_file = images_dir / f'{sanitize(img_key)}.png'
            img = img_file.name if img_file.exists() else ''

            # German audio (side 1) from TTS join table
            audio_de = tts_audio_de.get(row.get('id', ''), '')

            s3 = row.get(args.side3, '').strip() if args.side3 else ''

            rows.append({'s1': s1, 's2': s2, 's3': s3, 'audio': audio, 'audio_de': audio_de,
                         'category': cat, 'image': img})
            if audio:    has_audio    = True
            if audio_de: has_audio_de = True
            if cat:      has_category = True
            if img:      has_image    = True
            if s3:       has_side3    = True

    # Build header
    header = ['Text 1', 'Text 2']
    if has_side3:    header.append('Text 3')
    if has_image:    header.append('Picture 1')
    if has_audio_de: header.append('Sound 1')
    if has_audio:    header.append('Sound 2')
    if has_category: header.append('Category 1')

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\t'.join(header) + '\n')
        for row in rows:
            cols = [row['s1'], row['s2']]
            if has_side3:    cols.append(row['s3'])
            if has_image:    cols.append(row['image'])
            if has_audio_de: cols.append(row['audio_de'])
            if has_audio:    cols.append(row['audio'])
            if has_category: cols.append(row['category'])
            f.write('\t'.join(cols) + '\n')

    print(f'{len(rows)} cards → {out_path}')
    print(f'  columns: {", ".join(header)}')
    if has_image:
        img_count = sum(1 for r in rows if r['image'])
        print(f'  images: {img_count}/{len(rows)} cards have an image')

    # Copy audio files into "<deck name> Media/" alongside the .txt
    # This matches the Dropbox/Google Drive folder convention Flashcard Deluxe expects.
    if has_audio:
        audio_dst = out_path.parent / f'{out_path.stem} Media'
        audio_dst.mkdir(exist_ok=True)
        copied = skipped = 0
        for row in rows:
            if not row['audio']:
                continue
            src = audio_map.get(row['audio'])
            if src:
                shutil.copy2(src, audio_dst / row['audio'])
                copied += 1
            else:
                print(f'  WARNING: audio file not found: {row["audio"]}')
                skipped += 1
        print(f'  audio: {copied} files → {audio_dst}/' +
              (f' ({skipped} missing)' if skipped else ''))

    # Copy German TTS audio into the Media folder
    if has_audio_de:
        audio_src = Path('data/tts')
        media_dst = out_path.parent / f'{out_path.stem} Media'
        media_dst.mkdir(exist_ok=True)
        copied = skipped = 0
        for row in rows:
            if not row['audio_de']:
                continue
            src = audio_src / row['audio_de']
            if src.exists():
                shutil.copy2(src, media_dst / row['audio_de'])
                copied += 1
            else:
                print(f'  WARNING: German audio missing: {src}')
                skipped += 1
        print(f'  German audio: {copied} files → {media_dst}/' +
              (f' ({skipped} missing)' if skipped else ''))

    # Copy emoji images into the Media folder
    if has_image:
        media_dst = out_path.parent / f'{out_path.stem} Media'
        media_dst.mkdir(exist_ok=True)
        copied = 0
        for row in rows:
            if not row['image']:
                continue
            src = images_dir / row['image']
            shutil.copy2(src, media_dst / row['image'])
            copied += 1
        print(f'  images: {copied} files → {media_dst}/')


if __name__ == '__main__':
    main()
