# Sinhala Flashcard Pipeline
#
# Each deck is independent — review/<deck>.csv is the canonical curated source.
# Hand-curate by editing review/<deck>.csv directly (set status=skip, fix fields).
#
# Per-deck workflow:
#   vocab:   export → review → approve → translate → audio → deck
#   phrases: (cards.csv already generated) → review → approve → translate-phrases → audio-phrases → deck
#
# Usage:
#   make export                   run after adding a new .apkg
#   make review                   populate/update review/ CSVs
#   make approve DECK=<name>      bulk-approve a deck
#   make translate                EN→DE for vocab deck (requires ollama)
#   make translate-phrases        EN→DE for phrases deck (requires ollama)
#   make audio                    German TTS for vocab deck (requires internet)
#   make audio-phrases            German TTS for phrases deck (requires internet)
#   make deck                     build all output files
#   make master                   optional: merge all decks into data/master.csv

PYTHON      := python3
APKG_FILES   := $(wildcard raw/anki/*.apkg)
DATA_CSVS    := $(patsubst raw/anki/%.apkg, data/%/cards.csv, $(APKG_FILES))
# Manually maintained card CSVs (not generated from .apkg)
MANUAL_CSVS  := data/omniglot-phrases/cards.csv
REVIEW_CSVS  := $(wildcard review/*.csv)

REMOTE := Dropbox:Flashcards Deluxe

.PHONY: all export review approve approve-all master audio deck deploy clean-generated romanize help

all: deck

# 1. Export .apkg → data/<deck>/cards.csv + audio/
#    Reruns only when the .apkg or the script changes.
export: $(DATA_CSVS)

data/%/cards.csv: raw/anki/%.apkg scripts/export_apkg.py
	@echo "Exporting $<..."
	$(PYTHON) scripts/export_apkg.py --audio-out raw/audio/$* $< data/$*

# 2. Populate review/ CSVs (safe to rerun — never overwrites existing rows)
review: $(DATA_CSVS) $(MANUAL_CSVS) scripts/prepare_review.py
	@echo "Preparing review files..."
	$(PYTHON) scripts/prepare_review.py

# 2b. Bulk-approve a deck after reviewing it:
#     make approve DECK=everflip-sinhala-colors
#     make approve-all
approve:
	$(PYTHON) scripts/approve_deck.py $(DECK)

approve-all:
	$(PYTHON) scripts/approve_deck.py --all

# 3. Merge approved rows → data/master.csv
#    Reruns whenever any review file changes.
data/master.csv: scripts/merge.py $(REVIEW_CSVS)
	@echo "Merging..."
	$(PYTHON) scripts/merge.py

master: data/master.csv

# Preprocessing: generate emoji images for vocabulary words (outside main pipeline)
# Only fetches images that don't exist yet — safe to rerun.
# Requires: ollama serve running
images: scripts/generate_images.py
	$(PYTHON) scripts/generate_images.py --source review/ankiweb-vocab.csv
	$(PYTHON) scripts/generate_images.py --source review/omniglot-phrases.csv

# Preprocessing: generate EN→DE translations (outside main pipeline)
# Only translates missing words — safe to rerun.
# Requires: ollama serve running
#
# Each deck has its own translations file — translations never bleed across decks.
#   data/translations.csv                    ← vocab + everflip (simple words)
#   data/omniglot-phrases/translations.csv   ← omniglot phrases
# Enhance Sinhala recording quality (highpass + afftdn noise reduction + loudnorm)
# Output goes to data/ankiweb-vocab/audio_enhanced/ — originals in raw/audio/ untouched.
# Safe to rerun; already-enhanced files are skipped unless --force is passed.
enhance: scripts/enhance_audio.py
	$(PYTHON) scripts/enhance_audio.py
	$(PYTHON) scripts/enhance_audio.py \
		--src raw/audio/omniglot-phrases \
		--dst data/omniglot-phrases/audio_enhanced

romanize: review/ankiweb-vocab.csv review/omniglot-phrases.csv scripts/generate_romanization.py
	$(PYTHON) scripts/generate_romanization.py --source review/ankiweb-vocab.csv
	$(PYTHON) scripts/generate_romanization.py --source review/omniglot-phrases.csv

translate: review/ankiweb-vocab.csv scripts/generate_translations.py
	$(PYTHON) scripts/generate_translations.py --source review/ankiweb-vocab.csv

translate-phrases: review/omniglot-phrases.csv scripts/generate_translations.py
	$(PYTHON) scripts/generate_translations.py \
		--source review/omniglot-phrases.csv \
		--output data/omniglot-phrases/translations.csv

# 4. Generate TTS audio for cards without recordings
#    German (side 1): per deck, each using its own translations file
#    Sinhala (side 2): deferred — vocab has human recordings, everflip not yet in build
audio: review/ankiweb-vocab.csv scripts/generate_audio.py
#	$(PYTHON) scripts/generate_audio.py --engine edge-tts --voice si-LK-SameeraNeural
	$(PYTHON) scripts/generate_audio.py --engine edge-tts --voice de-DE-KatjaNeural \
		--text-column german --lang de \
		--source review/ankiweb-vocab.csv

audio-phrases: review/omniglot-phrases.csv data/omniglot-phrases/translations.csv scripts/generate_audio.py
	$(PYTHON) scripts/generate_audio.py --engine edge-tts --voice de-DE-KatjaNeural \
		--text-column german --lang de \
		--source review/omniglot-phrases.csv \
		--translations data/omniglot-phrases/translations.csv

# 5. Build final deck files
DECK_DEPS := scripts/build_deck.py

output/Deutsch\ Sinhala.txt: review/ankiweb-vocab.csv data/translations.csv $(DECK_DEPS)
	$(PYTHON) scripts/build_deck.py \
		--source review/ankiweb-vocab.csv \
		--side1 german --side3 romanized --image-key english \
		--out "output/Deutsch Sinhala.txt"

output/Omniglot\ Phrasen.txt: review/omniglot-phrases.csv data/omniglot-phrases/translations.csv $(DECK_DEPS)
	$(PYTHON) scripts/build_deck.py \
		--source review/omniglot-phrases.csv \
		--side1 german --side3 romanized --image-key english \
		--translations data/omniglot-phrases/translations.csv \
		--out "output/Omniglot Phrasen.txt"

deck: output/Deutsch\ Sinhala.txt output/Omniglot\ Phrasen.txt

# 6. Upload output/ to Google Drive → Flashcard Deluxe can sync from there
#    Requires: rclone configured with a remote named "gdrive"
#    Run once to configure: rclone config
#    Each deck produces:
#      "Flashcards Deluxe/<Deck Name>.txt"
#      "Flashcards Deluxe/<Deck Name> Media/" (audio + images)
DECK_NAME := Deutsch Sinhala

deploy:
	rclone copyto "output/Deutsch Sinhala.txt" "$(REMOTE)/Deutsch Sinhala.txt" --ignore-times --progress
	rclone sync "output/Deutsch Sinhala Media/" "$(REMOTE)/Deutsch Sinhala Media/" --progress
	rclone copyto "output/Omniglot Phrasen.txt" "$(REMOTE)/Omniglot Phrasen.txt" --ignore-times --progress
	rclone sync "output/Omniglot Phrasen Media/" "$(REMOTE)/Omniglot Phrasen Media/" --progress

# Remove only generated files — never review files or source .apkg
clean-generated:
	rm -rf data/*/cards.csv data/*/audio data/master.csv output/
	@echo "Removed generated files. Review files and .apkg sources untouched."

help:
	@echo "Targets: export  review  approve  approve-all  master  images  romanize  translate  audio  deck  all  deploy  clean-generated"
	@echo ""
	@echo "Normal workflow:"
	@echo "  1. make export                          (after adding a new .apkg)"
	@echo "  2. make review                          (generates review/ CSVs)"
	@echo "  3. open review/<deck>.csv, check cards"
	@echo "     make approve DECK=<name>             (approve all pending in one deck)"
	@echo "     make approve-all                     (approve all pending in all decks)"
	@echo "     manually set status=skip for bad cards in the spreadsheet"
	@echo "  4. make master                          (merges approved cards)"
	@echo "  5. make images                          (generates missing emoji PNGs — requires ollama)"
	@echo "     make translate                       (generates missing EN→DE translations — requires ollama)"
	@echo "  6. make audio                           (generates missing TTS audio)"
	@echo "  7. make deck                            (builds output/master_en.txt + output/master_de.txt)"
