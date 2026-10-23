# TODO — Pipeline Restructure

## Proposed four-layer model

```
raw/        expensive, sometimes-messy ground truth; treated as immutable by the pipeline
parsed/     structured output from raw; deterministic cleaning and restructuring only;
            fixes applied via explicit rules in fixes.csv
enriched/   LLM-generated additions (TTS, images, translations); expensive, non-deterministic,
            subject to model changes — treat output as a versioned artifact, not always recomputed
output/     final flashcard files; sources can be merged here
```

### Layer principles

- **parsed** should be cheap and fully deterministic. If a bug cannot be fixed by a
  rule in `fixes.csv`, handle it via a manual audit process (see "cleaning prompt" below)
  rather than bending the parsed step.
- **enriched** is the right home for anything that invokes a model, even if the result
  feels like "core" card data (e.g. translations). Enrichment steps may need to be
  re-run when models are swapped out or produce unsatisfactory results.
- **raw** data may come from two sources: hand-collected files (recordings, `.apkg`) that
  are truly irreplaceable, and script-acquired data (scraped/downloaded) that is
  reproducible in principle but whose acquisition scripts go stale quickly and should
  not require frequent re-running. Both are treated identically once they land in `raw/`.
  Acquisition scripts live in `scripts/acquire/` and are best-effort provenance
  documentation, not part of the regular pipeline.

---

## Review of the proposal against the current repo

### What maps cleanly

| Proposed layer | Current location |
|---|---|
| raw — .apkg files | `anki/` |
| raw — phrase recordings | `data/omniglot-phrases/audio/` |
| raw — vocab recordings | `data/ankiweb-vocab/audio/` |
| parsed — structured cards | `data/*/cards.csv` |
| enriched — translations | `data/translations.csv`, `data/omniglot-phrases/translations.csv` |
| enriched — TTS | `data/tts/*.mp3`, `data/tts_audio.csv` |
| enriched — images | `images/` |
| flashcards | `output/` |

### Problems with the current structure

**1. `review/` conflates parsed and fix layers.**
The `review/*.csv` files contain both the auto-exported card data *and* the human corrections
(`sinhala_fix`, `english_fix`, `status=skip`). This means:
- Re-running export cannot cleanly overwrite them (so `prepare_review.py` never overwrites
  existing rows — a workaround, not a solution).
- You cannot tell what came from the source vs. what a human changed without reading diffs.
- Fixes are per-card edits rather than reusable rules.

**2. No structured fix/blacklist mechanism.**
Bug 5 (wrong recording for *navattanna*) is fixed by hand-editing `audio_file` in a CSV.
Bugs 1 & 2 (wrong translations) were fixed by hand-editing `data/translations.csv`.
Neither is captured as a reusable rule — if you re-run the pipeline from scratch, the
fixes are gone.

**3. Raw data is scattered.**
`anki/`, `data/omniglot-phrases/audio/`, `data/ankiweb-vocab/audio/`,
and `data/Sinhala Basic Dialogs Cornell/` (unused Cornell recordings — no parsed
equivalent yet) all live in different places with no common `raw/` root.

**4. `data/` is a catch-all.**
It mixes raw audio, generated TTS, auto-exported cards, and translation join tables.
There is no structural signal for what is safe to delete vs. what is precious.

---

## Target structure

```
raw/
  anki/                             # .apkg files (current: anki/)
  audio/
    ankiweb-vocab/       # human vocab recordings
    omniglot-phrases/                 # phrase recordings
    Cornell/                        # Cornell dialogs (unused — future source)

parsed/
  <source>/
    cards.csv                       # id, sinhala, english, romanized, audio_file
    fixes.csv                       # blacklist (bad audio IDs) + search/replace rules

enriched/
  translations/
    <source>.csv                    # EN→DE per source
  tts/
    audio/                          # generated mp3s
    registry.csv                    # (id, lang) → filename join table
  images/
    <english_key>.png

output/
  <Deck Name>.txt
  <Deck Name> Media/
```

The `fixes.csv` per source replaces the inline fix columns in `review/`.
It could look like:

```csv
type,key,value,replacement,note
blacklist_audio,rec1590496296.mp3,,,wrong word read by speaker
replace_sinhala,vocab_abc123,old_value,correct_value,typo
replace_english,vocab_def456,to play,to hit,gloss too broad
```

Parse step reads `cards.csv` + `fixes.csv` and emits a clean enrichment-ready CSV,
with no human-edited columns mixed in.

---

## Open question — manual/AI cleaning steps

Some bugs cannot be fixed by a rule in `fixes.csv`:

- **Wrong source recording** (bug 5 — *navattanna*): the file exists and is referenced
  correctly, but the speaker read the wrong word. Detection requires listening; fix requires
  re-recording or TTS substitution.
- **Questionable translations** (bug 3 — *erzählen*, *kennen*): not outright wrong, but
  imprecise. Requires judgment about register and context.
- **Image ambiguity** (bug 4 — *tomorrow*): LLM picks a plausible but wrong emoji.
  Requires a review pass with eyes on the images.

These cases need a third artifact alongside `cards.csv` and `fixes.csv`: something like
a **cleaning prompt** — a documented, repeatable instruction (for a human or an LLM) that
describes what to look for and how to resolve it.  Questions still open:

- Where does this live? Per-source, or a shared `cleaning/` directory?
- What format? Free-text prompt, structured checklist, or a script that flags candidates
  for human review?
- How do accepted resolutions feed back into `fixes.csv` so they are not lost?

**Needs more thought before implementing.**

---

## Migration steps — DONE

All four layers are now in place:

1. ✓ Created `raw/`; moved `.apkg` and recordings there.
2. ✓ Renamed `review/*.csv` → `parsed/<source>/cards.csv`.
3. ✓ Extracted fix columns → `parsed/<source>/fixes.csv`.
4. ✓ Updated `prepare_review.py` to emit clean `cards.csv` + stub `fixes.csv`.
5. ✓ Moved translations, tts, images under `enriched/`.
6. ✓ Updated all script defaults and Makefile paths.
7. ✓ Deleted `data/master.csv` and `scripts/merge.py`.
