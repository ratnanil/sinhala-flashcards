#!/usr/bin/env python3
"""
One-off parser: raw/html/omniglot-phrases.html → data/omniglot-phrases/cards.csv

The HTML table has English → Sinhala rows. Each Sinhala cell may contain
multiple variants (separated by <br /> or newlines), each with optional
audio link and romanization in parentheses.

Output columns: english, sinhala, romanized, audio_file, notes

Review the CSV by hand after running — a few edge cases may need manual fixes.
"""

import csv
import html
import re
from pathlib import Path

HTML_FILE = Path("raw/html/omniglot-phrases.html")
OUT_CSV   = Path("data/omniglot-phrases/cards.csv")


def unescape(s):
    return html.unescape(s)

def strip_tags(s):
    return re.sub(r'<[^>]+>', '', s)

def clean(s):
    return unescape(strip_tags(s)).strip()

def has_sinhala(s):
    return any('\u0D80' <= c <= '\u0DFF' for c in s)


def parse_english_cell(cell):
    """Return (english, notes). Notes come from <em>...</em> or trailing parens."""
    em = re.search(r'<em>([^<]*)</em>', cell)
    notes = clean(em.group(1)) if em else ''
    english = clean(re.sub(r'<em>[^<]*</em>', '', cell))
    # Remove trailing parens that are notes, not translations
    english = re.sub(r'\s*\([^)]*\)\s*$', '', english).strip()
    return english, notes


def parse_sinhala_cell(cell):
    """
    Return list of (sinhala, romanized, audio_file, variant_note) tuples.

    Handles four segment patterns (after splitting by <br> / newline):
      A) <a href="…/FILE.mp3">SINHALA</a> (roman) [- note]  — audio + inline roman
      B) <a href="…/FILE.mp3">SINHALA</a>                   — audio, roman on next segment
      C) (roman)                                              — roman for previous B segment
      D) SINHALA (roman) [- note]                            — plain text, no audio
    """
    # Strip HTML comments
    cell = re.sub(r'<!--.*?-->', '', cell, flags=re.DOTALL)
    # Normalise <br /> to newline
    cell = re.sub(r'<br\s*/?>', '\n', cell)

    segments = [s.strip() for s in cell.split('\n') if s.strip()]

    variants = []
    pending = None  # (sinhala, audio_file, variant_note) waiting for a romanization

    for seg in segments:
        audio_m = re.search(r'<a\s+href="[^"]*?/([^/"]+\.mp3)">([^<]*)</a>', seg)

        if audio_m:
            # Flush any pending segment that got no romanization
            if pending:
                variants.append((*pending, ''))
                pending = None

            audio_file = audio_m.group(1)
            sinhala    = unescape(audio_m.group(2)).strip()

            # Check for inline content after the </a>
            after = re.sub(r'<a[^>]*>[^<]*</a>', '', seg).strip()
            after = clean(after)

            # Pattern: (roman) [- note]  or  (roman) [= note]
            m = re.match(r'^\(([^)]+)\)\s*(?:[-=]\s*(.*))?$', after)
            if m:
                roman = m.group(1).strip()
                note  = (m.group(2) or '').strip()
                variants.append((sinhala, roman, audio_file, note))
            else:
                # Roman comes on next segment
                note = re.sub(r'^[-=]\s*', '', after).strip() if after else ''
                pending = (sinhala, audio_file, note)

        else:
            # No audio link — plain text segment
            text = clean(seg)
            if not text:
                continue

            # Pattern C: pure romanization "(roman)" for the previous pending
            if re.match(r'^\([^)]+\)$', text) and pending:
                roman = text[1:-1].strip()
                sinhala, audio_file, note = pending
                variants.append((sinhala, roman, audio_file, note))
                pending = None
                continue

            # Pattern D: SINHALA (roman) [- note]  or just SINHALA
            m = re.match(r'^(.*?)\s*\(([^)]+)\)\s*(?:[-=]\s*(.*))?$', text)
            if m and has_sinhala(m.group(1)):
                if pending:
                    variants.append((*pending, ''))
                    pending = None
                sinhala = m.group(1).strip()
                roman   = m.group(2).strip()
                note    = (m.group(3) or '').strip()
                variants.append((sinhala, roman, '', note))
            elif has_sinhala(text):
                if pending:
                    variants.append((*pending, ''))
                pending = (text, '', '')
            else:
                # No Sinhala script (e.g. stray romanised text) — skip
                pass

    if pending:
        variants.append((*pending, ''))

    return variants


def main():
    text = HTML_FILE.read_text(encoding='utf-8')

    div = re.search(r'<div id="unicode">(.*?)</div>', text, re.DOTALL)
    if not div:
        print("ERROR: <div id='unicode'> not found")
        return

    rows = re.findall(r'<tr>(.*?)</tr>', div.group(1), re.DOTALL)
    print(f"Found {len(rows)} rows (including header)")

    cards = []
    for i, row in enumerate(rows):
        cells = re.findall(r'<td>(.*?)</td>', row, re.DOTALL)
        if len(cells) != 2:
            continue
        if i == 0:  # header row
            continue

        english, notes = parse_english_cell(cells[0])
        variants = parse_sinhala_cell(cells[1])

        if not variants:
            print(f"  WARNING row {i}: no variants extracted for {english!r}")
            continue

        for sinhala, romanized, audio_file, variant_note in variants:
            combined_notes = ' | '.join(filter(None, [notes, variant_note]))
            cards.append({
                'english':    english,
                'sinhala':    sinhala,
                'romanized':  romanized,
                'audio_file': audio_file,
                'notes':      combined_notes,
            })

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['english', 'sinhala', 'romanized', 'audio_file', 'notes'])
        w.writeheader()
        w.writerows(cards)

    print(f"{len(cards)} cards → {OUT_CSV}")


if __name__ == '__main__':
    main()
