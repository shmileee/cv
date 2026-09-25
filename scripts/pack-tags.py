#!/usr/bin/env python3

"""Bin-pack expertise tags using widths measured by the CV's LaTeX engine."""

from __future__ import annotations

import argparse
import math
import re
import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIDEBAR = ROOT / "src/sidebars/page1.tex"
GROUP = re.compile(r"(?:\\cvtag\{[^{}\n]+\}\n)+")
TAG = re.compile(r"\\cvtag\{([^{}\n]+)\}")


def measure(tags: list[str]) -> tuple[dict[str, float], float, float]:
    """Measure complete tag boxes, the real inter-tag gap and the column."""
    lines = [
        r"\documentclass[10pt,a4paper,ragged2e]{altacv}",
        r"\input{preamble}",
        r"\begin{document}",
        r"\newsavebox{\tagmeasure}",
        r"\typeout{TAGCOLUMN=\the\marginparwidth}",
    ]
    for index, tag in enumerate(tags):
        lines.extend([
            r"\sbox{\tagmeasure}{\cvtag{" + tag + "}}",
            r"\typeout{TAGWIDTH:" + str(index) + r"=\the\wd\tagmeasure}",
        ])
    lines.extend([
        r"\sbox{\tagmeasure}{\cvtag{" + tags[0] + r"} \cvtag{" + tags[1] + "}}",
        r"\typeout{TAGPAIR=\the\wd\tagmeasure}",
        r"Tag measurements.\end{document}",
    ])
    with tempfile.TemporaryDirectory(prefix="cv-tags-") as directory:
        work = Path(directory)
        for name in ("altacv.cls", "preamble.tex"):
            shutil.copyfile(ROOT / "src" / name, work / name)
        (work / "measure.tex").write_text("\n".join(lines) + "\n")
        result = subprocess.run(
            ["tectonic", "-X", "compile", "measure.tex", "--keep-logs", "--untrusted"],
            cwd=work, capture_output=True, text=True,
        )
        if result.returncode:
            raise SystemExit(result.stdout + result.stderr)
        log = (work / "measure.log").read_text()
    widths = {
        tags[int(index)]: float(width)
        for index, width in re.findall(r"TAGWIDTH:(\d+)=([\d.]+)pt", log)
    }
    if len(widths) != len(tags):
        raise SystemExit("Could not measure every tag")
    column = float(re.search(r"TAGCOLUMN=([\d.]+)pt", log)[1])
    pair = float(re.search(r"TAGPAIR=([\d.]+)pt", log)[1])
    return widths, column, pair - widths[tags[0]] - widths[tags[1]]


def pack(tags: list[str], widths: dict[str, float], column: float, gap: float) -> list[list[str]]:
    """Minimize row count, then fill earlier rows as fully as possible."""
    # Charge a gap to every item and add one gap to capacity. This makes a
    # subset's width additive; 0.1pt headroom absorbs TeX's printed rounding.
    capacity = column + gap - 0.1
    weights = [widths[tag] + gap for tag in tags]
    full = (1 << len(tags)) - 1
    totals = [0.0] * (full + 1)
    for mask in range(1, full + 1):
        bit = mask & -mask
        totals[mask] = totals[mask ^ bit] + weights[bit.bit_length() - 1]
    if max(weights) > capacity:
        raise SystemExit("A tag is wider than the sidebar: " + ", ".join(tags))
    feasible = [mask for mask in range(1, full + 1) if totals[mask] <= capacity]
    feasible.sort(key=lambda mask: (
        -totals[mask], tuple(sorted(tags[i] for i in range(len(tags)) if mask >> i & 1)),
    ))
    by_item = [[mask for mask in feasible if mask >> i & 1] for i in range(len(tags))]
    largest_first = sorted(range(len(tags)), key=lambda i: (-weights[i], tags[i]))

    @lru_cache(None)
    def fits(mask: int, rows: int) -> bool:
        if not mask:
            return True
        if rows < 1 or totals[mask] > rows * capacity:
            return False
        if totals[mask] <= capacity:
            return True
        first = next(i for i in largest_first if mask >> i & 1)
        return any(
            row & mask == row and fits(mask ^ row, rows - 1)
            for row in by_item[first]
        )

    count = math.ceil(totals[full] / capacity)
    while not fits(full, count):
        count += 1
    remaining, rows = full, []
    for left in range(count, 0, -1):
        row = next(row for row in feasible
                   if row & remaining == row and fits(remaining ^ row, left - 1))
        rows.append([tags[i] for i in range(len(tags)) if row >> i & 1])
        remaining ^= row
    assert not remaining
    # Source newlines are spaces, so TeX must reproduce these exact rows
    # without explicit line breaks or stretched gaps.
    actual, current, used = [], [], 0.0
    for tag in (tag for row in rows for tag in row):
        extra = widths[tag] + (gap if current else 0)
        if used + extra > column:
            actual.append(current)
            current, used, extra = [], 0.0, widths[tag]
        current.append(tag)
        used += extra
    actual.append(current)
    assert actual == rows, "Greedy LaTeX wrapping would change the packed rows"
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="check without rewriting")
    args = parser.parse_args()
    source = SIDEBAR.read_text()
    tags = list(dict.fromkeys(TAG.findall(source)))
    widths, column, gap = measure(tags)
    total_rows = 0

    def replace(match: re.Match) -> str:
        nonlocal total_rows
        rows = pack(TAG.findall(match[0]), widths, column, gap)
        total_rows += len(rows)
        for row in rows:
            width = sum(widths[tag] for tag in row) + gap * (len(row) - 1)
            print(f"{width / column:6.1%}  " + " | ".join(row))
        return "".join(r"\cvtag{" + tag + "}\n" for row in rows for tag in row)

    packed = GROUP.sub(replace, source)
    print(f"{len(tags)} tags, {total_rows} rows, {column:.2f}pt column")
    if args.check and packed != source:
        raise SystemExit("Tags need repacking: run mise run pack-tags")
    if not args.check:
        SIDEBAR.write_text(packed)


if __name__ == "__main__":
    main()
