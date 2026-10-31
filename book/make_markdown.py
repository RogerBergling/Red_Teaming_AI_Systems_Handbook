#!/usr/bin/env python3
"""Convert the generated handbook HTML into a structured Markdown edition.

The PDF is built from ``book.html``, so that file is the source of truth: it
already contains the injected plain-language briefs, deep-dive panels, figures
and the final table of contents. This script keeps that structure, extracts
every SVG into a figures directory, and rewrites the print-specific boxes as
Markdown blockquotes and tables.

Examples::

    python3 make_markdown.py --check    # validate conversion, write nothing
    python3 make_markdown.py            # write the Markdown edition and figures
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag
from markdownify import markdownify

ROOT = Path(__file__).resolve().parent
DEFAULT_SOURCE = ROOT / "book.html"
DEFAULT_MD_PATH = ROOT.parent / "Red_Teaming_AI_Systems_Handbook.md"
DEFAULT_FIG_DIR = ROOT.parent / "Red_Teaming_AI_Systems_Handbook_figures"

FIGURE_FILE_RE = re.compile(r"^figure-[\d-]+\.svg$")
UNRESOLVED_TOKEN_RE = re.compile(r"ZZ[A-Z0-9]+ZZ")

MD_OPTIONS = dict(
    heading_style="ATX",
    bullets="-",
    sub_symbol="<sub>",
    sup_symbol="<sup>",
    wrap=False,
    newline_style="backslash",
    escape_asterisks=False,
    escape_underscores=False,
)


class ConversionError(RuntimeError):
    """A fatal problem in the generated HTML or conversion step."""


def inline_md(node: Tag | NavigableString | None) -> str:
    """Convert an inline HTML fragment to Markdown without surrounding blank lines."""
    if node is None:
        return ""
    return markdownify(str(node), **MD_OPTIONS).strip()


def plain(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def lines_by_br(tag: Tag) -> list[str]:
    """Split a block on <br> boundaries, preserving inline markup as text."""
    lines: list[str] = []
    current: list[str] = []

    def flush() -> None:
        value = plain("".join(current))
        if value:
            lines.append(value)
        current.clear()

    for child in tag.children:
        if isinstance(child, Tag) and child.name == "br":
            flush()
        else:
            current.append(
                child.get_text(" ", strip=False) if isinstance(child, Tag) else str(child)
            )
    flush()
    return lines


def build_toc(nav: Tag) -> str:
    """Turn the print TOC into nested Markdown bullets with working anchors."""
    lines: list[str] = []
    for child in nav.find_all(["div", "a"], recursive=False):
        classes = child.get("class") or []
        if child.name == "div" and "part" in classes:
            lines.append(f"- **{plain(child.get_text(' ', strip=True))}**")
        elif child.name == "a":
            title = (
                plain(child.get_text(" ", strip=True))
                .replace("[", r"\[")
                .replace("]", r"\]")
            )
            target = child.get("href", "").lstrip("#")
            if "lvl2" in classes:
                lines.append(f"    - [{title}](#{target})")
            else:
                lines.append(f"  - [{title}](#{target})")
    return "\n".join(lines)


def extract_svg(svg_text: str, index: int, caption: str) -> tuple[str, str]:
    """Return the output filename and standalone SVG text for one figure.

    The source string is used verbatim rather than beautifulsoup's
    serialisation: the HTML parser lower-cases SVG attributes such as
    ``viewBox`` and ``markerWidth``, which silently breaks rendering.
    """
    match = re.search(r"Figure\s+([\d.]+)", caption)
    if match:
        stem = "figure-" + match.group(1).replace(".", "-")
    else:
        stem = f"figure-{index:02d}"
    name = f"{stem}.svg"

    opening = re.match(r"<svg\b([^>]*)>", svg_text)
    if opening is None:
        raise ConversionError(f"could not parse SVG {index}")
    attrs = opening.group(1)
    if "xmlns=" not in attrs:
        attrs += ' xmlns="http://www.w3.org/2000/svg"'
    if not re.search(r"\bwidth=", attrs):
        view_box = re.search(r'viewBox="([^"]+)"', attrs)
        if view_box:
            bits = re.split(r"[\s,]+", view_box.group(1).strip())
            if len(bits) == 4:
                try:
                    width, height = float(bits[2]), float(bits[3])
                    attrs += (
                        f' width="{int(round(width))}"'
                        f' height="{int(round(height))}"'
                    )
                except ValueError:
                    pass
    svg_text = f"<svg{attrs}>" + svg_text[opening.end():]
    # Standalone SVG is XML: HTML named entities other than the five XML ones
    # are undefined. Convert the only one used in the book.
    svg_text = svg_text.replace("&nbsp;", "&#160;")

    return name, '<?xml version="1.0" encoding="UTF-8"?>\n' + svg_text + "\n"


def mark_table_pipes(soup: BeautifulSoup) -> None:
    """Escape literal pipes so GFM does not split a table cell."""
    for cell in soup.select("table th, table td"):
        for text in list(cell.find_all(string=True)):
            if "|" in text and not re.search(r"\\\|", text):
                text.replace_with(text.replace("|", r"\|"))


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


def require(element: Tag | None, description: str) -> Tag:
    if element is None:
        raise ConversionError(f"generated HTML is missing {description}")
    return element


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert book.html into the Markdown edition."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate the conversion and exit without writing any files",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help=f"generated HTML source (default: {DEFAULT_SOURCE})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_MD_PATH,
        help=f"Markdown output path (default: {DEFAULT_MD_PATH})",
    )
    parser.add_argument(
        "--figures-dir",
        type=Path,
        default=DEFAULT_FIG_DIR,
        help=f"SVG output directory (default: {DEFAULT_FIG_DIR})",
    )
    return parser.parse_args(argv)


def convert(source: Path, md_path: Path, figures_dir: Path) -> tuple[str, dict[str, str]]:
    """Return the Markdown document and the standalone SVG files."""
    if not source.is_file():
        raise ConversionError(f"source HTML not found: {source}")

    raw_html = source.read_text(encoding="utf-8")
    soup = BeautifulSoup(raw_html, "html.parser")
    all_ids = {str(tag["id"]) for tag in soup.find_all(id=True)}

    raw_figures = re.findall(r"<figure\b.*?</figure>", raw_html, re.S)
    figure_tags = soup.find_all("figure")
    if len(raw_figures) != len(figure_tags):
        raise ConversionError(
            f"expected {len(figure_tags)} raw figures, found {len(raw_figures)}"
        )
    raw_svgs: list[str] = []
    for index, block in enumerate(raw_figures, start=1):
        found = re.search(r"<svg\b.*?</svg>", block, re.S)
        if found is None:
            raise ConversionError(f"figure {index} contains no SVG")
        raw_svgs.append(found.group(0))

    # ---------- cover: preserve as a Markdown title page ----------
    cover = require(soup.select_one("section.cover"), "section.cover")
    title = plain(require(cover.find("h1"), "cover title").get_text(" ", strip=True))
    kicker = plain(
        require(cover.select_one(".kicker"), "cover kicker").get_text(" ", strip=True)
    )
    subtitle = plain(
        require(cover.select_one(".sub"), "cover subtitle").get_text(" ", strip=True)
    )
    meta_lines = lines_by_br(require(cover.select_one(".meta"), "cover metadata"))
    bottom = plain(
        require(cover.select_one(".bottom"), "cover footer").get_text(" ", strip=True)
    )
    bottom = re.sub(r"\s+Version\s+", " — Version ", bottom)
    cover_md_parts = [
        f"# {title}",
        "",
        f"*{subtitle}*",
        "",
        f"**{kicker}**",
        "",
    ]
    for line in meta_lines:
        cover_md_parts.append(f"- {line}")
    cover_md_parts += ["", f"> {bottom}", ""]
    cover_md = "\n".join(cover_md_parts)
    cover.decompose()

    # ---------- TOC: capture the print version, then remove it ----------
    nav = require(soup.select_one("nav.toc"), "nav.toc")
    toc_targets = {
        str(link["href"])[1:]
        for link in nav.find_all("a", href=True)
        if str(link["href"]).startswith("#")
    }
    missing_targets = sorted(toc_targets - all_ids)
    if missing_targets:
        raise ConversionError(
            "TOC links to missing anchors: " + ", ".join(f"#{target}" for target in missing_targets)
        )
    toc_md = build_toc(nav)
    nav.replace_with(soup.new_tag("p"))
    holder = require(soup.select_one("h1#contents"), "h1#contents")
    placeholder = soup.new_tag("p")
    placeholder.string = "ZZTOCHOLDERZZ"
    holder.insert_after(placeholder)

    # ---------- figures: extract SVG, replace with placeholders ----------
    figure_prefix = Path(
        os.path.relpath(figures_dir.resolve(), md_path.parent.resolve())
    ).as_posix()
    figures: dict[str, str] = {}
    svg_files: dict[str, str] = {}
    for index, figure in enumerate(soup.find_all("figure"), start=1):
        svg = figure.find("svg")
        caption_tag = figure.find("figcaption")
        caption_text = plain(caption_tag.get_text(" ", strip=True)) if caption_tag else ""
        lead = caption_tag.find("b") if caption_tag else None
        alt = plain(lead.get_text(" ", strip=True)) if lead else caption_text
        alt = alt.replace("[", r"\[").replace("]", r"\]")
        if svg is None:
            raise ConversionError(f"figure {index} contains no parsed SVG")
        image_name, image_text = extract_svg(raw_svgs[index - 1], index, caption_text)
        if image_name in svg_files:
            raise ConversionError(f"figure {index}: duplicate output filename {image_name}")
        svg_files[image_name] = image_text
        caption_md = inline_md(caption_tag)
        token = f"ZZFIG{index}ZZ"
        figures[token] = f"![{alt}]({figure_prefix}/{image_name})\n\n{caption_md}"
        replacement = soup.new_tag("p")
        replacement.string = token
        figure.replace_with(replacement)

    # ---------- tables: escape pipes before Markdown conversion ----------
    mark_table_pipes(soup)

    # ---------- formulas: turn into quoted equations ----------
    for formula in soup.select("div.formula"):
        block = soup.new_tag("blockquote")
        for eq in formula.select("span.eq"):
            p = soup.new_tag("p")
            for child in list(eq.contents):
                p.append(child.extract())
            block.append(p)
        for where in formula.select("span.where"):
            p = soup.new_tag("p")
            em = soup.new_tag("em")
            em.string = "Where:"
            p.append(em)
            p.append(NavigableString(" "))
            for child in list(where.contents):
                p.append(child.extract())
            block.append(p)
        formula.replace_with(block)

    # ---------- shared box -> blockquote conversion ----------
    def quote_box(element: Tag, label: str | None) -> None:
        block = soup.new_tag("blockquote")
        if label:
            p = soup.new_tag("p")
            strong = soup.new_tag("strong")
            strong.string = label
            p.append(strong)
            block.append(p)
        for child in list(element.contents):
            if isinstance(child, Tag) and ("lbl" in (child.get("class") or [])):
                continue
            block.append(child.extract())
        element.replace_with(block)

    for brief in soup.select("div.plainbrief"):
        lbl = brief.find(class_="lbl")
        quote_box(brief, plain(lbl.get_text(" ", strip=True)) if lbl else None)

    for objectives in soup.select("div.objectives"):
        lbl = objectives.find(class_="lbl")
        quote_box(
            objectives,
            plain(lbl.get_text(" ", strip=True)) if lbl else "Learning objectives",
        )

    for quiz in soup.select("div.quiz"):
        lbl = quiz.find(class_="lbl")
        quote_box(quiz, plain(lbl.get_text(" ", strip=True)) if lbl else "Knowledge check")

    for deep in soup.select("div.deepdive"):
        lbl = deep.find(class_="lbl")
        quote_box(deep, plain(lbl.get_text(" ", strip=True)) if lbl else "Deep dive")

    for box in soup.select("div.box"):
        lbl = box.find(class_="lbl")
        quote_box(box, plain(lbl.get_text(" ", strip=True)) if lbl else None)

    # ---------- key/value blocks: readable bullet lists ----------
    for kv in soup.select("div.kv"):
        ul = soup.new_tag("ul")
        for row in kv.select("div.row"):
            key = row.find(class_="k")
            value = row.find(class_="v")
            li = soup.new_tag("li")
            strong = soup.new_tag("strong")
            strong.string = (plain(key.get_text(" ", strip=True)) + ".") if key else ""
            li.append(strong)
            li.append(NavigableString(" "))
            if value:
                for child in list(value.contents):
                    li.append(child.extract())
            ul.append(li)
        kv.replace_with(ul)

    # ---------- labels, ledes, endmarks ----------
    for label in soup.select("div.track-label"):
        text = plain(label.get_text(" ", strip=True))
        p = soup.new_tag("p")
        p.string = f"ZZTRACKLABELZZ{text}"
        label.replace_with(p)

    for endmark in soup.select("div.endmark"):
        text = plain(endmark.get_text(" ", strip=True))
        p = soup.new_tag("p")
        p.string = f"ZZENDMARKZZ{text}"
        endmark.replace_with(p)

    for chapter_label in soup.select("div.chapter-label"):
        chapter_label.decompose()

    for module_no in soup.select("span.module-no"):
        p = soup.new_tag("p")
        strong = soup.new_tag("strong")
        strong.string = plain(module_no.get_text(" ", strip=True))
        p.append(strong)
        module_no.replace_with(p)

    for dek in soup.select("p.dek, p.lede"):
        em = soup.new_tag("em")
        for child in list(dek.contents):
            em.append(child.extract())
        dek.clear()
        dek.append(em)

    # ---------- headings: resolve <br>, install explicit anchors ----------
    anchors: dict[str, str] = {}
    for n, heading in enumerate(soup.find_all(["h1", "h2", "h3"])):
        for br in heading.find_all("br"):
            br.replace_with(" ")
        hid = heading.get("id")
        if hid:
            token = f"ZZANCHOR{n}ZZ"
            anchors[token] = str(hid)
            heading.insert(0, NavigableString(token))
            del heading["id"]

    # ---------- convert ----------
    body = soup.body if soup.body is not None else soup
    markdown = markdownify(str(body), **MD_OPTIONS)

    # ---------- restore placeholders ----------
    for token, hid in anchors.items():
        markdown = markdown.replace(token, f'<a id="{hid}"></a>')
    for token, value in figures.items():
        markdown = markdown.replace(token, value)

    markdown = re.sub(
        r"ZZTRACKLABELZZ(.*)",
        lambda m: "---\n\n**" + m.group(1).strip() + "**",
        markdown,
    )
    markdown = re.sub(
        r"ZZENDMARKZZ(.*)",
        lambda m: "*" + m.group(1).strip() + "*",
        markdown,
    )
    markdown = markdown.replace("ZZTOCHOLDERZZ", toc_md)

    # Chapter separators: one rule before each top-level heading after the cover.
    # Module labels (Module 01, Foundation primer …) sit immediately before their
    # h1 in the HTML, so move them below the rule.  Never touch lines inside a
    # fenced code block: shell comments also begin with "# ".
    lines = markdown.splitlines()
    rebuilt: list[str] = []
    seen_h1 = False
    in_fence = False
    module_label = re.compile(
        r"^\*\*(Module \d+|Foundation primer[^*]*|Appendices)\*\*$"
    )
    for line in lines:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            rebuilt.append(line)
            continue
        if not in_fence and line.startswith("# "):
            if seen_h1:
                while rebuilt and not rebuilt[-1].strip():
                    rebuilt.pop()
                label = None
                if rebuilt and module_label.match(rebuilt[-1].strip()):
                    label = rebuilt.pop()
                    while rebuilt and not rebuilt[-1].strip():
                        rebuilt.pop()
                rebuilt.extend(["", "---", ""])
                if label:
                    rebuilt.extend([label, ""])
            seen_h1 = True
        rebuilt.append(line)
    markdown = "\n".join(rebuilt)

    # Fenced code inside a blockquote is not understood by every Markdown
    # implementation.  Rewrite those few blocks as indented code, which is
    # portable CommonMark and still nests correctly inside the quote.
    lines = markdown.splitlines()
    rebuilt = []
    i = 0
    while i < len(lines):
        line = lines[i]
        fence = re.match(r"^((?:> ?)+)```", line)
        if not fence:
            rebuilt.append(line)
            i += 1
            continue
        prefix = fence.group(1)
        i += 1
        code: list[str] = []
        while i < len(lines):
            candidate = lines[i]
            if candidate.startswith(prefix) and candidate[len(prefix):].strip().startswith("```"):
                break
            content = candidate
            if content.startswith(prefix):
                content = content[len(prefix):]
            elif content.rstrip() == prefix.rstrip():
                content = ""
            code.append(content)
            i += 1
        i += 1  # closing fence
        if rebuilt and rebuilt[-1].strip() not in ("", ">"):
            rebuilt.append(prefix.rstrip())
        rebuilt.append(prefix.rstrip())
        for content in code:
            rebuilt.append(prefix + ("    " + content if content else ""))
        rebuilt.append(prefix.rstrip())
    markdown = "\n".join(rebuilt)

    # Tidy spacing and orphaned quote markers.
    markdown = re.sub(r"[ \t]+\n", "\n", markdown)
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    markdown = markdown.strip() + "\n"

    front_matter = "\n".join(
        [
            "---",
            'title: "Red Teaming AI Systems — A Practitioner\'s Course Handbook"',
            'subtitle: "A practitioner\'s handbook for assessing the security of large language models, autonomous agents, retrieval pipelines and the infrastructure that runs them"',
            'author: "AI Security Curriculum"',
            'edition: "1.1"',
            'date: "2026"',
            'description: "Course handbook for an eleven-module red team curriculum, with two foundation primers on tokens, transformers and neural networks and a plain-language track in every module and foundation primer."',
            "---",
            "",
        ]
    )
    note = (
        f"> **Markdown edition.** Figures are in `{figure_prefix}/`; "
        "open this file from the same folder as that directory so the images resolve.\n\n"
    )
    final = front_matter + "\n" + cover_md + "\n" + note + "---\n\n" + markdown

    unresolved = sorted(set(UNRESOLVED_TOKEN_RE.findall(final)))
    if unresolved:
        raise ConversionError("unresolved conversion placeholders: " + ", ".join(unresolved))
    for image_name in svg_files:
        if f"{figure_prefix}/{image_name}" not in final:
            raise ConversionError(f"figure link for {image_name} is missing from the Markdown")

    return final, svg_files


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        markdown, svg_files = convert(args.source, args.output, args.figures_dir)
        words = len(re.findall(r"\S+", markdown))

        if args.check:
            print(
                f"checked {args.source}: {len(svg_files)} figures, "
                f"{words:,} words: no problems found"
            )
            return 0

        for image_name, image_text in svg_files.items():
            atomic_write(args.figures_dir / image_name, image_text)

        stale = [
            path
            for path in args.figures_dir.glob("*.svg")
            if FIGURE_FILE_RE.match(path.name) and path.name not in svg_files
        ]
        for path in stale:
            path.unlink()

        atomic_write(args.output, markdown)

        print(
            f"wrote {args.output} ({words:,} words, "
            f"{len(markdown.encode('utf-8')):,} bytes)"
        )
        print(f"wrote {len(svg_files)} figures to {args.figures_dir}")
        if stale:
            print(f"removed {len(stale)} stale figure(s)")
        return 0
    except (ConversionError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
