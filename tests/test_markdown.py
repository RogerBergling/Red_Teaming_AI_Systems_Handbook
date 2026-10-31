"""Tests for book/make_markdown.py."""

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


markdown = load_module("handbook_markdown", ROOT / "book" / "make_markdown.py")


class TocConversionTests(unittest.TestCase):
    def test_part_and_nested_links(self) -> None:
        nav = BeautifulSoup(
            '<nav class="toc">'
            '<div class="part">Part I — Foundations</div>'
            '<a class="lvl1" href="#m1">Module 1</a>'
            '<a class="lvl2" href="#m1-lab">Lab</a>'
            "</nav>",
            "html.parser",
        ).nav
        result = markdown.build_toc(nav)
        self.assertEqual(
            result,
            "- **Part I — Foundations**\n"
            "  - [Module 1](#m1)\n"
            "    - [Lab](#m1-lab)",
        )


class SvgConversionTests(unittest.TestCase):
    def test_filename_dimensions_and_xml_declaration(self) -> None:
        name, result = markdown.extract_svg(
            '<svg viewBox="0 0 320 180"><rect width="10" height="10"/></svg>',
            1,
            "Figure 2.1 — Example",
        )
        self.assertEqual(name, "figure-2-1.svg")
        self.assertTrue(result.startswith('<?xml version="1.0" encoding="UTF-8"?>'))
        self.assertIn('xmlns="http://www.w3.org/2000/svg"', result)
        self.assertIn('width="320"', result)
        self.assertIn('height="180"', result)

    def test_caption_fallback_uses_index(self) -> None:
        name, _ = markdown.extract_svg("<svg></svg>", 3, "no numbered caption")
        self.assertEqual(name, "figure-03.svg")


class TableTests(unittest.TestCase):
    def test_literal_pipes_are_escaped(self) -> None:
        soup = BeautifulSoup(
            "<table><tr><td>left | right</td></tr></table>", "html.parser"
        )
        markdown.mark_table_pipes(soup)
        self.assertIn(r"left \| right", str(soup))


if __name__ == "__main__":
    unittest.main()
