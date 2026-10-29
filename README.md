# Sinhala Flashcards

Goal: create flashcard decks for the mobile app **Flashcard Deluxe** to learn colloquial/spoken
Sinhala as a German speaker. Some decks must be suitable for non-reading children, requiring
images and audio on every card.

## Challenges

- Sinhala is a low-resource language: very few open datasets exist
- Colloquial spoken Sinhala differs substantially from written/formal Sinhala — most textbook
  material teaches the wrong register
- Audio requires either human recordings or a TTS that actually supports Sinhala
- Images for children's decks need to be simple, recognisable, and freely licensed
- No Sinhala–German parallel data exists; translation must go via English

## Decks

| Short name | Source | Output file |
|------------|--------|-------------|
| **ankiweb-vocab** | `A_raw/ankiweb-vocab/apkg/ankiweb-vocab.apkg` | `D_output/Deutsch Sinhala.txt` |
| **omniglot-phrases** | `B_parsed/omniglot-phrases/cards.csv` (parsed from HTML, one-off) | `D_output/Omniglot Phrasen.txt` |

The pipeline runs per-deck. Each deck has its own translations file so German translations
never bleed across decks.

## Pipeline

Four stages: `A_raw/` → `B_parsed/` → `C_enriched/` → `D_output/`

Every step has a per-deck target and an aggregate that runs all decks:

```bash
# ── A → B: parse ─────────────────────────────────────────────────────────────
make parse-ankiweb-vocab        # extract .apkg → B_parsed/ankiweb-vocab/cards.csv
make parse-omniglot-phrases     # parse HTML    → B_parsed/omniglot-phrases/cards.csv
make parse-ilovelanguages       # parse HTML    → B_parsed/ilovelanguages/cards.csv
make parse-everflip-sinhala     # extract 8 .apkg files → B_parsed/everflip-sinhala/cards.csv
                                # ↳ curate B_parsed/<deck>/cards.csv and A_raw/<deck>/fixes.csv by hand

# ── B → C: enrich ────────────────────────────────────────────────────────────
make enrich-enhance-<deck>      # ffmpeg: highpass + noise reduction + loudnorm
                                # A_raw/<deck>/audio/ → B_parsed/<deck>/audio_enhanced/
make enrich-romanize-<deck>     # IAST transliteration → B_parsed/<deck>/cards.csv (romanized col)
make enrich-translate-<deck>    # EN→DE via DeepL      → C_enriched/<deck>/translations/translations.csv
make enrich-tts-<deck>          # German TTS           → C_enriched/<deck>/audio/<card_id>_de.mp3
# make enrich-images-<deck>       # emoji PNGs via Ollama → C_enriched/<deck>/images/<card_id>.png CURRENTLY NOT IN USE

# ── C → D: build ─────────────────────────────────────────────────────────────
make deck-ankiweb-vocab         # → D_output/Deutsch Sinhala.txt + Media/
make deck-omniglot-phrases      # → D_output/Omniglot Phrasen.txt + Media/

# ── deploy ───────────────────────────────────────────────────────────────────
make deploy-ankiweb-vocab       # rclone → Dropbox/Flashcards Deluxe/
make deploy-omniglot-phrases
```

Aggregate targets (`make parse`, `make enrich-translate`, `make deck`, …) run all decks at once.
`A_raw/<deck>/fixes.csv` is the curate layer — blacklist cards or override field values by card ID. Survives a full `B_parsed/` wipe.

## TTS audio

All TTS uses edge-tts (Microsoft neural voices, online). Requires internet at generation time
but only needs to run once. Install: `pip install edge-tts`.

Generated audio is stored in `C_enriched/<source>/audio/` as `<card_id>_<lang>.mp3`.
File existence is the source of truth — no registry file needed.

### German (side 1) — active

Voice: `de-CH-LeniNeural` (Swiss German female). Enabled in `make enrich-tts`.

### Sinhala (side 2) — deferred

Only needed for everflip cards (vocab cards have human recordings). Deferred until everflip cards
are included in the build. Voice to use: `si-LK-SameeraNeural` (male, chosen after comparing
both si-LK voices). Use `make enrich-tts-si-<deck>` when ready (deferred until everflip cards are included).

### Dead end: Piper TTS — `chan4lk/piper-tts-sinhala`

Tested `si_LK-sinhala-medium.onnx` (the only available Sinhala Piper model). Very fast on GPU
via ONNX, but audio quality was not usable. Discarded.

### Not evaluated: VITS — `deathlegionteam/sinhala-tts-vits`

Potentially higher quality but significantly more complex setup (Coqui TTS stack). Could be
worth trying if edge-tts Sinhala quality proves insufficient.

## Target apps

### Flashcard Deluxe (primary)

Uses the "new import format": a tab-separated `.txt` (or `.xlsx`) file with a named **header
row**. The header labels tell the app what each column contains. Up to 5 text sides, 5 pictures,
5 sounds, and 4 categories are supported.

```
Text 1	Text 2	Sound 2	Category 1
banana	කෙසෙල්	banana.mp3	fruits
```

Column names: `Text 1`…`Text 5`, `Sound 1`…`Sound 5`, `Picture 1`…`Picture 5`,
`Category 1`…`Category 4`. The number is the card side.

#### Import methods

**Dropbox (recommended for media decks)**

rclone remote name: `Dropbox` (configured with personal Google account login).
Dropbox path: `Flashcards Deluxe/` (root level — requires Full Dropbox access scope, not App folder).

Place files in the `Flashcards Deluxe` folder in Dropbox. Media files go in a subfolder named
`<deck name> Media` at the same level (e.g. deck `Sinhala Vocab.txt` → media folder
`Sinhala Vocab Media/`). In the app: `+` → Dropbox.

**Note: use Full Dropbox access**

In Flashcard Deluxe's Dropbox settings, choose **Full Dropbox** (not App folder). With App folder
access each device gets its own sandboxed folder (`Apps/Flashcards Deluxe (1)`, etc.), so multiple
devices can't share the same deck. With Full Dropbox access all devices read from the same
`Flashcards Deluxe/` folder at the Dropbox root.

```
Dropbox/Flashcards Deluxe/
├── Sinhala Vocab.txt
└── Sinhala Vocab Media/
    ├── rec1590325441.mp3
    └── ...
```

**Google Drive**

Same folder/media convention as Dropbox, but inside a `Flashcards Deluxe` folder on Drive.
In the app: `+` → Google Drive.

**OrangeOrApple.com (text only, or media uploaded separately)**

Paste text into the upload box, set a Deck Code. For media: also upload a zip via
"Upload Pictures / Sounds". In the app: `+` → Private Deck → enter Deck Code.

**USB**

Text-only. Copy `.txt` to `\Android\data\com.orangeorapple.flashcards\files\` (Android) or
via iTunes File Sharing (iOS). In the app: `+`.

#### Notes
- File encoding must be **UTF-8** (or Unicode/UTF-16) for Sinhala script
- Filenames in the spreadsheet must exactly match the uploaded/synced media filenames

### Mnemosyne (alternative worth exploring)

Open-source spaced-repetition app (mnemosyne-proj.org). No pre-made Sinhala decks found on their
website, but the format is open and the app is actively maintained. Could be a better long-term
target than Flashcard Deluxe.

## Data sources

### Active: `A_raw/ankiweb-vocab/apkg/ankiweb-vocab.apkg`

108 vocabulary cards, Sinhala → English, with one human MP3 recording per card.

Categories: fruits, clothing, days of the week, colors, time words, ~50 colloquial verbs
(infinitive `-න්න` form), question words, adjectives/adverbs.

**Source:** AnkiWeb shared deck ID 505727396 — https://ankiweb.net/shared/info/505727396
**Download:** manual (via AnkiWeb "Download" button), no username or author information available.

Ingested via `scripts/ingest.py` → `B_parsed/ankiweb-vocab/cards.csv`; recordings in `A_raw/ankiweb-vocab/audio/`.

### Active: `A_raw/everflip-sinhala/apkg/*.apkg` (8 decks, merged)

~100 cards across 8 thematic decks: colors (12), days (11), family (12), greetings (11),
nouns (15), numbers (15), politeness (12), questions (12). No audio. Sinhala → English only.

The English field contains embedded romanization and usage notes, e.g.:
`"Hello / Goodbye (āyubōwan; lit. 'may you live long' — standard polite greeting)"` — these
should be parsed into separate `english`, `romanized`, and `notes` columns during export.

Some overlap with `ankiweb-vocab.apkg` in colors and days; the vocab deck has audio,
the everflip decks have romanization. The two complement each other well.

### Unexplored: GitHub / Kaggle

Not yet searched. Kaggle datasets and GitHub repositories may have Sinhala wordlists or
parallel corpora.

### Plan B: translate another language's deck

If no sufficient Sinhala source data is found, take a well-resourced language deck (e.g. a
complete German–English or German–Tamil deck) and machine-translate the target side to Sinhala.
Quality risk: machine translation into Sinhala is poor. Last resort only.

### Dead end: Noji (noji.io)

Noji has a library of pre-made decks, including Sinhala content. However, Noji only allows
exporting decks you created yourself — decks imported or duplicated from another user cannot be
exported. This is a Noji platform restriction, not a tooling limitation. A third-party converter
exists at nojitoanki.com but is subject to the same restriction.

### Dead end: Quizlet

Quizlet has community decks including some Sinhala content. Export requires a third-party Chrome
extension (chromewebstore.google.com). However, Quizlet only exports decks you own — community
decks cannot be exported. Same fundamental restriction as Noji.

### Dead end: Tatoeba

Downloaded `sin_sentences.tsv` (75 Sinhala sentences) and `deu_sentences.tsv.bz2` (783k German
sentences) plus `links.tar.bz2` and `sentences_base.tar.bz2`.

Discarded because:
- Only 75 Sinhala sentences exist in the entire Tatoeba corpus — too small to be useful
- The German and Sinhala files are not directly linked (require cross-referencing `links.csv`)
- Several sentences contained vulgar content
- Sentences only, no vocabulary

## Images for children's decks

Emoji PNGs from [jdecked/twemoji](https://github.com/jdecked/twemoji) (CC-BY 4.0, 72×72px),
served via jsDelivr CDN. Stored in `C_enriched/<source>/images/<card_id>.png`, keyed by card ID.
`build_deck.py` automatically includes `Picture 1` for any card that has a matching image file.

Generation uses Ollama (`qwen3.5`, `--think false`) to pick an emoji per English word, then
downloads the corresponding Twemoji PNG. Runs in ~2 minutes for ~180 words.

```bash
make enrich-images                       # all decks; safe to rerun; requires ollama serve
make enrich-images-ankiweb-vocab         # single deck
```

Notes:
- Numbers 1–9 map to keycap emoji (1️⃣–9️⃣); larger numbers are skipped (no suitable emoji)
- Images are looked up by card ID (`{card_id}.png`), independent of which side is displayed

## Translation (EN → DE)

Stored in `C_enriched/<source>/translations/translations.csv` as a join table (`id,english,german`),
keyed by card ID. The `english` column is included for readability. One file per source deck.

`build_deck.py` auto-loads translations at build time and fills the `german` column by card ID.

```bash
make enrich-translate                        # all decks; safe to rerun; requires DEEPL_API_KEY
make enrich-translate-ankiweb-vocab          # single deck
python scripts/generate_translations.py --force   # retranslate everything
```

Uses DeepL API. Set the key before running:

```bash
export DEEPL_API_KEY=your-key-here   # free keys end with :fx
```

Verbs sent as "to X" → infinitive; nouns sent as "the X" → article + noun.
~0.2 s per word. Free tier (500k chars/month) is sufficient.

## Directory structure

```
Sinhala-Flashcards/
├── A_raw/                    immutable source files, one subdirectory per source
│   └── <source>/
│       ├── apkg/           source .apkg files (for Anki-derived sources)
│       ├── audio/          human recordings (never modified)
│       ├── html/           scraped source HTML (for HTML-parsed sources)
│       └── fixes.csv       blacklist/replace rules (hand-edited; survives B_parsed wipe)
├── B_parsed/                 cleaned card data (deterministic; editable)
│   └── <deck>/
│       ├── cards.csv           canonical card data per deck
│       └── audio_enhanced/     ffmpeg-processed recordings (make enrich-enhance)
├── C_enriched/               generated assets (expensive, non-deterministic)
│   └── <source>/
│       ├── cards.csv               enriched snapshot written by make deck-<deck>
│       ├── translations/
│       │   └── translations.csv    id, english, german — keyed by card ID
│       ├── images/                 <card_id>.png — emoji PNGs
│       └── audio/                  <card_id>_<lang>.mp3 — TTS audio
├── D_output/                 final Flashcard Deluxe import files + Media/ folders
│   └── Deutsch Sinhala.txt
└── scripts/
    ├── export_apkg.py          extract .apkg → CSV + audio
    ├── ingest.py               extract .apkg → B_parsed/<source>/cards.csv (append-only)
    ├── generate_images.py      generate emoji PNGs via Ollama + Twemoji (make enrich-images)
    ├── generate_translations.py  EN→DE translations via DeepL (make enrich-translate)
    ├── build_deck.py           assemble final Flashcard Deluxe .txt + Media/
    ├── generate_audio.py       TTS for cards without recordings (make enrich-tts)
    ├── enhance_audio.py        ffmpeg audio quality enhancement (make enrich-enhance)
    └── generate_romanization.py  IAST transliteration of Sinhala script (make enrich-romanize)
```

### `build_deck.py` key flags

| Flag | Default | Purpose |
|------|---------|---------|
| `--source` | *(required)* | Input CSV, e.g. `B_parsed/ankiweb-vocab/cards.csv` |
| `--side1` | `english` | Column for side 1 text |
| `--side2` | `sinhala` | Column for side 2 text |
| *(images)* | by card ID | Images looked up as `C_enriched/<source>/images/{card_id}.png` |
| `--source-deck` | *(all)* | Filter to one source deck, e.g. `ankiweb-vocab` |
| `--translations` | `C_enriched/<source>/translations.csv` | EN→DE join table; auto-detected per source, skipped if missing |

## Current state & next steps

**Done:**
- Full pipeline from `.apkg` → Dropbox → Flashcard Deluxe app (tested and working)
- 108-card vocab deck with human audio: exported, reviewed, built, deployed
- 73-card Omniglot phrases deck: parsed from HTML, reviewed, built, deployed
- 8 everflip decks: exported and reviewed (all approved), excluded from build until TTS audio is added
- `make enrich-images` / `make enrich-images-<deck>` working: emoji PNGs via Ollama + Twemoji, keyed by card ID
- `make enrich-translate` / `make enrich-translate-<deck>` working: per-deck EN→DE translations (no cross-deck bleed)
- `make enrich-tts` / `make enrich-tts-<deck>` generates German TTS (`de-CH-LeniNeural`)
- `make enrich-enhance` / `make enrich-enhance-<deck>` improves audio quality (highpass + afftdn noise reduction + loudnorm)
- `make enrich-romanize` / `make enrich-romanize-<deck>` generates IAST transliteration; displayed as Text 3
- Multi-device Dropbox sync: switched to Full Dropbox access; all devices share `Flashcards Deluxe/`

**Next:**
1. Add everflip cards to the build and run `make enrich-tts-si-<deck>` for Sinhala TTS
2. Search GitHub / Kaggle for additional Sinhala data

### ✓ Done: Pseudo-phonetics (romanized Sinhala)

Goal: display romanized Sinhala on cards so hearing-impaired learners (or beginners not yet reading
the script) can follow along without audio.

**Implementation:** `scripts/generate_romanization.py` — custom IAST transliteration via Unicode
lookup table (no LLM needed; Sinhala is a phonetic abugida so pronunciation is fully predictable
from the script). Algorithm: consonant + inherent 'a'; virama suppresses vowel; vowel diacritics
replace inherent vowel.

Output uses IAST diacritics (ā, ī, ū, ṭ, ś, etc.) — accurate for linguists and precise enough
for learners. Wired into both decks as `Text 3` via `--side3 romanized` flag on `build_deck.py`.

Rerun with: `make enrich-romanize` (skips existing values; use `--force` to overwrite all).

**Optional follow-up:** add a reading guide card (or card back annotation) explaining the IAST
symbols to German speakers — e.g. "ā = langes a wie in 'Vater'", "ś = sch".

### ✓ Done: Improve vocab recording quality

Originals in `A_raw/ankiweb-vocab/audio/` (never modified).
Enhanced files in `B_parsed/ankiweb-vocab/audio_enhanced/` — picked up automatically
by `build_deck.py` (overrides originals for matching filenames).

Filters applied: `highpass=f=80` → `afftdn=nr=20:nf=-40` → `loudnorm=I=-16`.
Result: mean volume −44 dB → −20 dB; background noise substantially reduced.
Rerun with: `make enrich-enhance` (skips already-processed files; use `--force` to redo all).

### Possible future source: Cornell Basic Dialogs

22 MP3s of English–Sinhala dialog recordings from a Cornell language course. Not currently in
the repo (removed to keep it lean), but worth revisiting as a source for a conversational deck.

**Key challenge:** recordings mix English narration ("Now repeat...") with the actual phrases.
Pipeline would require Whisper ASR with mixed-language handling, dialog parsing, and ffmpeg
slicing — significant effort. Look for pre-segmented Sinhala audio (OpenSLR, Hugging Face,
Mozilla Common Voice) before investing in this.

### ✓ Done: Parse Omniglot phrases HTML → CSV

Source: `A_raw/omniglot-phrases/html/omniglot-phrases.html` — the Omniglot "Useful phrases in Sinhala" page,
73 English→Sinhala phrases. Audio files in `A_raw/omniglot-phrases/audio/` (43 of 73 have audio).

**Source URL:** https://www.omniglot.com/language/phrases/sinhala.htm (saved manually).

Parsed via `scripts/parse_omniglot.py` (`make parse-omniglot-phrases`) into
`B_parsed/omniglot-phrases/cards.csv` → `D_output/Omniglot Phrasen.txt` + Media/.
The HTML was downloaded once; the parser runs from the saved file and is fully repeatable.
