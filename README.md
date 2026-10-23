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
| **vocab** | `anki/Sinhala_to_English_vocab.apkg` | `output/Deutsch Sinhala.txt` |
| **phrases** | `data/sinhalaphrases/cards.csv` (parsed from HTML, one-off) | `output/Omniglot Phrasen.txt` |

The pipeline runs per-deck. Each deck has its own translations file so German translations
never bleed across decks.

## Pipeline

```
── vocab deck ──────────────────────────────────────────────────────────────────

anki/Sinhala_to_English_vocab.apkg
    └─[make export]──────────→ data/Sinhala_to_English_vocab/cards.csv + audio/
    └─[make review]──────────→ review/Sinhala_to_English_vocab.csv   ← curate here
    └─[make approve DECK=…]──→ status: pending → ok / skip

    [make translate]─────────→ data/translations.csv             (EN→DE, vocab only)
    [make images]────────────→ images/<word>.png                 (emoji PNGs)
    [make audio]─────────────→ data/tts/ + data/tts_audio.csv   (German TTS)

    └─[make deck]────────────→ output/Deutsch Sinhala.txt


── phrases deck ────────────────────────────────────────────────────────────────

data/sinhalaphrases/cards.csv  (generated once by scripts/parse_omniglot.py)
    └─[make review]──────────→ review/sinhalaphrases.csv         ← curate here
    └─[make approve DECK=…]──→ status: pending → ok / skip

    [make translate-phrases]─→ data/sinhalaphrases/translations.csv  (EN→DE, phrases only)
    [make audio-phrases]─────→ data/tts/ + data/tts_audio.csv   (German TTS)

    └─[make deck]────────────→ output/Omniglot Phrasen.txt


── notes ───────────────────────────────────────────────────────────────────────

review/<deck>.csv is the canonical source for each deck — hand-edit it directly
to fix Sinhala/English text (sinhala_fix, english_fix columns) or skip cards.

make master  — optional; merges all decks into data/master.csv for inspection
make images  — runs for all decks; emoji PNGs keyed by English word
make deck    — builds all output files in one shot
```

## TTS audio

All TTS uses edge-tts (Microsoft neural voices, online). Requires internet at generation time
but only needs to run once. Install: `pip install edge-tts`.

Generated audio is stored in `data/audio/` and registered in `data/tts_audio.csv` (join table
keyed by card ID + lang), so `make master` never overwrites it.

### German (side 1) — active

Voice: `de-DE-SeraphinaMultilingualNeural` (female, chosen after comparing all 6 de-DE voices).
Generated for all cards. Enabled in `make audio`.

### Sinhala (side 2) — deferred

Only needed for everflip cards (vocab cards have human recordings). Deferred until everflip cards
are included in the build. Voice to use: `si-LK-SameeraNeural` (male, chosen after comparing
both si-LK voices). Line is commented out in `make audio` — uncomment when ready.

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

### Active: `anki/Sinhala_to_English_vocab.apkg`

108 vocabulary cards, Sinhala → English, with one human MP3 recording per card.

Categories: fruits, clothing, days of the week, colors, time words, ~50 colloquial verbs
(infinitive `-න්න` form), question words, adjectives/adverbs.

Exported to `data/` via `scripts/export_apkg.py`.

### Active: `anki/everflip-sinhala-*.apkg` (8 decks)

~100 cards across 8 thematic decks: colors (12), days (11), family (12), greetings (11),
nouns (15), numbers (15), politeness (12), questions (12). No audio. Sinhala → English only.

The English field contains embedded romanization and usage notes, e.g.:
`"Hello / Goodbye (āyubōwan; lit. 'may you live long' — standard polite greeting)"` — these
should be parsed into separate `english`, `romanized`, and `notes` columns during export.

Some overlap with `Sinhala_to_English_vocab.apkg` in colors and days; the vocab deck has audio,
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
served via jsDelivr CDN. Stored in `images/<english_word>.png`, keyed by the English keyword.
`build_deck.py` automatically includes `Picture 1` for any card that has a matching image file.

Generation uses Ollama (`qwen3.5`, `--think false`) to pick an emoji per English word, then
downloads the corresponding Twemoji PNG. Runs in ~2 minutes for ~180 words.

```bash
make images   # generates missing images only, safe to rerun; requires ollama serve
```

Notes:
- Source must be `data/master.csv` (not raw `data/*/cards.csv`) so image filenames match the
  clean English keys that `build_deck.py` looks up at build time
- Numbers 1–9 map to keycap emoji (1️⃣–9️⃣); larger numbers are skipped (no suitable emoji)
- `build_deck.py --image-key english` is needed when side 1 is not English (e.g. German deck)

## Translation (EN → DE)

Stored in `data/translations.csv` as a join table (`english,german`), separate from all source
CSVs so translations can be curated without touching the card data.

`build_deck.py` auto-loads `data/translations.csv` at build time and fills the `german` column
for any card where it is empty. Manually set values in master.csv always take precedence.

```bash
make translate          # translates missing words only, safe to rerun; requires ollama serve
python scripts/generate_translations.py --force   # retranslate everything
```

Model: `qwen3.5` with `--think false`. Prompt asks for the definite article for nouns
(`der/die/das`) and the infinitive for verbs. ~1 s per word.

## Directory structure

```
Sinhala-Flashcards/
├── anki/                   source .apkg files
├── data/                   exported CSVs (data/<deck>/cards.csv + audio/)
│   ├── audio/              human recordings (from .apkg exports, never modified)
│   ├── tts/                TTS-generated audio (make audio), separate from human recordings
│   ├── master.csv          merged + approved cards (generated by make master)
│   ├── translations.csv    EN→DE join table, keyed by English word (make translate)
│   └── tts_audio.csv       TTS audio join table, keyed by card ID + lang (make audio)
├── images/                 emoji PNGs keyed by English word (make images)
├── output/                 final Flashcard Deluxe import files + Media/ folders
│   └── Deutsch Sinhala.txt       German + image → Sinhala + audio deck
├── review/                 human-reviewed CSVs (never overwritten by scripts)
└── scripts/
    ├── export_apkg.py          extract .apkg → CSV + audio
    ├── prepare_review.py       generate review CSVs from exported data
    ├── approve_deck.py         bulk-approve a deck's review CSV
    ├── merge.py                merge approved reviews → master.csv
    ├── generate_images.py      generate emoji PNGs via Ollama + Twemoji (make images)
    ├── generate_translations.py  EN→DE translations via Ollama (make translate)
    ├── build_deck.py           assemble final Flashcard Deluxe .txt + Media/
    ├── generate_audio.py       TTS for cards without recordings (make audio)
    ├── enhance_audio.py        ffmpeg audio quality enhancement (make enhance)
    └── generate_romanization.py  IAST transliteration of Sinhala script (make romanize)
```

### `build_deck.py` key flags

| Flag | Default | Purpose |
|------|---------|---------|
| `--source` | *(required)* | Input CSV (`data/master.csv`) |
| `--side1` | `english` | Column for side 1 text |
| `--side2` | `sinhala` | Column for side 2 text |
| `--image-key` | same as `--side1` | Column used to look up emoji PNG; set to `english` when side 1 is German |
| `--source-deck` | *(all)* | Filter to one source deck, e.g. `Sinhala_to_English_vocab` |
| `--translations` | `data/translations.csv` | EN→DE join table; auto-applied if file exists |

## Current state & next steps

**Done:**
- Full pipeline from `.apkg` → Dropbox → Flashcard Deluxe app (tested and working)
- 108-card vocab deck with human audio: exported, reviewed, built, deployed
- 73-card Omniglot phrases deck: parsed from HTML, reviewed, built, deployed
- 8 everflip decks: exported and reviewed (all approved), excluded from build until TTS audio is added
- `make images` working: ~180 emoji PNGs generated via Ollama + jdecked/twemoji CDN
- `make translate` / `make translate-phrases` working: per-deck EN→DE translations (no cross-deck bleed)
- `make audio` / `make audio-phrases` generates German TTS (`de-DE-SeraphinaMultilingualNeural`)
- `make enhance` improves audio quality (highpass + afftdn noise reduction + loudnorm); both decks
- `make romanize` generates IAST transliteration for all Sinhala text; displayed as Text 3 on cards
- Multi-device Dropbox sync: switched to Full Dropbox access; all devices share `Flashcards Deluxe/`

**Next:**
1. Uncomment Sinhala TTS in `make audio` and include everflip cards in the build
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

Rerun with: `make romanize` (skips existing values; use `--force` to overwrite all).

**Optional follow-up:** add a reading guide card (or card back annotation) explaining the IAST
symbols to German speakers — e.g. "ā = langes a wie in 'Vater'", "ś = sch".

### ✓ Done: Improve vocab recording quality

Originals in `data/Sinhala_to_English_vocab/audio/` (never modified).
Enhanced files in `data/Sinhala_to_English_vocab/audio_enhanced/` — picked up automatically
by `build_deck.py` (overrides originals for matching filenames).

Filters applied: `highpass=f=80` → `afftdn=nr=20:nf=-40` → `loudnorm=I=-16`.
Result: mean volume −44 dB → −20 dB; background noise substantially reduced.
Rerun with: `make enhance` (skips already-processed files; use `--force` to redo all).

### Todo: Import Cornell Basic Dialogs audio

Source: `data/Sinhala Basic Dialogs Cornell/` — 22 MP3s of English–Sinhala dialog recordings
from a Cornell language course.

This is a significant undertaking. The pipeline would be:

```
Cornell Set XX.mp3
    └─[ffmpeg]──────────→ enhanced audio
    └─[Whisper ASR]─────→ timestamped transcript (English + Sinhala segments)
    └─[parse dialogs]───→ per-phrase CSV  (english_phrase, sinhala_phrase, start_ms, end_ms)
    └─[ffmpeg slice]────→ one audio clip per Sinhala phrase
    └─[Ollama translate]─→ english_phrase → german
    └─[edge-tts]────────→ German audio per phrase
    └─[build_deck.py]───→ new Cornell deck
```

**Key challenges:**
- The recordings mix English narration ("Now repeat...") with the actual phrases to learn. The
  English narration must be discarded; only the Sinhala utterances and their English translations
  become cards.
- Whisper needs special handling for mixed-language audio (Sinhala + English in the same file).
  Running with `--language si` mis-transcribes English segments and vice versa.
- Parsing the dialog structure reliably across 22 files requires careful prompt/heuristic work.

**Alternative worth exploring first:** look for Sinhala audio datasets that are already segmented
and labeled (e.g. on OpenSLR, Hugging Face, or Mozilla Common Voice) — these would slot directly
into the pipeline without the transcription/parsing complexity.

### ✓ Done: Parse Omniglot phrases HTML → CSV

Source: `data/sinhalaphrases.html` — an Omniglot page with 73 English→Sinhala phrases.
Audio files in `data/sinhalaphrases/audio/` (43 of 73 cards have audio).

Parsed via `scripts/parse_omniglot.py` (one-off, not in the automated pipeline) into
`data/sinhalaphrases/cards.csv`. Wired into the pipeline as the `phrases` deck:
`review/sinhalaphrases.csv` → `output/Omniglot Phrasen.txt` + Media/.
