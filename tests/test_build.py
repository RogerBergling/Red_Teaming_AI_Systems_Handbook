"""Tests for book/build.py (stdlib unittest, no WeasyPrint needed)."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


build = load_module("handbook_build", ROOT / "book" / "build.py")


def fragment(name: str, text: str):
    soup = BeautifulSoup(text, "html.parser")
    return build.Fragment(Path(name), text, soup, build.collect_headings(soup, name))


class TrackInjectionTests(unittest.TestCase):
    def test_brief_follows_objectives_and_deep_precedes_lab(self) -> None:
        source = (
            '<div class="objectives"><div class="lbl">Objectives</div>'
            "<ul><li>one</li></ul></div>\n"
            '<h2 id="m1-lab">Lab</h2>'
        )
        diagnostics = build.Diagnostics()
        result = build.inject_tracks(
            source,
            "01_intro.html",
            "<!--BRIEF-->\nPlain brief\n<!--DEEP-->\nDeep detail",
            diagnostics,
            "01.html",
        )
        self.assertIn("Plain brief", result)
        self.assertIn("Deep detail", result)
        self.assertLess(result.index("Plain brief"), result.index("Deep detail"))
        self.assertLess(result.index("Deep detail"), result.index('id="m1-lab"'))
        self.assertEqual(diagnostics.warnings, [])

    def test_missing_deep_marker_warns_and_leaves_text_alone(self) -> None:
        diagnostics = build.Diagnostics()
        source = "<p>unchanged</p>"
        result = build.inject_tracks(
            source, "01_intro.html", "brief only", diagnostics, "01.html"
        )
        self.assertEqual(result, source)
        self.assertTrue(any("<!--DEEP-->" in warning for warning in diagnostics.warnings))


class TocTests(unittest.TestCase):
    def test_parts_override_and_skipped_front_matter_headings(self) -> None:
        fragments = [
            fragment(
                "00_front.html",
                '<h1 id="about" data-toc="About this handbook">About</h1>'
                '<h2 id="how-to-use">How to use this book</h2>'
                '<h1 id="contents">Contents</h1>',
            ),
            fragment(
                "01_intro.html",
                '<h1 id="m1">Module 1</h1><h2 id="m1-lab">Lab</h2>',
            ),
        ]
        diagnostics = build.Diagnostics()
        toc = build.build_toc(fragments, diagnostics)
        self.assertIn("Front matter", toc)
        self.assertIn("Part I — Foundations", toc)
        self.assertIn('href="#about"', toc)
        self.assertIn(">About this handbook<", toc)
        self.assertIn('href="#m1-lab"', toc)
        self.assertNotIn("How to use this book", toc)
        self.assertNotIn(">Contents<", toc)
        self.assertEqual(diagnostics.errors, [])


class ValidationTests(unittest.TestCase):
    def test_duplicate_ids_are_errors(self) -> None:
        fragments = [
            fragment("a.html", '<h1 id="same">A</h1><!--TOC-->'),
            fragment("b.html", '<h2 id="same">B</h2>'),
        ]
        diagnostics = build.Diagnostics()
        build.validate_fragments(fragments, diagnostics)
        self.assertTrue(any("duplicate id" in error for error in diagnostics.errors))

    def test_missing_toc_marker_is_an_error(self) -> None:
        diagnostics = build.Diagnostics()
        build.validate_fragments([fragment("a.html", '<h1 id="x">A</h1>')], diagnostics)
        self.assertTrue(any("<!--TOC-->" in error for error in diagnostics.errors))

    def test_figure_needs_svg_and_caption(self) -> None:
        source = '<h1 id="x">A</h1><!--TOC--><figure><svg></svg></figure>'
        diagnostics = build.Diagnostics()
        build.validate_fragments([fragment("a.html", source)], diagnostics)
        self.assertTrue(any("figcaption" in error for error in diagnostics.errors))

    def test_missing_anchor_is_an_error(self) -> None:
        source = (
            '<h1 id="x">A</h1><!--TOC-->'
            '<p><a href="#does-not-exist">broken</a></p>'
        )
        diagnostics = build.Diagnostics()
        build.validate_fragments([fragment("a.html", source)], diagnostics)
        self.assertTrue(any("does-not-exist" in error for error in diagnostics.errors))


if __name__ == "__main__":
    unittest.main()
