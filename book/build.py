#!/usr/bin/env python3
"""Build the Red Teaming AI Systems handbook PDF.

Concatenates the HTML fragments in src/ in filename order, auto-generates the
table of contents from h1/h2 ids, and renders with WeasyPrint.
"""
import html
import re
import sys
from pathlib import Path

from weasyprint import HTML

ROOT = Path(__file__).parent
SRC = ROOT / "src"
TRACKS = SRC / "tracks"
OUT = ROOT.parent / "Red_Teaming_AI_Systems_Handbook.pdf"

fragments = sorted(SRC.glob("*.html"))
if not fragments:
    sys.exit("no source fragments found")

parts = []
entries = []  # (level, id, text, fragment name)

PART_OF = {
    "00": "Front matter",
    "00b": "Part 0 — How the machine works",
    "00c": "Part 0 — How the machine works",
    "01": "Part I — Foundations",
    "03": "Part II — Attacking the application layer",
    "08": "Part III — Infrastructure, supply chain and strategy",
    "12": "Appendices",
}


def inject_tracks(text: str, fname: str) -> str:
    """Insert the plain-language brief and the deep-dive panel for a module.

    Each module has an optional src/tracks/NN.html file split into two halves by
    the marker <!--DEEP-->. The first half is placed immediately after the
    learning objectives (so every reader meets the accessible explanation
    first); the second half is placed just before the lab section.
    """
    key = fname.split("_", 1)[0]
    track = TRACKS / f"{key}.html"
    if not track.exists():
        return text
    raw = track.read_text(encoding="utf-8")
    if "<!--DEEP-->" not in raw:
        return text
    brief, deep = raw.split("<!--DEEP-->", 1)
    brief = brief.replace("<!--BRIEF-->", "").strip()
    deep = deep.strip()

    text, n = re.subn(
        r'(<div class="objectives">.*?</ul>\s*</div>)',
        lambda m: m.group(1) + "\n\n" + brief,
        text,
        count=1,
        flags=re.S,
    )
    if n == 0:
        print(f"warning: no objectives block in {fname}; brief not inserted")

    anchor = re.search(r'<h2 id="m\d+-lab"', text)
    if anchor is None:
        anchor = re.search(r'<h2 id="m\d+-takeaways"', text)
    if anchor:
        text = text[: anchor.start()] + deep + "\n\n  " + text[anchor.start():]
    else:
        print(f"warning: no insertion anchor in {fname}; deep panel not inserted")
    return text


for f in fragments:
    text = f.read_text(encoding="utf-8")
    text = inject_tracks(text, f.name)
    for m in re.finditer(r'<h([12])\b([^>]*)>(.*?)</h\1>', text, re.S):
        level = int(m.group(1))
        attrs = m.group(2)
        idm = re.search(r'id="([^"]+)"', attrs)
        if not idm:
            continue
        raw = re.sub(r"<[^>]+>", " ", m.group(3).replace("<br>", " ").replace("<br/>", " ").replace("<br />", " "))
        title = html.unescape(re.sub(r"\s+", " ", raw)).strip()
        override = re.search(r'data-toc="([^"]+)"', attrs)
        if override:
            title = override.group(1)
        entries.append((level, idm.group(1), title, f.name))
    parts.append(f'<!-- ===== {f.name} ===== -->\n{text}')

toc_rows = []
last_part = None
for level, id_, title, fname in entries:
    if title.lower().startswith(("contents", "how to use")):
        continue
    stem = fname.rsplit(".", 1)[0].split("_", 1)[0]
    part = PART_OF.get(stem)
    if part and part != last_part:
        toc_rows.append(f'<div class="part">{part}</div>')
        last_part = part
    cls = "lvl1" if level == 1 else "lvl2"
    toc_rows.append(f'<a class="{cls}" href="#{id_}">{html.escape(title)}</a>')

toc_html = '<nav class="toc">\n' + "\n".join(toc_rows) + "\n</nav>"

body = "\n".join(parts).replace("<!--TOC-->", toc_html)

doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Red Teaming AI Systems — A Practitioner's Course Handbook</title>
<meta name="author" content="AI Security Curriculum">
<meta name="description" content="Course handbook for an eleven-module red team curriculum on attacking and defending AI systems, with two foundation primers on tokens, transformers and neural networks and a plain-language track in every chapter.">
<meta name="keywords" content="AI red teaming, LLM security, prompt injection, RAG, MCP, A2A, adversarial ML, tokenization, transformers, neural networks">
<link rel="stylesheet" href="style.css">
</head>
<body>
{body}
</body>
</html>
"""

(ROOT / "book.html").write_text(doc, encoding="utf-8")
HTML(string=doc, base_url=str(ROOT)).write_pdf(str(OUT))
print(f"wrote {OUT}")
