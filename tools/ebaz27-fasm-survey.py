#!/usr/bin/env python3
"""EBAZ-27: read-only, conservative survey of decoded Project X-Ray FASM.

A feature line does not prove an occupied site; no tile is labelled SAFE_FREE.
Only Python 3 stdlib. Does not access hardware, NAND, or .bit contents.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

FEATURE_RE = re.compile(r"^([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)(?:\s*=\s*(\S+))?$")
CLASSES = [
    ("CLB", re.compile(r"^(?:CLB|CLE|SLICE)")),
    ("BRAM", re.compile(r"^(?:BRAM|RAMB)")),
    ("DSP", re.compile(r"^DSP")),
    ("IOB", re.compile(r"^(?:IOB|LIOB|RIOB|IOI|LIOI|RIOI)")),
    ("CLOCK", re.compile(r"^(?:CLK|HCLK|BUFG|CMT|MMCM|PLL)")),
    ("INTERCONNECT", re.compile(r"^(?:INT|LINT|RINT)")),
]

def kind(tile):
    prefix = tile.split("_X")[0]
    for name, rx in CLASSES:
        if rx.search(prefix):
            return name
    return "OTHER_OR_UNKNOWN"

def survey(path):
    counts = Counter()
    tiles = defaultdict(lambda: {"features": 0, "classes": Counter()})
    ignored = Counter()
    examples = []
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for raw in f:
            hasher.update(raw)
            line = raw.decode("utf-8", errors="replace").strip()
            if not line or line.startswith("#"):
                continue
            # FASM feature lines typically include TILE.FEATURE and may
            # include a decimal/hex assignment or bit-field index syntax.
            # Only tile prefix is parsed here; retain conservative unknowns.
            match = re.match(r"^([A-Za-z][A-Za-z0-9_]*_X\d+Y\d+)\.", line)
            if not match:
                ignored["unparsed_noncomment"] += 1
                if len(examples) < 12:
                    examples.append(line[:200])
                continue
            tile = match.group(1)
            cls = kind(tile)
            counts[cls] += 1
            tiles[tile]["features"] += 1
            tiles[tile]["classes"][cls] += 1
    result = {
        "input_name": path.name,
        "sha256": hasher.hexdigest(),
        "feature_line_counts_by_tile_class": dict(sorted(counts.items())),
        "tiles_with_expressed_features": len(tiles),
        "tile_counts_by_class": dict(sorted(Counter(kind(x) for x in tiles).items())),
        "unparsed_lines": ignored["unparsed_noncomment"],
        "unparsed_examples": examples,
        "tile_feature_counts": {k: v["features"] for k, v in sorted(tiles.items())},
        "status": "FASM_TEXT_SURVEY_ONLY",
        "limitations": [
            "No occupied/free resource inference",
            "Missing FASM features cannot establish absence of circuitry",
            "Unknown bits and incomplete Project X-Ray database require separate accounting",
            "Clock, PIP, IOB and shared routing may cross tiles or partitions",
            "No full device tilegrid or Vivado placement/routing was inspected",
            "Original factory .bit cannot be safely extended from this report",
        ],
    }
    return result

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("fasm", type=Path)
    p.add_argument("--json", type=Path, dest="output")
    args = p.parse_args()
    if not args.fasm.is_file():
        p.error("FASM source file does not exist")
    report = survey(args.fasm)
    print(json.dumps({k:v for k,v in report.items() if k != "tile_feature_counts"}, indent=2))
    if args.output:
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        print("REPORT:", args.output)
    if report["unparsed_lines"]:
        print("WARNING: some non-comment lines unparsed; do not claim complete FASM inventory")

if __name__ == "__main__":
    main()
