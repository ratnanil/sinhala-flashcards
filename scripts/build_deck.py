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
    """Load fixes.csv from A_raw/<source>/fixes.csv.
    Returns (blacklisted_ids, sinhala_replacements, english_replacements).
    """
    fixes_path = Path('A_raw') / cards_path.parent.name / 'fixes.csv'
    blacklist, sinhala_fixes, english_fixes, german_fixes = set(), {}, {}, {}
    if not fixes_path.exists():
        return blacklist, sinhala_fixes, english_fixes, german_fixes
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
            elif t == 'replace_german':
                german_fixes[key] = rep
    return blacklist, sinhala_fixes, english_fixes, german_fixes


def merge_variants(rows: list[dict]) -> list[dict]:
    """Group rows by s1, merging sinhala/romanized variants and spreading audio across audio/audio2."""
    seen: dict[str, dict] = {}
    order: list[str] = []
    for row in rows:
        key = row['s1']
        if key not in seen:
            merged = dict(row)
            merged['audio2'] = ''
            seen[key] = merged
            order.append(key)
        else:
            m = seen[key]
            if row['s2'] and row['s2'] not in m['s2'].split(' / '):
                m['s2'] += ' / ' + row['s2']
            if row['s3'] and row['s3'] not in m['s3'].split(' / '):
                m['s3'] += ' / ' + row['s3']
            # s4 (english) is the same for all variants — no merging needed
            if row['audio'] and not m['audio2'] and row['audio'] != m['audio']:
                m['audio2'] = row['audio']
    return [seen[k] for k in order]


def write_deck(rows: list[dict], out_path: Path, audio_map: dict,
               tts_audio_dir: Path, images_dir: Path) -> None:
    """Write one Flashcard Deluxe .txt and copy its media files."""
    has_audio    = any(r['audio']    for r in rows)
    has_audio2   = any(r['audio2']   for r in rows)
    has_audio_de = any(r['audio_de'] for r in rows)
    has_image    = any(r['image']    for r in rows)
    has_side3    = any(r['s3']       for r in rows)
    has_side4    = any(r['s4']       for r in rows)
    has_category = any(r['category'] for r in rows)

    header = ['Text 1', 'Text 2']
    if has_side3:    header.append('Text 3')
    if has_side4:    header.append('Text 4')
    if has_image:    header.append('Picture 1')
    if has_audio_de: header.append('Sound 1')
    if has_audio:    header.append('Sound 2')
    if has_audio2:   header.append('Sound 3')
    if has_category: header.append('Category 1')
    header.append('Extra Info')

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\t'.join(header) + '\n')
        for row in rows:
            cols = [row['s1'], row['s2']]
            if has_side3:    cols.append(row['s3'])
            if has_side4:    cols.append(row['s4'])
            if has_image:    cols.append(row['image'])
            if has_audio_de: cols.append(row['audio_de'])
            if has_audio:    cols.append(row['audio'])
            if has_audio2:   cols.append(row['audio2'])
            if has_category: cols.append(row['category'])
            cols.append(row['id'])
            f.write('\t'.join(cols) + '\n')
    print(f'{len(rows)} cards → {out_path}')
    print(f'  columns: {", ".join(header)}')

    media_dst = out_path.parent / f'{out_path.stem} Media'
    if has_audio or has_audio2:
        media_dst.mkdir(exist_ok=True)
        copied = skipped = 0
        for row in rows:
            for key in ('audio', 'audio2'):
                fname = row.get(key, '')
                if not fname:
                    continue
                src = audio_map.get(fname)
                if src:
                    shutil.copy2(src, media_dst / fname)
                    copied += 1
                else:
                    print(f'  WARNING: audio file not found: {fname}')
                    skipped += 1
        print(f'  audio: {copied} files → {media_dst}/' +
              (f' ({skipped} missing)' if skipped else ''))
    if has_audio_de:
        media_dst.mkdir(exist_ok=True)
        copied = skipped = 0
        for row in rows:
            if not row['audio_de']:
                continue
            src = tts_audio_dir / row['audio_de']
            if src.exists():
                shutil.copy2(src, media_dst / row['audio_de'])
                copied += 1
            else:
                print(f'  WARNING: German audio missing: {src}')
                skipped += 1
        print(f'  German audio: {copied} files → {media_dst}/' +
              (f' ({skipped} missing)' if skipped else ''))
    if has_image:
        media_dst.mkdir(exist_ok=True)
        copied = 0
        for row in rows:
            if not row['image']:
                continue
            shutil.copy2(images_dir / row['image'], media_dst / row['image'])
            copied += 1
        print(f'  images: {copied} files → {media_dst}/')


def main():
    parser = argparse.ArgumentParser(description='Build Flashcard Deluxe import file')
    parser.add_argument('--source',   required=True,    help='Path to cards CSV')
    parser.add_argument('--side1',    default='english', help='CSV column for side 1 (default: english)')
    parser.add_argument('--side2',    default='sinhala', help='CSV column for side 2 (default: sinhala)')
    parser.add_argument('--side3',    default='',        help='CSV column for side 3, e.g. romanized (default: none)')
    parser.add_argument('--side4',    default='',        help='CSV column for side 4, e.g. english (default: none)')
    parser.add_argument('--audio',    default='audio_file', help='CSV column for audio filename (default: audio_file)')
    parser.add_argument('--category', default='category',   help='CSV column for category (default: category)')
    parser.add_argument('--out',      default=None,         help='Output file (default: D_output/<source_dir>.txt)')
    parser.add_argument('--images',       default=None,
                        help='Directory of pre-generated emoji PNGs (default: C_enriched/<source>/images/)')
    parser.add_argument('--source-deck',  default=None,
                        help='Only include cards where source_deck matches this value')
    parser.add_argument('--translations', default=None,
                        help='ID→DE join table CSV (default: C_enriched/<source>/translations/translations.csv)')
    parser.add_argument('--merge-variants', action='store_true',
                        help='Merge cards with the same side-1 text: join sinhala/romanized with " / ", spread audio across Sound 2+3')
    parser.add_argument('--require-audio', action='store_true',
                        help='Skip cards with no Sinhala audio file')
    parser.add_argument('--split-by-category', action='store_true',
                        help='Write one output file per category (filename: <out-stem>-<category>.txt)')
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
    blacklist, sinhala_fixes, english_fixes, german_fixes = load_fixes(source)
    out_path   = Path(args.out) if args.out else Path('D_output') / f'{source.parent.name}.txt'
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    enriched_rows = []
    has_audio    = False
    has_audio_de = False
    has_category = False
    has_image    = False
    has_side3    = False
    has_side4    = False

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
            if card_id in german_fixes:
                row['german'] = german_fixes[card_id]

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
            if args.require_audio and not audio:
                continue

            # Look for a pre-generated image keyed by card ID
            img_file = images_dir / f'{card_id}.png'
            img = img_file.name if img_file.exists() else ''

            # German audio (side 1) — look up by file existence
            audio_de = get_tts_filename(tts_audio_dir, card_id, 'de')

            s3 = row.get(args.side3, '').strip() if args.side3 else ''
            s4 = row.get(args.side4, '').strip() if args.side4 else ''

            rows.append({'s1': s1, 's2': s2, 's3': s3, 's4': s4, 'audio': audio, 'audio2': '',
                         'audio_de': audio_de, 'category': cat, 'image': img})
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
            if s4:       has_side4    = True

    if args.split_by_category:
        cats: dict[str, list] = {}
        for row in rows:
            cats.setdefault(row['category'], []).append(row)
        for cat, cat_rows in cats.items():
            if args.merge_variants:
                cat_rows = merge_variants(cat_rows)
            cat_out = out_path.parent / f'{out_path.stem}-{sanitize(cat)}.txt'
            write_deck(cat_rows, cat_out, audio_map, tts_audio_dir, images_dir)
    else:
        if args.merge_variants:
            rows = merge_variants(rows)
        write_deck(rows, out_path, audio_map, tts_audio_dir, images_dir)

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
