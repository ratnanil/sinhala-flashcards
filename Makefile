# Sinhala Flashcard Pipeline
#
# Pipeline stages:
#   A_raw/      immutable raw sources (.apkg, audio, html)
#   B_parsed/   curated cards + enhanced audio
#   C_enriched/ LLM-generated enrichments (translations, TTS, images, romanization)
#   D_output/   final Flashcard Deluxe decks
#
# Usage:
#   make parse               A → B: parse .apkg → B_parsed/<deck>/cards.csv
#   make enhance             A → B: enhance Sinhala audio quality
#   make enrich-romanize     B → C: generate romanization
#   make enrich-translate    B → C: EN→DE translations    (requires ollama)
#   make enrich-images       B → C: emoji images          (requires ollama)
#   make enrich-tts          B → C: German TTS audio      (requires internet)
#   make deck                C → D: build Flashcard Deluxe output files
#   make deploy              D → Dropbox
#
# All enrich-* and enhance accept DECK= to target a single source:
#   make enrich-translate DECK=ankiweb-vocab
#   make enrich-tts DECK=omniglot-phrases

PYTHON  := python3
SOURCES := $(patsubst A_raw/%/apkg/%.apkg, %, $(wildcard A_raw/*/apkg/*.apkg))
REMOTE  := Dropbox:Flashcards Deluxe

DECK ?=
_ALL_DECKS := $(patsubst B_parsed/%/cards.csv, %, $(wildcard B_parsed/*/cards.csv))
_DECKS     := $(if $(DECK), $(DECK), $(_ALL_DECKS))

.PHONY: all parse enhance enrich-romanize enrich-translate enrich-images enrich-tts deck deploy clean-generated help

all: deck

# ── A → B ──────────────────────────────────────────────────────────────────

# Parse .apkg sources → B_parsed/<deck>/cards.csv + audio/
# Reruns only when the .apkg or the script changes. Append-only.
parse: $(patsubst %, B_parsed/%/cards.csv, $(SOURCES))

B_parsed/%/cards.csv: A_raw/%/apkg/%.apkg scripts/ingest.py
	@echo "Ingesting $<..."
	$(PYTHON) scripts/ingest.py $< B_parsed/$* --audio-out A_raw/$*/audio

# Enhance raw Sinhala audio (highpass + afftdn noise reduction + loudnorm)
# Output: B_parsed/*/audio_enhanced/ — originals in A_raw/*/audio/ untouched
enhance:
	@for deck in $(_DECKS); do \
		[ -d A_raw/$$deck/audio ] || continue; \
		$(PYTHON) scripts/enhance_audio.py \
			--src A_raw/$$deck/audio \
			--dst B_parsed/$$deck/audio_enhanced; \
	done

# ── B → C ──────────────────────────────────────────────────────────────────

# Generate romanization for all cards
enrich-romanize:
	@for deck in $(_DECKS); do \
		$(PYTHON) scripts/generate_romanization.py --source B_parsed/$$deck/cards.csv; \
	done

# Generate EN→DE translations (requires ollama)
# Each deck keeps its own translations file — never bleed across decks
enrich-translate:
	@for deck in $(_DECKS); do \
		$(PYTHON) scripts/generate_translations.py --source B_parsed/$$deck/cards.csv; \
	done

# Generate emoji images keyed by card ID (requires ollama)
enrich-images:
	@for deck in $(_DECKS); do \
		$(PYTHON) scripts/generate_images.py --source B_parsed/$$deck/cards.csv; \
	done

# Generate German TTS audio for side 1 (requires internet)
enrich-tts:
	@for deck in $(_DECKS); do \
		$(PYTHON) scripts/generate_audio.py --engine edge-tts --voice de-DE-KatjaNeural \
			--text-column german --lang de \
			--source B_parsed/$$deck/cards.csv; \
	done

# ── C → D ──────────────────────────────────────────────────────────────────

DECK_DEPS := scripts/build_deck.py

D_output/Deutsch\ Sinhala.txt: B_parsed/ankiweb-vocab/cards.csv C_enriched/ankiweb-vocab/translations.csv $(DECK_DEPS)
	$(PYTHON) scripts/build_deck.py \
		--source B_parsed/ankiweb-vocab/cards.csv \
		--side1 german --side3 romanized \
		--out "D_output/Deutsch Sinhala.txt"

D_output/Omniglot\ Phrasen.txt: B_parsed/omniglot-phrases/cards.csv C_enriched/omniglot-phrases/translations.csv $(DECK_DEPS)
	$(PYTHON) scripts/build_deck.py \
		--source B_parsed/omniglot-phrases/cards.csv \
		--side1 german --side3 romanized \
		--out "D_output/Omniglot Phrasen.txt"

deck: D_output/Deutsch\ Sinhala.txt D_output/Omniglot\ Phrasen.txt

# ── Deploy ─────────────────────────────────────────────────────────────────

deploy:
	rclone copyto "D_output/Deutsch Sinhala.txt" "$(REMOTE)/Deutsch Sinhala.txt" --ignore-times --progress
	rclone sync "D_output/Deutsch Sinhala Media/" "$(REMOTE)/Deutsch Sinhala Media/" --progress
	rclone copyto "D_output/Omniglot Phrasen.txt" "$(REMOTE)/Omniglot Phrasen.txt" --ignore-times --progress
	rclone sync "D_output/Omniglot Phrasen Media/" "$(REMOTE)/Omniglot Phrasen Media/" --progress

# ── Utilities ──────────────────────────────────────────────────────────────

# Remove only generated output — never parsed cards or raw sources
clean-generated:
	rm -rf D_output/
	@echo "Removed D_output/. Parsed cards and raw sources untouched."

help:
	@echo "Pipeline:"
	@echo "  A -> B:  parse               parse .apkg -> B_parsed/<deck>/cards.csv"
	@echo "           enhance             enhance Sinhala audio quality"
	@echo "  B -> C:  enrich-romanize     generate romanization"
	@echo "           enrich-translate    EN->DE translations  (requires ollama)"
	@echo "           enrich-images       emoji images        (requires ollama)"
	@echo "           enrich-tts          German TTS audio    (requires internet)"
	@echo "  C -> D:  deck                build Flashcard Deluxe output files"
	@echo "           deploy              upload to Dropbox"
	@echo ""
	@echo "Options:"
	@echo "  DECK=<name>  limit enrich-* and enhance to one deck"
	@echo "               e.g. make enrich-translate DECK=ankiweb-vocab"
