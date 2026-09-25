#!/usr/bin/env python3

"""Rewrite the PDF's ToUnicode CMaps so an extracted hyphen is U+002D.

Lato's cmap reaches one glyph, named `hyphen`, from three codepoints: U+002D
HYPHEN-MINUS, U+00AD SOFT HYPHEN and U+2010 HYPHEN. xdvipdfmx builds ToUnicode
by reverse-mapping glyph IDs through that cmap, and with three candidates for
one glyph it emits the last it finds -- U+2010. Every hyphen in the finished
document therefore extracts as U+2010, and none of them match a search for the
ASCII hyphen a reader actually types:

    on-call  multi-region  multi-account  multi-tenant  cell-based
    policy-defined  self-managed  smart-card  sign-on  admission-time
    aleksandr-ponomarov

`multi-region` and `multi-account` are verbatim phrases in the AWS-facing job
descriptions this CV answers, and `On-call` is a tag in the expertise column,
so the loss is not cosmetic.

Nothing on the TeX side can fix it. The mapping is a property of the font's
cmap, not of the input encoding, and it survives Ligatures=NoCommon, an empty
Mapping, an explicit \\char"002D and bold -- all four were tried. The remaining
choices are to patch the font or to patch the CMap, and the CMap is the far
smaller object.

The patch is `<2010>` -> `<002D>` inside the ToUnicode streams. Both are four
hex digits, so the decompressed CMap keeps its exact length, and recompressing
it at level 9 lands at or under the original compressed length. Padding the
remainder with newlines keeps the stream byte-for-byte the same size, which is
what lets this run as an in-place edit: no object moves, so the cross-reference
table stays correct and the file needs no structural rewrite. zlib stops at its
own end-of-stream marker and ignores the padding.

Python 3 only, standard library only -- see the note in README.md.
"""

import re
import sys
import zlib
from pathlib import Path

# The glyph is reachable from U+002D, U+00AD and U+2010; only U+2010 is ever
# emitted, so it is the only one this has to rewrite.
WRONG = b"<2010>"
RIGHT = b"<002D>"


def patch_stream(raw: bytes) -> bytes | None:
    """Return a same-length replacement for one ToUnicode stream, or None."""
    try:
        decoded = zlib.decompress(raw)
    except zlib.error:
        return None

    # Only ToUnicode CMaps, never a content stream that happens to hold the
    # same four digits as coordinate data.
    if b"beginbfchar" not in decoded and b"beginbfrange" not in decoded:
        return None
    if WRONG not in decoded:
        return None

    patched = decoded.replace(WRONG, RIGHT)
    if len(patched) != len(decoded):
        raise SystemExit("ascii-hyphens: replacement changed the CMap length")

    compressed = zlib.compress(patched, 9)
    if len(compressed) > len(raw):
        raise SystemExit(
            "ascii-hyphens: patched CMap no longer fits its stream "
            f"({len(compressed)} > {len(raw)} bytes)"
        )
    return compressed + b"\n" * (len(raw) - len(compressed))


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: ascii-hyphens.py <pdf>", file=sys.stderr)
        return 2

    path = Path(argv[1])
    original = path.read_bytes()
    patched = bytearray(original)
    count = 0

    for match in re.finditer(rb"stream\r?\n", original):
        start = match.end()
        end = original.find(b"endstream", start)
        if end < 0:
            continue
        replacement = patch_stream(original[start:end])
        if replacement is None:
            continue
        patched[start:end] = replacement
        count += 1

    if count == 0:
        # A silent no-op would let a font change reintroduce the problem
        # without the build ever mentioning it.
        print(
            "ascii-hyphens: no ToUnicode CMap mapped a hyphen to U+2010; "
            "if the font changed, confirm the extracted text still uses "
            "U+002D before removing this step.",
            file=sys.stderr,
        )
        return 1

    if len(patched) != len(original):
        raise SystemExit("ascii-hyphens: file length changed; xref would break")

    path.write_bytes(bytes(patched))
    print(f"[cv] Rewrote {count} ToUnicode CMap(s) to ASCII hyphens")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
