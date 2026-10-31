# Red Teaming AI Systems — A Practitioner's Course Handbook

A practitioner's handbook for assessing the security of large language models, autonomous agents, retrieval pipelines and the infrastructure that runs them.

**Edition 1.1 · 2026 · AI Security Curriculum**

The handbook is an eleven-module red team curriculum with two foundation primers. Every module and foundation primer is written on two levels: a plain-language short version, then a technical deep dive with architecture, attack surface, evidence, detection and controls.

> **Authorised testing only.** All techniques and payloads are intended for systems you own or have explicit written permission to test. See the ethics and authorisation chapter before running anything.

## Contents

**Part 0 — How the machine works**

- How AI Reads: Tokens and Transformers
- How Neural Networks Learn

**Part I — Foundations**

1. Introduction to Red Teaming AI Systems
2. Reconnaissance for AI Targets

**Part II — Attacking the application layer**

3. Attacking AI Agents
4. Attacking Multi-Agent Systems and A2A Protocols
5. Exploiting RAG Pipelines
6. Attacking Embeddings
7. Attacking Model Context Protocol and Tool Surfaces

**Part III — Infrastructure, supply chain and strategy**

8. Supply Chain Attacks on AI/ML Systems
9. AI Infrastructure and Deployment Exploits
10. Threat Modelling for AI-Enabled Targets
11. Assembling the Pieces (capstone)

Plus front matter on authorisation, ethics and safety, and appendices with lab build instructions, tooling, framework mappings, a telemetry schema, glossary and references. Reporting templates are in the capstone module.

## Repository layout

```
.
├── Red_Teaming_AI_Systems_Handbook.md    # Markdown edition (root)
├── Red_Teaming_AI_Systems_Handbook.pdf   # PDF edition (root)
├── Red_Teaming_AI_Systems_Handbook_figures/
│   └── figure-*.svg                      # Figures referenced by the Markdown
├── Makefile                              # build / check / audit / clean targets
├── requirements.txt                      # Pinned Python build dependencies
├── requirements-dev.txt                  # Pinned audit/test tooling
├── SECURITY.md                           # How to report build-pipeline issues
├── tests/                                # Unit tests for both build scripts
├── .github/workflows/ci.yml              # CI: audit, validate, build, freshness
└── book/
    ├── src/                              # HTML source fragments, one per chapter
    │   └── tracks/                       # Per-module plain-language/deep-dive panels
    ├── build.py                          # HTML → PDF build (WeasyPrint)
    ├── make_markdown.py                  # HTML → Markdown + figure extraction
    ├── style.css                         # Print and screen styles
    └── book.html                         # Generated combined HTML
```

## Reading

- **PDF:** open `Red_Teaming_AI_Systems_Handbook.pdf`.
- **Markdown:** open `Red_Teaming_AI_Systems_Handbook.md` from this folder so the relative figure paths in `Red_Teaming_AI_Systems_Handbook_figures/` resolve.

## Building

The source of truth is `book/src/`. `build.py` concatenates the HTML fragments in filename order, injects the plain-language and deep-dive panels from `book/src/tracks/`, generates the table of contents and renders the PDF. `make_markdown.py` then converts the generated `book.html` into the Markdown edition and extracts the SVG figures.

Requirements:

- Python 3.10+
- [WeasyPrint](https://weasyprint.org/) (PDF rendering)
- `beautifulsoup4` and `markdownify` (Markdown conversion)

Install the pinned Python dependencies:

```bash
python3 -m pip install -r requirements.txt
```

The versions in `requirements.txt` are pinned deliberately. Keep them current:
WeasyPrint releases before 70.0 have published SSRF and RCE advisories, and
markdownify releases before 0.14.1 have a memory-exhaustion advisory.

Build both editions from the repository root:

```bash
make build
```

Or run the scripts directly:

```bash
cd book
python3 build.py
python3 make_markdown.py
```

A full build writes:

- `book/book.html`
- `Red_Teaming_AI_Systems_Handbook.pdf`
- `Red_Teaming_AI_Systems_Handbook.md`
- `Red_Teaming_AI_Systems_Handbook_figures/*.svg`

WeasyPrint also needs the usual native libraries (Pango and related packages);
see the WeasyPrint installation guide for your platform if the PDF step fails.
If those libraries are unavailable, rebuild the HTML and Markdown editions only:

```bash
make html
# equivalent to: cd book && python3 build.py --html-only && python3 make_markdown.py
```

### Validation, tests and dependency audit

`build.py` validates the sources before writing anything: duplicate ids, broken
internal links, missing TOC markers, malformed figures and missing track
markers are reported together. `make check` runs that validation in strict mode
(warnings fail the build) and then runs the unit tests:

```bash
make check
```

Audit the pinned build and development dependencies with `pip-audit`:

```bash
python3 -m pip install -r requirements-dev.txt
make audit
# or: python3 -m pip_audit -r requirements.txt -r requirements-dev.txt
```

`build.py --check` and `make_markdown.py --check` perform validation without
writing files. CI runs the same checks on every push and pull request, audits
the dependencies, builds both editions and verifies that the committed
generated files are current.

## Contributing

Edit the fragments in `book/src/` (and `book/src/tracks/` for the per-module track panels), then run `make check` and `make build`. Do not edit the generated `book/book.html`, PDF, Markdown or figures directly — they are overwritten on the next build.

For vulnerabilities in the build pipeline, see [SECURITY.md](SECURITY.md).

## Licence

No licence file is currently included in this repository. Contact the maintainer before redistributing or reusing the material.
