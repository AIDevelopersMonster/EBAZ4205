#!/usr/bin/env python3
"""EBAZ-27: map expressed factory FASM features onto the complete XC7Z010 tilegrid.

READ-ONLY: no .bit/NAND/FPGA writes, no Vivado. Reports go to an external
private output directory. A tile without a decoded feature is NOT a free tile.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re
from xml.sax.saxutils import escape

FACTORY_FASM_SHA256 = "f22e32fc1608a9cee8ce30757b7d8f2856b3a307492534b02aafa7b90738b66b"
TILE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*_X[0-9]+Y[0-9]+)\.([^\s#]+)")
UNKNOWN_BIT_RE = re.compile(r'unknown_bit\s*=\s*"([^"]+)"')
UNKNOWN_SEG_RE = re.compile(r'unknown_segment\s*=\s*"([^"]+)"')


def group(tile_type):
    x = tile_type.upper()
    if x.startswith(("CLBL", "CLE", "SLICE")):
        return "CLB"
    if x.startswith(("BRAM", "RAMB")):
        return "BRAM"
    if x.startswith("DSP"):
        return "DSP"
    if x.startswith(("IOB", "IOI", "LIOB", "RIOB", "LIOI", "RIOI")):
        return "IOB"
    if x.startswith(("CLK", "HCLK", "CMT", "MMCM", "PLL", "BUFG")):
        return "CLOCK"
    if x.startswith(("INT", "LINT", "RINT")):
        return "INTERCONNECT"
    if x.startswith("PS7"):
        return "PS7"
    return "OTHER_OR_UNKNOWN"


def examine(fasm_path, grid_path, expected_sha):
    data = json.loads(grid_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data:
        raise ValueError("STOP: empty or unexpected tilegrid.json")
    # Tilegrid must contain one map entry per physical tile, not a part.yaml.
    if not any(isinstance(v, dict) and "grid_x" in v and "type" in v for v in data.values()):
        raise ValueError("STOP: tilegrid missing grid_x/type")
    feature_counts = Counter()
    example_features = defaultdict(list)
    unknown_segments = Counter()
    unknown_frames = Counter()
    unknown_examples = []
    other_examples = []
    unknown_count = other_count = blank_count = comment_count = 0
    lines = 0
    digest = hashlib.sha256()

    with fasm_path.open("rb") as f:
        for raw in f:
            digest.update(raw)
            lines += 1
            line = raw.decode("utf-8", "replace").strip()
            if not line:
                blank_count += 1
                continue
            if line.startswith("#"):
                comment_count += 1
                continue
            m = TILE_RE.match(line)
            if m:
                tile, feature = m.groups()
                feature_counts[tile] += 1
                if len(example_features[tile]) < 3:
                    example_features[tile].append(feature)
                continue
            bits = UNKNOWN_BIT_RE.findall(line)
            if bits:
                unknown_count += len(bits)
                for bit in bits:
                    frame = bit.split("_")[0].lower()
                    unknown_frames[frame] += 1
                segments = UNKNOWN_SEG_RE.findall(line)
                for seg in segments:
                    unknown_segments[seg] += 1
                if len(unknown_examples) < 12:
                    unknown_examples.append(line[:200])
                continue
            other_count += 1
            if len(other_examples) < 12:
                other_examples.append(line[:200])

    actual_sha = digest.hexdigest()
    if expected_sha and actual_sha != expected_sha.lower():
        raise ValueError("STOP: FASM SHA256 mismatch, expected %s but got %s" %
                         (expected_sha, actual_sha))

    rows = []
    tile_totals = Counter()
    tile_with_features = Counter()
    line_totals = Counter()
    for tile, item in data.items():
        if not isinstance(item, dict):
            raise ValueError("STOP: malformed tilegrid entry for " + tile)
        typ = str(item.get("type", "UNKNOWN"))
        category = group(typ)
        tile_totals[category] += 1
        features = feature_counts[tile]
        if features:
            tile_with_features[category] += 1
            line_totals[category] += features
        sites = item.get("sites") or {}
        rows.append({
            "tile": tile,
            "tile_type": typ,
            "category": category,
            "grid_x": item.get("grid_x"),
            "grid_y": item.get("grid_y"),
            "site_count": len(sites) if isinstance(sites, dict) else 0,
            "features_expressed": features,
            "evidence": "FEATURES_EXPRESSED" if features else "NO_DECODED_FEATURES",
            "free_status": "UNKNOWN_NOT_PROVEN_FREE",
            "feature_samples": " | ".join(example_features[tile]),
        })
    grid_set = set(data)
    outside = [(t, n) for t, n in feature_counts.items() if t not in grid_set]
    outside.sort(key=lambda x: -x[1])
    report = {
        "status": "PHYSICAL_TILEGRID_SURVEY_ONLY",
        "input": {"fasm": fasm_path.name, "fasm_sha256": actual_sha,
                  "tilegrid": str(grid_path), "tilegrid_sha256":
                  hashlib.sha256(grid_path.read_bytes()).hexdigest()},
        "fasm_lines": lines,
        "feature_lines_parsed": sum(feature_counts.values()),
        "unknown_bit_annotations": unknown_count,
        "unknown_frames_count": len(unknown_frames),
        "unknown_segments_count": len(unknown_segments),
        "unknown_bit_examples": unknown_examples,
        "top_unknown_segments": unknown_segments.most_common(30),
        "unclassified_noncomment_lines": other_count,
        "unclassified_examples": other_examples,
        "comments": comment_count, "blank_lines": blank_count,
        "grid_tiles_total": len(rows),
        "grid_tiles_with_expressed_features": sum(bool(feature_counts[x]) for x in data),
        "features_with_tile_not_in_grid": sum(n for _, n in outside),
        "tiles_not_in_grid_examples": outside[:20],
        "class_counts": {
            key: {"all_tiles_in_grid": tile_totals[key],
                  "tiles_with_expressed_features": tile_with_features[key],
                  "expressed_feature_lines": line_totals[key]}
            for key in sorted(tile_totals)
        },
        "meaning": [
            "Tilegrid coordinates are physical tile locations, not placement utilization.",
            "NO_DECODED_FEATURES does not mean unused or free.",
            "Even FEATURES_EXPRESSED does not demonstrate an occupied LUT or site.",
            "Unknown bit annotations are frame-level and NOT assigned to tiles here.",
            "No PIP/BEL/site ownership, static boundary, routing clearance or DFX validity proven.",
            "Every tile free_status intentionally stays UNKNOWN_NOT_PROVEN_FREE."
        ],
    }
    return report, rows


def save_csv(path, rows):
    columns = ["tile", "tile_type", "category", "grid_x", "grid_y",
               "site_count", "features_expressed", "evidence",
               "free_status", "feature_samples"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)


def save_svg(path, rows):
    positioned = [r for r in rows
                  if isinstance(r["grid_x"], int) and isinstance(r["grid_y"], int)]
    if not positioned:
        raise ValueError("STOP: tilegrid has no numeric physical coordinates")
    min_x = min(r["grid_x"] for r in positioned)
    min_y = min(r["grid_y"] for r in positioned)
    max_x = max(r["grid_x"] for r in positioned)
    max_y = max(r["grid_y"] for r in positioned)
    cell = 6
    left, top = 15, 64
    width = (max_x - min_x + 1) * cell + 30
    height = (max_y - min_y + 1) * cell + top + 26
    colors = {
        "CLB": "#16877b", "BRAM": "#7951b0",
        "DSP": "#ad5a2a", "IOB": "#2474b4", "CLOCK": "#c58b25",
        "INTERCONNECT": "#6c788c", "PS7": "#2e3b4e",
        "OTHER_OR_UNKNOWN": "#945d92",
    }
    elements = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d">' % (width, height),
        '<rect width="100%%" height="100%%" fill="#fff"/>',
        '<text x="15" y="20" font-family="sans-serif" font-size="14" font-weight="bold">EBAZ-27: XC7Z010 tilegrid / expressed features</text>',
        '<text x="15" y="37" font-family="sans-serif" font-size="11">Gray = no decoded features (NOT free); color = features reported, NOT occupied sites</text>',
        '<text x="15" y="52" font-family="sans-serif" font-size="10">Factory bitstream read-only survey; partial database may leave unknown bits</text>',
    ]
    for r in positioned:
        x = left + (r["grid_x"] - min_x) * cell
        y = top + (max_y - r["grid_y"]) * cell
        if r["features_expressed"]:
            color = colors.get(r["category"], "#945d92")
        else:
            color = "#e6e9ee"
        label = escape("%s | %s | features=%d | FREE UNKNOWN" %
                       (r["tile"], r["tile_type"], r["features_expressed"]))
        elements.append('<rect x="%d" y="%d" width="%d" height="%d" fill="%s" stroke="#fff" stroke-width=".4"><title>%s</title></rect>' %
                        (x, y, cell, cell, color, label))
    elements.append("</svg>")
    path.write_text("\n".join(elements) + "\n", encoding="utf-8")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fasm", type=Path, required=True)
    p.add_argument("--tilegrid", type=Path, required=True)
    p.add_argument("--outdir", type=Path, required=True)
    p.add_argument("--expected-sha256", default=FACTORY_FASM_SHA256,
                   help="SHA256 of known factory.fasm; change only for a different verified input")
    args = p.parse_args()
    for path in (args.fasm, args.tilegrid):
        if not path.is_file():
            p.error("missing input: " + str(path))
    if not args.outdir.is_dir():
        p.error("output directory must already exist")
    report, rows = examine(args.fasm, args.tilegrid, args.expected_sha256)
    prefix = args.outdir / "ebaz27-tilegrid"
    (prefix.with_suffix(".json")).write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    save_csv(prefix.with_suffix(".csv"), rows)
    save_svg(prefix.with_suffix(".svg"), rows)
    print("EBAZ27 TILEGRID SURVEY")
    for key in ("fasm_lines", "feature_lines_parsed", "unknown_bit_annotations",
                "unclassified_noncomment_lines", "grid_tiles_total",
                "grid_tiles_with_expressed_features", "features_with_tile_not_in_grid"):
        print("%s: %s" % (key, report[key]))
    print("CATEGORY | GRID TILES | WITH FEATURES | FEATURE LINES")
    for name, x in report["class_counts"].items():
        print("%s | %d | %d | %d" % (
            name, x["all_tiles_in_grid"], x["tiles_with_expressed_features"],
            x["expressed_feature_lines"]))
    for suffix in (".json", ".csv", ".svg"):
        print("REPORT:", prefix.with_suffix(suffix))
    if report["features_with_tile_not_in_grid"] or report["unclassified_noncomment_lines"]:
        print("WARNING: unmatched FASM lines/tiles require investigation")
    print("EBAZ27_TILEGRID_SURVEY_PASS (NOT FREE-REGION PASS)")


if __name__ == "__main__":
    main()
