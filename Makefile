# Sinhala Flashcard Pipeline
#
# Pipeline stages:
#   A_raw/      immutable raw sources (.apkg, audio, html)
#   B_parsed/   curated cards + enhanced audio
#   C_enriched/ LLM-generated enrichments (translations, TTS, images, romanization)
#   D_output/   final Flashcard Deluxe decks
#
# Per-deck targets:
#   make parse-<deck>             A → B: parse source into B_parsed/<deck>/cards.csv
#   make enrich-enhance-<deck>    B → C: enhance Sinhala audio quality
#   make enrich-romanize-<deck>   B → C: generate romanization
#   make enrich-translate-<deck>  B → C: EN→DE translations    (requires DEEPL_API_KEY)
#   make enrich-images-<deck>     B → C: emoji images          (requires ollama)
#   make enrich-tts-<deck>        B → C: German TTS audio      (requires internet)
#   make deck-<deck>              C → D: build Flashcard Deluxe output file
#   make deploy-<deck>            D → Dropbox
#
# Aggregate targets run all decks:
#   make parse / enrich-enhance / enrich-romanize / enrich-translate / enrich-images / enrich-tts / deck / deploy

PYTHON     := python3
# Decks where the apkg filename matches the deck folder name (handled by pattern rule parse-%)
APKG_DECKS := $(foreach f,$(wildcard A_raw/*/apkg/*.apkg),\
    $(if $(filter $(notdir $(patsubst %/apkg/,%,$(dir $f))),$(basename $(notdir $f))),\
    $(notdir $(patsubst %/apkg/,%,$(dir $f)))))
ALL_DECKS  := $(patsubst B_parsed/%/cards.csv, %, $(wildcard B_parsed/*/cards.csv))
DECK_DEPS  := scripts/build_deck.py
REMOTE     := Dropbox:Flashcards Deluxe

.PHONY: all parse enrich-enhance enrich-romanize enrich-translate enrich-images enrich-tts \
        deck deploy clean-generated help \
        deck-ankiweb-vocab deck-omniglot-phrases \
        deploy-ankiweb-vocab deploy-omniglot-phrases \
        parse-everflip-sinhala parse-omniglot-phrases parse-ilovelanguages

all: deck

# ── A → B ──────────────────────────────────────────────────────────────────

parse: $(patsubst %, parse-%, $(APKG_DECKS)) parse-everflip-sinhala parse-omniglot-phrases parse-ilovelanguages

# Multi-apkg sources — explicit rules
parse-everflip-sinhala:
	@for apkg in A_raw/everflip-sinhala/apkg/*.apkg; do \
		cat=$$(basename $$apkg .apkg | sed 's/everflip-sinhala-//'); \
		$(PYTHON) scripts/ingest.py $$apkg B_parsed/everflip-sinhala --category $$cat; \
	done

# HTML-sourced decks — explicit rules
parse-omniglot-phrases:
	$(PYTHON) scripts/parse_omniglot.py

parse-ilovelanguages:
	$(PYTHON) scripts/parse_ilovelanguages.py

# .apkg-sourced decks (one apkg per folder, folder name matches apkg name)
parse-%:
	@echo "Parsing $*..."
	$(PYTHON) scripts/ingest.py A_raw/$*/apkg/$*.apkg B_parsed/$* --audio-out A_raw/$*/audio

# ── B → C ──────────────────────────────────────────────────────────────────

enrich-enhance: $(patsubst %, enrich-enhance-%, $(ALL_DECKS))

enrich-enhance-%:
	@if [ -d A_raw/$*/audio ]; then \
		$(PYTHON) scripts/enhance_audio.py \
			--src A_raw/$*/audio \
			--dst B_parsed/$*/audio_enhanced; \
	else \
		echo "enrich-enhance-$*: no audio dir, skipping."; \
	fi

enrich-romanize: $(patsubst %, enrich-romanize-%, $(ALL_DECKS))

enrich-romanize-%:
	$(PYTHON) scripts/generate_romanization.py --source B_parsed/$*/cards.csv

enrich-translate: $(patsubst %, enrich-translate-%, $(ALL_DECKS))

enrich-translate-%:
	$(PYTHON) scripts/generate_translations.py --source B_parsed/$*/cards.csv

enrich-images: $(patsubst %, enrich-images-%, $(ALL_DECKS))

enrich-images-%:
	$(PYTHON) scripts/generate_images.py --source B_parsed/$*/cards.csv

enrich-tts: $(patsubst %, enrich-tts-%, $(ALL_DECKS))

enrich-tts-%:
	$(PYTHON) scripts/generate_audio.py --engine edge-tts --voice de-CH-LeniNeural \
		--text-column german --lang de \
		--source B_parsed/$*/cards.csv

# ── C → D ──────────────────────────────────────────────────────────────────

deck: deck-ankiweb-vocab deck-omniglot-phrases

deck-ankiweb-vocab: $(DECK_DEPS)
	$(PYTHON) scripts/build_deck.py \
		--source B_parsed/ankiweb-vocab/cards.csv \
		--side1 german --side3 romanized --side4 english --merge-variants \
		--out "D_output/Deutsch Sinhala.txt"

deck-omniglot-phrases: $(DECK_DEPS)
	$(PYTHON) scripts/build_deck.py \
		--source B_parsed/omniglot-phrases/cards.csv \
		--side1 german --side3 romanized --side4 english --merge-variants \
		--out "D_output/Omniglot Phrasen.txt"

# ── Deploy ─────────────────────────────────────────────────────────────────

deploy: deploy-ankiweb-vocab deploy-omniglot-phrases

deploy-ankiweb-vocab:
	rclone copyto "D_output/Deutsch Sinhala.txt" "$(REMOTE)/Deutsch Sinhala.txt" --ignore-times --progress
	rclone sync "D_output/Deutsch Sinhala Media/" "$(REMOTE)/Deutsch Sinhala Media/" --progress

deploy-omniglot-phrases:
	rclone copyto "D_output/Omniglot Phrasen.txt" "$(REMOTE)/Omniglot Phrasen.txt" --ignore-times --progress
	rclone sync "D_output/Omniglot Phrasen Media/" "$(REMOTE)/Omniglot Phrasen Media/" --progress

# ── Utilities ──────────────────────────────────────────────────────────────

clean-generated:
	rm -rf D_output/
	@echo "Removed D_output/. Parsed cards and raw sources untouched."

help:
	@echo "Per-deck:  make <step>-<deck>"
	@echo "  Steps:   parse  enhance  enrich-romanize  enrich-translate  enrich-images  enrich-tts  deck  deploy"
	@echo "  Decks:   $(ALL_DECKS)"
	@echo ""
	@echo "Aggregate: make parse / enrich-enhance / enrich-romanize / enrich-translate / enrich-images / enrich-tts / deck / deploy"
