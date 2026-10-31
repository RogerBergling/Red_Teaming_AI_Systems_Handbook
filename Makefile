PYTHON ?= python3

.PHONY: all build html check test audit clean

all: build

build:
	cd book && $(PYTHON) build.py
	cd book && $(PYTHON) make_markdown.py

html:
	cd book && $(PYTHON) build.py --html-only
	cd book && $(PYTHON) make_markdown.py

check:
	$(PYTHON) book/build.py --check --strict
	$(PYTHON) -m unittest discover -s tests -v

test:
	$(PYTHON) -m unittest discover -s tests -v

audit:
	$(PYTHON) -m pip_audit -r requirements.txt -r requirements-dev.txt

clean:
	rm -f book/book.html
	rm -f Red_Teaming_AI_Systems_Handbook.pdf
	rm -f Red_Teaming_AI_Systems_Handbook.md
	rm -f Red_Teaming_AI_Systems_Handbook_figures/figure-*.svg
