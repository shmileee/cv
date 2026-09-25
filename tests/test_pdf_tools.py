"""Regression checks for searchable PDFs and exact tag packing (stdlib only)."""

import importlib.util
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch


def load(name, filename):
    path = Path(__file__).resolve().parents[1] / "scripts" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pdf = load("pdf_text", "normalize-pdf-text.py")
tags = load("tag_packing", "pack-tags.py")


class PdfTextTests(unittest.TestCase):
    def stream(self, entries, font=b"Lato"):
        cmap = (b"begincmap\n/CMapName /ABC+" + font + b"-UTF16 def\n"
                b"4 beginbfchar\n" + entries + b"\nendbfchar\nendcmap")
        return zlib.compress(cmap, 0)

    def test_hyphen_destination_changes_but_source_glyph_and_other_text_do_not(self):
        raw = self.stream(b"<0001> <2010>\n<2010> <0041>\n<0003> <F041>\n<0004> <0142>")
        result = pdf.patch_stream(raw)
        self.assertEqual(len(raw), len(result))
        decoded = zlib.decompress(result)
        self.assertIn(b"<0001> <002D>", decoded)
        self.assertIn(b"<2010> <0041>", decoded)
        self.assertIn(b"<0003> <F041>", decoded)
        self.assertIn(b"<0004> <0142>", decoded)

    def test_only_fontawesome_private_use_destinations_become_spaces(self):
        raw = self.stream(b"<0048> <F041>\n<0077> <F073>\n<009D> <F09B>\n<00D2> <F0E1>",
                          b"FontAwesome")
        result = pdf.patch_stream(raw)
        self.assertEqual(len(raw), len(result))
        self.assertEqual(zlib.decompress(result).count(b"<0020>"), 4)
        self.assertIsNone(pdf.patch_stream(result))

    def test_non_cmap_streams_are_untouched(self):
        raw = zlib.compress(b"BT /F1 10 Tf <2010> Tj ET")
        self.assertIsNone(pdf.patch_stream(raw))
        self.assertIsNone(pdf.patch_stream(b"not compressed"))

    def test_lato_space_mapping_keeps_q_searchable_and_is_idempotent(self):
        for font in (b"Lato-Regular", b"Lato-Bold"):
            raw = self.stream(b"<0003> <0041>\n<0020> <0051>", font)
            result = pdf.patch_stream(raw)
            self.assertEqual(len(result), len(raw))
            self.assertIn(b"<0020> <0051>", zlib.decompress(result))
            self.assertIn(b"<0002> <0020>", zlib.decompress(result))
            self.assertIsNone(pdf.patch_stream(result))

    def test_oversized_replacement_fails_instead_of_breaking_offsets(self):
        raw = self.stream(b"<0001> <2010>")
        with patch.object(pdf.zlib, "compress", return_value=b"x" * (len(raw) + 1)):
            with self.assertRaisesRegex(SystemExit, "no longer fits"):
                pdf.patch_stream(raw)

    def test_stream_separator_is_never_used_as_compression_space(self):
        raw = self.stream(b"<0001> <2010>")
        for separator in (b"\n", b"\r\n"):
            original = (b"1 0 obj\n<</Filter/FlateDecode/Length " +
                        str(len(raw)).encode() + b">>\nstream\n" + raw +
                        separator + b"endstream\nendobj\n")
            with patch.object(pdf.zlib, "compress", return_value=b"x" * (len(raw) + 1)):
                with self.assertRaisesRegex(SystemExit, "no longer fits"):
                    pdf.patch_pdf(original)
            result, count = pdf.patch_pdf(original)
            self.assertEqual(count, 1)
            self.assertEqual(len(original), len(result))
            self.assertEqual(original.index(b"endstream"), result.index(b"endstream"))
            self.assertTrue(result.endswith(separator + b"endstream\nendobj\n"))
            self.assertIn(b"<0001> <002D>", zlib.decompress(result.split(b"stream\n", 1)[1]))
            self.assertEqual(pdf.patch_pdf(result), (result, 0))

    def test_optional_cmap_spacing_can_make_an_oversized_replacement_fit(self):
        raw = self.stream(b"<0001> <2010>")
        compress = zlib.compress
        def tight_stream(data, level):
            if b"> <" in data:
                return b"x" * (len(raw) + 1)
            return compress(data, level)
        with patch.object(pdf.zlib, "compress", side_effect=tight_stream):
            result = pdf.patch_stream(raw)
        self.assertEqual(len(result), len(raw))
        self.assertIn(b"<0001><002D>", zlib.decompress(result))

    def test_affected_range_fails_instead_of_remapping_unrelated_glyphs(self):
        raw = zlib.compress(b"begincmap\n1 beginbfrange\n<0001> <0002> <2010>\n"
                            b"endbfrange\nendcmap")
        with self.assertRaisesRegex(SystemExit, "unsupported CMap range"):
            pdf.patch_stream(raw)


class PackingTests(unittest.TestCase):
    def test_finds_two_rows_when_first_fit_decreasing_needs_three(self):
        widths = dict(zip("abcdef", [6, 5, 3, 2, 2, 2]))
        rows = tags.pack(list(widths), widths, 10.1, 0)
        self.assertEqual(len(rows), 2)
        self.assertEqual([sum(widths[tag] for tag in row) for row in rows], [10, 10])
        self.assertEqual(sorted(tag for row in rows for tag in row), sorted(widths))

    def test_real_gaps_and_slack_are_accounted_for(self):
        widths = dict(zip("abcde", [6, 5, 3, 2, 2]))
        rows = tags.pack(list(widths), widths, 11.1, 1)
        used = [sum(widths[tag] for tag in row) + len(row) - 1 for row in rows]
        self.assertTrue(all(width <= 11.1 for width in used))
        self.assertEqual(used, sorted(used, reverse=True))
        flattened = [tag for row in rows for tag in row]
        self.assertEqual(tags.pack(flattened, widths, 11.1, 1), rows)

    def test_oversized_tag_is_reported(self):
        with self.assertRaisesRegex(SystemExit, "wider than the sidebar"):
            tags.pack(["too wide"], {"too wide": 15}, 10, 1)


if __name__ == "__main__":
    unittest.main()
