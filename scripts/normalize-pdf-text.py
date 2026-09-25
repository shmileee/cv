#!/usr/bin/env python3

"""Normalize PDF text mappings without changing appearance or object offsets.

Lato's hyphen maps to U+2010 instead of searchable ASCII U+002D. FontAwesome
icons map to private-use characters that pollute extracted contact details and
dates. Map those decorative glyphs to spaces while retaining their appearance.
Restore Lato's omitted space mapping so extractors infer word gaps correctly.

Only destination codes in Unicode CMaps are remapped, never source glyph IDs.
Recompression and padding preserve every stream's length and the PDF's xref.
Uses only the standard library, including on macOS's Python 3.9.
"""

from __future__ import annotations

import re
import sys
import zlib
from pathlib import Path

BFCHAR = re.compile(rb"(beginbfchar\s+)(.*?)(\s+endbfchar)", re.DOTALL)
ENTRY = re.compile(rb"(<[0-9a-fA-F]+>\s*)<([0-9a-fA-F]{4})>")


def patch_stream(raw: bytes) -> bytes | None:
    """Return a same-length replacement for one ToUnicode stream, or None."""
    try:
        decoded = zlib.decompress(raw)
    except zlib.error:
        return None

    if b"begincmap" not in decoded:
        return None
    icons = b"FontAwesome-" in decoded

    def replace_entry(match: re.Match) -> bytes:
        code = int(match[2], 16)
        if code == 0x2010:
            return match[1] + b"<002D>"
        if icons and 0xE000 <= code <= 0xF8FF:
            return match[1] + b"<0020>"
        return match[0]

    patched = BFCHAR.sub(
        lambda match: match[1] + ENTRY.sub(replace_entry, match[2]) + match[3],
        decoded,
    )
    # xdvipdfmx emits the affected glyphs as bfchar entries. Fail explicitly
    # if a future font/engine emits one inside a range; moving the range's
    # start would also remap unrelated characters.
    for block in re.findall(rb"beginbfrange(.*?)endbfrange", patched, re.DOTALL):
        for line in block.splitlines():
            destinations = re.findall(rb"<([0-9a-fA-F]{4})>", line)[2:]
            if any(int(code, 16) == 0x2010 or
                   (icons and 0xE000 <= int(code, 16) <= 0xF8FF)
                   for code in destinations):
                raise SystemExit("pdf-text: affected glyph in an unsupported CMap range")
    needs_remapping = patched != decoded

    # xdvipdfmx emits word gaps as positioning, omitting the space glyph from
    # Lato's subset. Without a Unicode space mapping, pypdf mistakes CID 32
    # (Q in this font) for a space once Qualys introduces that letter. The
    # pinned Lato Regular/Bold fonts both use CID 2 for their real space.
    # Declaring this unused mapping changes no painted glyph or advance.
    if re.search(rb"\+Lato-(?:Regular|Bold)-UTF16", patched):
        has_space = any(
            int(entry[2], 16) == 0x20
            for block in BFCHAR.finditer(patched)
            for entry in ENTRY.finditer(block[2])
        )
        if not has_space:
            if re.search(rb"<0002>", patched):
                raise SystemExit("pdf-text: Lato space glyph is already mapped unexpectedly")
            patched = re.sub(
                rb"(\d+) beginbfchar",
                lambda match: str(int(match[1]) + 1).encode() +
                b" beginbfchar\n<0002> <0020>",
                patched, count=1,
            )
            needs_remapping = True
    if not needs_remapping:
        return None

    compressed = zlib.compress(patched, 9)
    if len(compressed) > len(raw):
        # Hex strings delimit themselves in CMaps. Omit optional spaces
        # between them if a changed destination compresses slightly worse.
        compact = re.sub(rb">[ \t]+<", b"><", patched)
        compact = re.sub(
            rb"/CIDSystemInfo\s*<<\s*/Registry\s*\(Adobe\)\s*"
            rb"/Ordering\s*\(UCS\)\s*/Supplement\s+0\s*>>",
            b"/CIDSystemInfo<</Registry(Adobe)/Ordering(UCS)/Supplement 0>>",
            compact,
        )
        compressed = zlib.compress(compact, 9)
    if len(compressed) > len(raw):
        raise SystemExit(
            "pdf-text: patched CMap no longer fits its stream "
            f"({len(compressed)} > {len(raw)} bytes)"
        )
    return compressed + b"\n" * (len(raw) - len(compressed))


def patch_pdf(original: bytes) -> tuple[bytes, int]:
    """Patch Tectonic's direct-length streams, retaining their EOL separators."""
    patched = bytearray(original)
    count = 0
    for match in re.finditer(rb"\bstream\r?\n", original):
        header_start = original.rfind(b"obj", 0, match.start()) + 3
        header = original[header_start:match.start()]
        length = re.search(rb"/Length\s+(\d+)\s*>>\s*$", header)
        if length is None:
            raise SystemExit("pdf-text: unsupported stream length declaration")
        start = match.end()
        end = start + int(length[1])
        if not original[end:].startswith((b"\nendstream", b"\r\nendstream")):
            raise SystemExit("pdf-text: stream length does not match its boundary")
        replacement = patch_stream(original[start:end])
        if replacement is None:
            continue
        patched[start:end] = replacement
        count += 1
    if len(patched) != len(original):
        raise SystemExit("pdf-text: file length changed; xref would break")
    return bytes(patched), count


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: normalize-pdf-text.py <pdf>", file=sys.stderr)
        return 2

    path = Path(argv[1])
    original = path.read_bytes()
    patched, count = patch_pdf(original)

    if count == 0:
        print(
            "[cv] No PDF text mappings needed normalization; "
            "verify extraction if the font or engine changed."
        )
        return 0

    path.write_bytes(patched)
    print(f"[cv] Normalized {count} ToUnicode CMap(s): hyphens, spaces and decorative icons")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
