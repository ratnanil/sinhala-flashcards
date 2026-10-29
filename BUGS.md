# Deutsch Sinhala — Known Bugs

Deck: `D_output/Deutsch Sinhala.txt`
Source: `B_parsed/ankiweb-vocab/cards.csv` + `C_enriched/ankiweb-vocab/translations/translations.csv`

---

## 1. Wrong German article — *der* Mango, *der* Ananas

| Card | Current | Correct |
|------|---------|---------|
| mango | `der Mango` | `die Mango` |
| pineapple | `der Ananas` | `die Ananas` |

**Root cause:** `C_enriched/ankiweb-vocab/translations/translations.csv` — stale entries from old LLM-based pipeline; will be correct after re-running `make enrich-translate-ankiweb-vocab`.

**Fix:**
1. Edit `C_enriched/ankiweb-vocab/translations/translations.csv`: correct the two entries.
2. Delete stale TTS files `C_enriched/ankiweb-vocab/audio/vocab_171ee3dd_de.mp3` and `C_enriched/ankiweb-vocab/audio/vocab_5d9d9c69_de.mp3`.
3. Run `make enrich-tts-ankiweb-vocab && make deck-ankiweb-vocab`.

---

## 2. Wrong German translation

| Card (English) | Sinhala | Current German | Correct German | Why wrong |
|----------------|---------|----------------|----------------|-----------|
| pomegranate | දෙලුම් | `die Granate` | `der Granatapfel` | *Granate* = grenade (weapon) |
| orange (color) | තැඹිලි | `die Orange` | `orange` | *die Orange* = the fruit; the color is the adjective *orange* (uninflected) |
| to play | ගහන්න | `spielen` | `schlagen` | *gahanna* = to hit/beat; *spielen* = to play games — wrong register |

**Root cause:** `C_enriched/ankiweb-vocab/translations/translations.csv` — stale entries from old LLM-based pipeline.

**Fix:**
1. Edit `C_enriched/ankiweb-vocab/translations/translations.csv`: correct `pomegranate`, `orange`, `to play`.
2. Delete stale TTS: `C_enriched/ankiweb-vocab/audio/vocab_1b5610e6_de.mp3`, `vocab_6dd39305_de.mp3`, `vocab_ca4596ea_de.mp3`.
3. Run `make enrich-tts-ankiweb-vocab && make deck-ankiweb-vocab`.

---

## 3. Questionable German translations

These are not outright wrong but are imprecise for what the Sinhala word actually covers.
Flagged for human review.

| Card (English) | Sinhala | Current German | Concern |
|----------------|---------|----------------|---------|
| to tell | කියන්න (kiyanna) | `erzählen` | *erzählen* = to narrate/tell a story; *kiyanna* = to say/tell broadly → `sagen` may be better |
| to know | දැන ගන්න (dæna ganna) | `kennen` | *kennen* = to know a person; *dæna ganna* = to get to know/learn → `wissen` or `erfahren` may be better |
| to read | කියවන්න (kiyavanna) | `lesen` | *lesen* is correct; *kiyavanna* also covers recitation — probably fine |
| to make | හදන්න (hadanna) | `machen` | *hadanna* = make/build/fix/prepare; *machen* is broad and acceptable but `herstellen` or `bauen` could be more precise |

**Fix:** Edit `C_enriched/ankiweb-vocab/translations/translations.csv`, delete corresponding TTS files from
`C_enriched/ankiweb-vocab/audio/`, then run `make enrich-tts-ankiweb-vocab && make deck-ankiweb-vocab`.

---

## 4. Wrong image for *morgen* (tomorrow)

**Symptom:** The card for `morgen` / හෙට shows a sunrise image.

**Root cause:** `C_enriched/ankiweb-vocab/images/vocab_544c5cbd.png` — the LLM picked a sunrise emoji
which evokes *der Morgen* (morning) rather than *morgen* (tomorrow).

**Fix:** Delete `C_enriched/ankiweb-vocab/images/vocab_544c5cbd.png` and either:
- (a) Regenerate: `make enrich-images-ankiweb-vocab` (Ollama may pick a different emoji; may need a few tries).
- (b) Manually replace with a more unambiguous image (e.g. a calendar page emoji).

Then run `make deck-ankiweb-vocab`.

---

## Summary — files to edit

| File | Issues |
|------|--------|
| `C_enriched/ankiweb-vocab/translations/translations.csv` | bugs 1, 2, 3 — stale; rerun `make enrich-translate-ankiweb-vocab` |
| `C_enriched/ankiweb-vocab/images/vocab_544c5cbd.png` | bug 4 — delete and regenerate or replace manually |

After all edits: `make enrich-tts-ankiweb-vocab && make deck-ankiweb-vocab && make deploy-ankiweb-vocab`

---

## Resolved

### ✓ Bug 5: German TTS pronounced with English accent

**Symptom:** `de-DE-KatjaNeural` mispronounced German-specific phonemes (ä, ö, ü, z as /ts/, etc.).
Known example: `erzählen` → *erselen*.

**Fix applied:** Switched voice to `de-CH-LeniNeural` in `make enrich-tts`. All stale TTS audio
deleted — will be regenerated on next pipeline run.

---

### ✓ Bug 6: Wrong Sinhala source recording for *stehen* / නවත්තන්න (vocab_09fa560a)

**Symptom:** The Sinhala audio for `stehen` / නවත්තන්න sounded wrong — speaker read the wrong word.

**Root cause:** Source recording `A_raw/ankiweb-vocab/audio/rec1590496296.mp3` is a bad take.
Pipeline correctly referenced it; the recording itself was wrong.

**Fix applied:** Blacklisted `vocab_09fa560a` in `A_raw/ankiweb-vocab/fixes.csv`.
Card is excluded from all decks until a correct recording is available.
