# Sinhala Flashcard Pipeline
#
# Each deck is independent — parsed/<deck>/cards.csv is the canonical source.
# Fix bad cards by editing parsed/<deck>/fixes.csv (blacklist/replace rules).
#
# Per-deck workflow:
#   vocab:   ingest → translate → audio → deck
#   phrases: (parsed/cards.csv already exists) → translate-phrases → audio-phrases → deck
#
# Usage:
#   make ingest                   run after adding a new .apkg → parsed/<deck>/cards.csv
#   make translate                EN→DE for vocab deck (requires ollama)
#   make translate-phrases        EN→DE for phrases deck (requires ollama)
#   make audio                    German TTS for vocab deck (requires internet)
#   make audio-phrases            German TTS for phrases deck (requires internet)
#   make deck                     build all output files

PYTHON      := python3
# Each source with an .apkg sits at raw/<source>/apkg/<source>.apkg
SOURCES      := $(patsubst raw/%/apkg/%.apkg, %, $(wildcard raw/*/apkg/*.apkg))
PARSED_CSVS  := $(wildcard parsed/*/cards.csv)

REMOTE := Dropbox:Flashcards Deluxe

.PHONY: all ingest audio deck deploy clean-generated romanize help

all: deck

# 1. Ingest .apkg → parsed/<deck>/cards.csv + audio/
#    Reruns only when the .apkg or the script changes.
#    Append-only: existing parsed cards are never overwritten.
ingest: $(patsubst %, parsed/%/cards.csv, $(SOURCES))

parsed/%/cards.csv: raw/%/apkg/%.apkg scripts/ingest.py
	@echo "Ingesting $<..."
	$(PYTHON) scripts/ingest.py $< parsed/$* --audio-out raw/$*/audio

# Preprocessing: generate emoji images for vocabulary words (outside main pipeline)
# Only fetches images that don't exist yet — safe to rerun.
# Requires: ollama serve running
images: scripts/generate_images.py
	$(PYTHON) scripts/generate_images.py --source parsed/ankiweb-vocab/cards.csv
	$(PYTHON) scripts/generate_images.py --source parsed/omniglot-phrases/cards.csv

# Preprocessing: generate EN→DE translations (outside main pipeline)
# Only translates missing words — safe to rerun.
# Requires: ollama serve running
#
# Each deck has its own translations file — translations never bleed across decks.
#   enriched/ankiweb-vocab/translations.csv
#   enriched/omniglot-phrases/translations.csv
# Enhance Sinhala recording quality (highpass + afftdn noise reduction + loudnorm)
# Output goes to parsed/*/audio_enhanced/ — originals in raw/*/audio/ untouched.
# Safe to rerun; already-enhanced files are skipped unless --force is passed.
enhance: scripts/enhance_audio.py
	$(PYTHON) scripts/enhance_audio.py
	$(PYTHON) scripts/enhance_audio.py \
		--src raw/omniglot-phrases/audio \
		--dst parsed/omniglot-phrases/audio_enhanced

romanize: parsed/ankiweb-vocab/cards.csv parsed/omniglot-phrases/cards.csv scripts/generate_romanization.py
	$(PYTHON) scripts/generate_romanization.py --source parsed/ankiweb-vocab/cards.csv
	$(PYTHON) scripts/generate_romanization.py --source parsed/omniglot-phrases/cards.csv

translate: parsed/ankiweb-vocab/cards.csv scripts/generate_translations.py
	$(PYTHON) scripts/generate_translations.py --source parsed/ankiweb-vocab/cards.csv

translate-phrases: parsed/omniglot-phrases/cards.csv scripts/generate_translations.py
	$(PYTHON) scripts/generate_translations.py \
		--source parsed/omniglot-phrases/cards.csv

# 4. Generate TTS audio for cards without recordings
#    German (side 1): per deck, each using its own translations file
#    Sinhala (side 2): deferred — vocab has human recordings, everflip not yet in build
audio: parsed/ankiweb-vocab/cards.csv scripts/generate_audio.py
#	$(PYTHON) scripts/generate_audio.py --engine edge-tts --voice si-LK-SameeraNeural
	$(PYTHON) scripts/generate_audio.py --engine edge-tts --voice de-DE-KatjaNeural \
		--text-column german --lang de \
		--source parsed/ankiweb-vocab/cards.csv

audio-phrases: parsed/omniglot-phrases/cards.csv enriched/omniglot-phrases/translations.csv scripts/generate_audio.py
	$(PYTHON) scripts/generate_audio.py --engine edge-tts --voice de-DE-KatjaNeural \
		--text-column german --lang de \
		--source parsed/omniglot-phrases/cards.csv

# 5. Build final deck files
DECK_DEPS := scripts/build_deck.py

output/Deutsch\ Sinhala.txt: parsed/ankiweb-vocab/cards.csv enriched/ankiweb-vocab/translations.csv $(DECK_DEPS)
	$(PYTHON) scripts/build_deck.py \
		--source parsed/ankiweb-vocab/cards.csv \
		--side1 german --side3 romanized --image-key english \
		--out "output/Deutsch Sinhala.txt"

output/Omniglot\ Phrasen.txt: parsed/omniglot-phrases/cards.csv enriched/omniglot-phrases/translations.csv $(DECK_DEPS)
	$(PYTHON) scripts/build_deck.py \
		--source parsed/omniglot-phrases/cards.csv \
		--side1 german --side3 romanized --image-key english \
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

# Remove only generated output files — never parsed cards or raw sources
clean-generated:
	rm -rf output/
	@echo "Removed generated output. Parsed cards and raw sources untouched."

help:
	@echo "Targets: ingest  images  romanize  translate  audio  deck  all  deploy  clean-generated"
	@echo ""
	@echo "Normal workflow:"
	@echo "  1. make ingest                          (after adding a new .apkg → parsed/<deck>/cards.csv)"
	@echo "  2. edit parsed/<deck>/cards.csv by hand"
	@echo "     add blacklist/replace rules to parsed/<deck>/fixes.csv if needed"
	@echo "  3. make images                          (generates missing emoji PNGs — requires ollama)"
	@echo "     make translate                       (generates missing EN→DE translations — requires ollama)"
	@echo "  4. make audio                           (generates missing TTS audio)"
	@echo "  5. make deck                            (builds output/ decks)"
