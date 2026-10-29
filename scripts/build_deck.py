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
    python scripts/build_deck.py --source B_parsed/ankiweb-vocab/cards.csv

    # German → Sinhala with audio (once german column is populated)
    python scripts/build_deck.py --source B_parsed/ankiweb-vocab/cards.csv --side1 german

    # Custom output path
    python scripts/build_deck.py --source B_parsed/ankiweb-vocab/cards.csv --out D_output/vocab.txt
"""

import argparse
import csv
import re
import shutil
from pathlib import Path


def sanitize(word: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', word.lower()).strip('_')


def load_translations(path: Path) -> dict:
    """Return {card_id: german} from a translations join table CSV."""
    if not path.exists():
        return {}
    with open(path, newline='', encoding='utf-8') as f:
        return {row['id']: row['german'] for row in csv.DictReader(f)}


def get_tts_filename(audio_dir: Path, card_id: str, lang: str) -> str:
    """Return TTS audio filename if it exists, else ''."""
    filename = f'{card_id}_{lang}.mp3'
    return filename if (audio_dir / filename).exists() else ''


def load_fixes(cards_path: Path) -> tuple:
    """Load fixes.csv from the same directory as cards.csv.
    Returns (blacklisted_ids, sinhala_replacements, english_replacements).
    """
    fixes_path = cards_path.parent / 'fixes.csv'
    blacklist, sinhala_fixes, english_fixes = set(), {}, {}
    if not fixes_path.exists():
        return blacklist, sinhala_fixes, english_fixes
    with open(fixes_path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            t   = row.get('type', '').strip()
            key = row.get('key', '').strip()
            rep = row.get('replacement', '').strip()
            if not key:
                continue
            if t == 'blacklist':
                blacklist.add(key)
            elif t == 'blacklist_audio':
                blacklist.add(key)   # key is audio filename; matched below
            elif t == 'replace_sinhala':
                sinhala_fixes[key] = rep
            elif t == 'replace_english':
                english_fixes[key] = rep
    return blacklist, sinhala_fixes, english_fixes


def main():
    parser = argparse.ArgumentParser(description='Build Flashcard Deluxe import file')
    parser.add_argument('--source',   required=True,    help='Path to cards CSV')
    parser.add_argument('--side1',    default='english', help='CSV column for side 1 (default: english)')
    parser.add_argument('--side2',    default='sinhala', help='CSV column for side 2 (default: sinhala)')
    parser.add_argument('--side3',    default='',        help='CSV column for side 3, e.g. romanized (default: none)')
    parser.add_argument('--audio',    default='audio_file', help='CSV column for audio filename (default: audio_file)')
    parser.add_argument('--category', default='category',   help='CSV column for category (default: category)')
    parser.add_argument('--out',      default=None,         help='Output file (default: D_output/<source_dir>.txt)')
    parser.add_argument('--images',       default=None,
                        help='Directory of pre-generated emoji PNGs (default: C_enriched/<source>/images/)')
    parser.add_argument('--source-deck',  default=None,
                        help='Only include cards where source_deck matches this value')
    parser.add_argument('--translations', default=None,
                        help='ID→DE join table CSV (default: C_enriched/<source>/translations/translations.csv)')
    args = parser.parse_args()

    source      = Path(args.source)
    source_name = source.parent.name
    enriched    = Path('C_enriched') / source_name
    images_dir        = Path(args.images)      if args.images      else enriched / 'images'
    translations_path = Path(args.translations) if args.translations else enriched / 'translations' / 'translations.csv'
    tts_audio_dir     = enriched / 'audio'

    # Build a unified audio map: filename → full path.
    # Raw originals come from A_raw/*/audio/, enhanced from B_parsed/*/audio_enhanced/.
    # Enhanced is scanned second so it overwrites originals for the same filename.
    audio_map: dict[str, Path] = {}
    for audio_dir in sorted(Path('A_raw').glob('*/audio')):
        if audio_dir.is_dir():
            for f in audio_dir.iterdir():
                if f.is_file():
                    audio_map[f.name] = f
    for audio_dir in sorted(Path('B_parsed').glob('*/audio_enhanced')):
        for f in audio_dir.iterdir():
            if f.is_file():
                audio_map[f.name] = f  # overrides original
    translations = load_translations(translations_path)
    if translations:
        print(f'Loaded {len(translations)} translations from {translations_path}')
    blacklist, sinhala_fixes, english_fixes = load_fixes(source)
    out_path   = Path(args.out) if args.out else Path('D_output') / f'{source.parent.name}.txt'
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    enriched_rows = []
    has_audio    = False
    has_audio_de = False
    has_category = False
    has_image    = False
    has_side3    = False

    with open(source, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if args.source_deck and row.get('source_deck', '') != args.source_deck:
                continue

            # Apply fixes: blacklist by card id or audio filename
            card_id   = row.get('id', '')
            audio_ref = row.get('audio_file', '')
            if card_id in blacklist or audio_ref in blacklist:
                continue

            # Apply text replacements
            if card_id in sinhala_fixes:
                row['sinhala'] = sinhala_fixes[card_id]
            if card_id in english_fixes:
                row['english'] = english_fixes[card_id]

            # Fill Sinhala audio from TTS if not already set in source
            if not row.get('audio_file', '').strip():
                row['audio_file'] = get_tts_filename(tts_audio_dir, card_id, 'si')

            # Fill german column from translations join table if not already set in source
            if translations and not row.get('german', '').strip():
                row['german'] = translations.get(card_id, '')

            s1    = row.get(args.side1,    '').strip()
            s2    = row.get(args.side2,    '').strip()
            audio = row.get(args.audio,    '').strip()
            cat   = row.get(args.category, '').strip()

            if not s1 or not s2:
                print(f'  SKIP (empty side): {row}')
                continue

            # Look for a pre-generated image keyed by card ID
            img_file = images_dir / f'{card_id}.png'
            img = img_file.name if img_file.exists() else ''

            # German audio (side 1) — look up by file existence
            audio_de = get_tts_filename(tts_audio_dir, card_id, 'de')

            s3 = row.get(args.side3, '').strip() if args.side3 else ''

            rows.append({'s1': s1, 's2': s2, 's3': s3, 'audio': audio, 'audio_de': audio_de,
                         'category': cat, 'image': img})
            enriched_rows.append({
                'id':          card_id,
                'source_deck': row.get('source_deck', ''),
                'sinhala':     row.get('sinhala', ''),
                'english':     row.get('english', ''),
                'romanized':   row.get('romanized', ''),
                'audio_si':    audio,
                'german':      row.get('german', ''),
                'audio_de':    audio_de,
                'image':       img,
            })
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
        audio_src = tts_audio_dir
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

    # Write enriched snapshot — one merged CSV per source showing the deck at this stage
    enriched_csv = enriched / 'cards.csv'
    enriched_csv.parent.mkdir(parents=True, exist_ok=True)
    _ENRICHED_FIELDS = ['id', 'source_deck', 'sinhala', 'english', 'romanized',
                        'audio_si', 'german', 'audio_de', 'image']
    with open(enriched_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=_ENRICHED_FIELDS)
        writer.writeheader()
        writer.writerows(enriched_rows)
    print(f'  enriched snapshot → {enriched_csv}')


if __name__ == '__main__':
    main()
