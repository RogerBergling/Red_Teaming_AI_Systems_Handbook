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

Install the Python dependencies:

```bash
python3 -m pip install weasyprint beautifulsoup4 markdownify
```

Build both editions from the repository root:

```bash
cd book
python3 build.py
python3 make_markdown.py
```

This writes:

- `book/book.html`
- `Red_Teaming_AI_Systems_Handbook.pdf`
- `Red_Teaming_AI_Systems_Handbook.md`
- `Red_Teaming_AI_Systems_Handbook_figures/*.svg`

WeasyPrint also needs the usual native libraries (Pango, cairo and related packages); see the WeasyPrint installation guide for your platform if the PDF step fails.

## Contributing

Edit the fragments in `book/src/` (and `book/src/tracks/` for the per-module track panels), then rebuild. Do not edit the generated `book/book.html`, PDF, Markdown or figures directly — they are overwritten on the next build.

## Licence

No licence file is currently included in this repository. Contact the maintainer before redistributing or reusing the material.
