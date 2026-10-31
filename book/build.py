#!/usr/bin/env python3
"""Build the Red Teaming AI Systems handbook.

Concatenates the HTML fragments in ``src/`` in filename order, injects the
plain-language and deep-dive track panels, generates the table of contents,
writes ``book.html`` and renders the PDF with WeasyPrint.

Examples::

    python3 build.py --check        # validate sources, write nothing
    python3 build.py --html-only    # rebuild book.html without rendering a PDF
    python3 build.py                # rebuild book.html and the PDF
"""

from __future__ import annotations

import argparse
import html
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
TRACKS = SRC / "tracks"
STYLESHEET = ROOT / "style.css"
DEFAULT_HTML_OUT = ROOT / "book.html"
DEFAULT_PDF_OUT = ROOT.parent / "Red_Teaming_AI_Systems_Handbook.pdf"

# Fixed date for reproducible PDF metadata. Update when a new edition is cut.
EDITION_DATE = "2026-10-29"

TRACKED_MODULES = {f"{number:02d}" for number in range(1, 12)}

PART_OF = {
    "00": "Front matter",
    "00b": "Part 0 — How the machine works",
    "00c": "Part 0 — How the machine works",
    "01": "Part I — Foundations",
    "02": "Part I — Foundations",
    "03": "Part II — Attacking the application layer",
    "04": "Part II — Attacking the application layer",
    "05": "Part II — Attacking the application layer",
    "06": "Part II — Attacking the application layer",
    "07": "Part II — Attacking the application layer",
    "08": "Part III — Infrastructure, supply chain and strategy",
    "09": "Part III — Infrastructure, supply chain and strategy",
    "10": "Part III — Infrastructure, supply chain and strategy",
    "11": "Part III — Infrastructure, supply chain and strategy",
    "12": "Appendices",
}


class BuildError(RuntimeError):
    """A fatal build/validation problem with a user-facing message."""


@dataclass
class Diagnostics:
    """Collect problems instead of stopping at the first one."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def report(self, stream: TextIO = sys.stderr) -> None:
        for message in self.warnings:
            print(f"warning: {message}", file=stream)
        for message in self.errors:
            print(f"error: {message}", file=stream)


@dataclass(frozen=True)
class Heading:
    """An h1/h2 that should appear in the table of contents."""

    level: int
    anchor: str
    title: str
    fragment: str


@dataclass
class Fragment:
    """One source fragment after track injection."""

    path: Path
    text: str
    soup: BeautifulSoup
    headings: list[Heading]


def inject_tracks(
    text: str,
    fname: str,
    track_text: str | None,
    diagnostics: Diagnostics,
    track_name: str | None = None,
) -> str:
    """Insert the plain-language brief and the deep-dive panel for a module.

    Each module has an optional ``src/tracks/NN.html`` file split into two
    halves by the ``<!--DEEP-->`` marker. The first half is placed immediately
    after the learning objectives (so every reader meets the accessible
    explanation first); the second half is placed just before the lab section.
    """
    if track_text is None:
        return text

    label = track_name or f"{fname.split('_', 1)[0]}.html"
    if "<!--DEEP-->" not in track_text:
        diagnostics.warn(f"{label}: missing <!--DEEP--> marker; track panel not injected")
        return text
    if "<!--BRIEF-->" not in track_text:
        diagnostics.warn(f"{label}: missing <!--BRIEF--> marker")

    brief, deep = track_text.split("<!--DEEP-->", 1)
    brief = brief.replace("<!--BRIEF-->", "").strip()
    deep = deep.strip()
    if not brief:
        diagnostics.warn(f"{label}: brief panel is empty")
    if not deep:
        diagnostics.warn(f"{label}: deep-dive panel is empty")

    text, matches = re.subn(
        r'(<div class="objectives">.*?</ul>\s*</div>)',
        lambda match: match.group(1) + "\n\n" + brief,
        text,
        count=1,
        flags=re.S,
    )
    if matches == 0:
        diagnostics.warn(f"{fname}: no learning-objectives block; brief not inserted")

    anchor = re.search(r'<h2 id="m\d+-lab"', text)
    if anchor is None:
        anchor = re.search(r'<h2 id="m\d+-takeaways"', text)
    if anchor:
        text = text[: anchor.start()] + deep + "\n\n  " + text[anchor.start():]
    else:
        diagnostics.warn(f"{fname}: no lab or takeaways heading; deep panel not inserted")
    return text


def collect_headings(soup: BeautifulSoup, fname: str) -> list[Heading]:
    """Return h1/h2 headings that carry an id, in document order."""
    headings: list[Heading] = []
    for heading in soup.find_all(["h1", "h2"]):
        anchor = heading.get("id")
        if not anchor:
            continue
        override = heading.get("data-toc")
        title = override if isinstance(override, str) and override else heading.get_text(" ", strip=True)
        title = re.sub(r"\s+", " ", title).strip()
        headings.append(Heading(int(heading.name[1]), str(anchor), title, fname))
    return headings


def load_fragments(diagnostics: Diagnostics) -> list[Fragment]:
    """Read every source fragment and inject its optional track panel."""
    paths = sorted(SRC.glob("*.html"))
    if not paths:
        raise BuildError(f"no source fragments found in {SRC}")

    fragments: list[Fragment] = []
    for path in paths:
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise BuildError(f"cannot read {path}: {exc}") from exc
        if not raw.strip():
            diagnostics.error(f"{path.name}: source fragment is empty")

        stem = path.name.split("_", 1)[0]
        track = TRACKS / f"{stem}.html"
        track_text = None
        if track.exists():
            try:
                track_text = track.read_text(encoding="utf-8")
            except OSError as exc:
                raise BuildError(f"cannot read {track}: {exc}") from exc
        elif stem in TRACKED_MODULES:
            diagnostics.warn(f"{path.name}: no matching track file {track.name}")
        if track_text:
            if 'class="plainbrief"' not in track_text:
                diagnostics.warn(f"{track.name}: no div.plainbrief panel")
            if 'class="deepdive"' not in track_text:
                diagnostics.warn(f"{track.name}: no div.deepdive panel")

        text = inject_tracks(raw, path.name, track_text, diagnostics, track.name)
        soup = BeautifulSoup(text, "html.parser")
        fragments.append(Fragment(path, text, soup, collect_headings(soup, path.name)))
    return fragments


def validate_fragments(fragments: list[Fragment], diagnostics: Diagnostics) -> None:
    """Check structure that the TOC, Markdown converter and PDF rely on."""
    if not STYLESHEET.is_file():
        diagnostics.error(f"stylesheet not found: {STYLESHEET}")
    else:
        stylesheet = STYLESHEET.read_text(encoding="utf-8")
        if re.search(r"url\(\s*[\"']?https?://", stylesheet, re.I) or re.search(
            r"@import\s+[\"']?https?://", stylesheet, re.I
        ):
            diagnostics.warn(f"{STYLESHEET.name}: references a remote resource")

    toc_markers = sum(fragment.text.count("<!--TOC-->") for fragment in fragments)
    if toc_markers != 1:
        diagnostics.error(
            f"expected exactly one <!--TOC--> marker, found {toc_markers}"
        )

    ids: dict[str, str] = {}
    for fragment in fragments:
        for tag in fragment.soup.find_all(id=True):
            value = str(tag["id"])
            first = ids.get(value)
            if first is not None:
                diagnostics.error(
                    f"{fragment.path.name}: duplicate id '{value}' (already used in {first})"
                )
            else:
                ids[value] = fragment.path.name

        for heading in fragment.soup.find_all(["h1", "h2"]):
            if heading.get("id"):
                continue
            if heading.find_parent("section", class_="cover") is not None:
                continue
            location = f"{fragment.path.name}:{heading.sourceline}"
            diagnostics.warn(
                f"{location}: <{heading.name}> has no id and is omitted from the TOC"
            )

        for index, figure in enumerate(fragment.soup.find_all("figure"), start=1):
            location = f"{fragment.path.name}:{figure.sourceline}"
            if len(figure.find_all("svg")) != 1:
                diagnostics.error(
                    f"{location}: figure {index} must contain exactly one <svg>"
                )
            captions = figure.find_all("figcaption")
            if len(captions) != 1:
                diagnostics.error(
                    f"{location}: figure {index} must contain exactly one <figcaption>"
                )
            elif not captions[0].get_text(" ", strip=True):
                diagnostics.error(f"{location}: figure {index} has an empty caption")

        for tag in fragment.soup.find_all(
            ["img", "script", "link", "iframe", "object", "embed", "source", "video", "audio", "use", "image"]
        ):
            resource = tag.get("src") or tag.get("href") or tag.get("data")
            if isinstance(resource, str) and re.match(r"(?i)^https?://", resource):
                diagnostics.warn(
                    f"{fragment.path.name}: external resource referenced by "
                    f"<{tag.name}>: {resource}"
                )

        if re.search(r"url\(\s*[\"']?https?://", fragment.text, re.I):
            diagnostics.warn(
                f"{fragment.path.name}: inline style references a remote resource"
            )

    for fragment in fragments:
        for link in fragment.soup.find_all("a", href=True):
            target = str(link["href"])
            if target.startswith("#") and target[1:] not in ids:
                diagnostics.error(
                    f"{fragment.path.name}: link target '{target}' does not exist"
                )

    fragment_keys = {fragment.path.name.split("_", 1)[0] for fragment in fragments}
    for track in sorted(TRACKS.glob("*.html")):
        if track.stem not in fragment_keys:
            diagnostics.warn(f"{track.name}: no matching source fragment")

    for fragment in fragments:
        stem = fragment.path.name.split("_", 1)[0]
        if stem not in TRACKED_MODULES:
            continue
        number = int(stem)
        anchors = {heading.anchor for heading in fragment.headings}
        if fragment.soup.select_one("div.objectives") is None:
            diagnostics.warn(f"{fragment.path.name}: no div.objectives block")
        if fragment.soup.select_one("div.quiz") is None:
            diagnostics.warn(f"{fragment.path.name}: no div.quiz block")
        if f"m{number}-takeaways" not in anchors:
            diagnostics.warn(f"{fragment.path.name}: no m{number}-takeaways heading")
        if number <= 10 and f"m{number}-lab" not in anchors:
            diagnostics.warn(f"{fragment.path.name}: no m{number}-lab heading")


def build_toc(fragments: list[Fragment], diagnostics: Diagnostics) -> str:
    """Build the print TOC from h1/h2 headings."""
    entries = [heading for fragment in fragments for heading in fragment.headings]
    if not entries:
        diagnostics.error("no h1/h2 headings with ids found; the TOC would be empty")

    rows: list[str] = []
    last_part: str | None = None
    for heading in entries:
        if heading.title.lower().startswith(("contents", "how to use")):
            continue
        stem = heading.fragment.rsplit(".", 1)[0].split("_", 1)[0]
        part = PART_OF.get(stem)
        if part is None:
            diagnostics.warn(
                f"{heading.fragment}: no PART_OF entry for '{stem}'; "
                "the chapter will not appear under a part heading"
            )
        elif part != last_part:
            rows.append(f'<div class="part">{part}</div>')
            last_part = part
        css_class = "lvl1" if heading.level == 1 else "lvl2"
        rows.append(f'<a class="{css_class}" href="#{heading.anchor}">{html.escape(heading.title)}</a>')

    return '<nav class="toc">\n' + "\n".join(rows) + "\n</nav>"


def build_document(
    fragments: list[Fragment], toc_html: str, stylesheet_href: str = "style.css"
) -> str:
    """Combine fragments into the standalone HTML document."""
    parts = [
        f"<!-- ===== {fragment.path.name} ===== -->\n{fragment.text}"
        for fragment in fragments
    ]
    body = "\n".join(parts).replace("<!--TOC-->", toc_html)
    if "<!--TOC-->" in body:
        raise BuildError("TOC placeholder was not replaced")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Red Teaming AI Systems — A Practitioner's Course Handbook</title>
<meta name="author" content="AI Security Curriculum">
<meta name="description" content="Course handbook for an eleven-module red team curriculum on attacking and defending AI systems, with two foundation primers on tokens, transformers and neural networks and a plain-language track in every module and foundation primer.">
<meta name="keywords" content="AI red teaming, LLM security, prompt injection, RAG, MCP, A2A, adversarial ML, tokenization, transformers, neural networks">
<meta name="dcterms.created" content="{EDITION_DATE}">
<meta name="dcterms.modified" content="{EDITION_DATE}">
<link rel="stylesheet" href="{html.escape(stylesheet_href)}">
</head>
<body>
{body}
</body>
</html>
"""


def atomic_write(path: Path, data: str | bytes) -> None:
    """Write a file atomically, preserving its existing permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = data.encode("utf-8") if isinstance(data, str) else data
    mode = (path.stat().st_mode & 0o777) if path.exists() else 0o644
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def render_pdf(document_html: str, output: Path, base_url: Path) -> int:
    """Render the PDF and return its page count."""
    try:
        from weasyprint import HTML
    except Exception as exc:  # pragma: no cover - depends on host libraries
        raise BuildError(
            "WeasyPrint is not available. Install requirements.txt and the "
            "native Pango libraries, or use --html-only/--check. "
            f"Original error: {exc}"
        ) from exc

    document = HTML(string=document_html, base_url=str(base_url)).render()
    pdf = document.write_pdf()
    if not pdf:
        raise BuildError("WeasyPrint produced an empty PDF")
    atomic_write(output, pdf)
    return len(document.pages)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the handbook HTML/PDF.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate sources and exit without writing any files",
    )
    parser.add_argument(
        "--html-only",
        action="store_true",
        help="write book.html but do not render the PDF (no Pango needed)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat warnings as errors",
    )
    parser.add_argument(
        "--html-output",
        type=Path,
        default=DEFAULT_HTML_OUT,
        help=f"output HTML path (default: {DEFAULT_HTML_OUT})",
    )
    parser.add_argument(
        "--pdf-output",
        type=Path,
        default=DEFAULT_PDF_OUT,
        help=f"output PDF path (default: {DEFAULT_PDF_OUT})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    diagnostics = Diagnostics()

    try:
        fragments = load_fragments(diagnostics)
        validate_fragments(fragments, diagnostics)
        toc_html = build_toc(fragments, diagnostics)
        stylesheet_href = Path(
            os.path.relpath(STYLESHEET, args.html_output.parent.resolve())
        ).as_posix()
        document_html = build_document(fragments, toc_html, stylesheet_href)

        diagnostics.report()
        if diagnostics.errors:
            print("build failed: fix the errors above", file=sys.stderr)
            return 1
        if args.strict and diagnostics.warnings:
            print("build failed: warnings treated as errors (--strict)", file=sys.stderr)
            return 1

        figures = sum(len(fragment.soup.find_all("figure")) for fragment in fragments)
        heading_count = sum(len(fragment.headings) for fragment in fragments)

        if args.check:
            status = (
                f"{len(diagnostics.warnings)} warning(s)"
                if diagnostics.warnings
                else "no problems found"
            )
            print(
                f"checked {len(fragments)} fragments, {heading_count} headings, "
                f"{figures} figures: {status}"
            )
            return 0

        pages = None
        if not args.html_only:
            pages = render_pdf(
                document_html, args.pdf_output, args.html_output.parent.resolve()
            )
        atomic_write(args.html_output, document_html)

        print(
            f"wrote {args.html_output} ({len(document_html):,} bytes, "
            f"{len(fragments)} fragments, {figures} figures)"
        )
        if pages is not None:
            print(f"wrote {args.pdf_output} ({pages} pages)")
        else:
            print("skipped PDF rendering (--html-only)")
        return 0
    except (BuildError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
