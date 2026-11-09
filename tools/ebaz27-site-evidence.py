#!/usr/bin/env python3
"""Read-only EBAZ-27 site inventory and expressed FASM-feature family survey.

Tilegrid sites are *available physical site definitions*, not implemented logic.
A tile that appears in FASM is not necessarily occupied by a design cell.
Do not infer utilization, free routes, pin function or partial reconfiguration.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re

FACTORY_FASM_SHA256 = "f22e32fc1608a9cee8ce30757b7d8f2856b3a307492534b02aafa7b90738b66b"
FEATURE_RE = re.compile(r"^([A-Za-z0-9_]+_X\d+Y\d+)\.([^\s#]+)")
UNKNOWN_RE = re.compile(r'unknown_bit\s*=\s*"([^"]+)"')


def survey(grid_file, fasm_file, expected_sha256):
    grid = json.loads(grid_file.read_text(encoding="utf-8"))
    if not isinstance(grid, dict) or not grid:
        raise ValueError("STOP: tilegrid is empty or malformed")
    feature_count_by_tile = Counter()
    feature_families = defaultdict(Counter)
    examples_by_type = defaultdict(list)
    unknown_annotations = 0
    unmatched = Counter()
    h = hashlib.sha256()
    with fasm_file.open("rb") as fd:
        for raw in fd:
            h.update(raw)
            line = raw.decode("utf-8", "replace").strip()
            if not line or line.startswith("#"):
                continue
            m = FEATURE_RE.match(line)
            if m:
                tile, feature = m.groups()
                if tile not in grid:
                    unmatched["feature_tile_not_in_grid"] += 1
                    continue
                tile_type = grid[tile].get("type", "UNKNOWN")
                feature_count_by_tile[tile] += 1
                feature_families[tile_type][".".join(feature.split(".")[:2])] += 1
                if len(examples_by_type[tile_type]) < 3:
                    examples_by_type[tile_type].append(line[:200])
            elif UNKNOWN_RE.search(line):
                unknown_annotations += len(UNKNOWN_RE.findall(line))
            else:
                unmatched["nonfeature_unparsed"] += 1
    actual_hash = h.hexdigest()
    if expected_sha256 and actual_hash != expected_sha256.lower():
        raise ValueError("STOP: factory.fasm SHA256 changed: " + actual_hash)
    if unmatched:
        raise ValueError("STOP: unexpected unparsed data: " + str(unmatched))

    site_type_count = Counter()
    site_type_tiles_with_fasm = Counter()
    tile_type_count = Counter()
    tile_type_with_fasm = Counter()
    tile_type_feature_lines = Counter()
    site_rows = []
    for tile, meta in grid.items():
        tile_type = meta.get("type", "UNKNOWN")
        tile_type_count[tile_type] += 1
        count = feature_count_by_tile[tile]
        if count:
            tile_type_with_fasm[tile_type] += 1
            tile_type_feature_lines[tile_type] += count
        sites = meta.get("sites", {}) or {}
        if not isinstance(sites, dict):
            raise ValueError("STOP: unexpected site dictionary for " + tile)
        for site, site_type in sorted(sites.items()):
            site_type_count[site_type] += 1
            if count:
                site_type_tiles_with_fasm[site_type] += 1
            site_rows.append({
                "tile": tile, "tile_type": tile_type,
                "site": site, "site_type": site_type,
                "grid_x": meta.get("grid_x"), "grid_y": meta.get("grid_y"),
                "tile_has_fasm_features": bool(count),
                "tile_fasm_feature_lines": count,
                "site_utilization": "UNKNOWN",
            })

    site_types = {
        typ: {"site_entries": count,
              "site_entries_in_tiles_with_fasm": site_type_tiles_with_fasm[typ]}
        for typ, count in sorted(site_type_count.items())
    }
    tile_types = {
        typ: {"total_tiles": count,
              "tiles_with_fasm": tile_type_with_fasm[typ],
              "feature_lines": tile_type_feature_lines[typ],
              "top_feature_prefixes": feature_families[typ].most_common(8),
              "sample_features": examples_by_type[typ]}
        for typ, count in sorted(tile_type_count.items())
    }
    report = {
        "status": "SITE_DEFINITION_AND_FASM_FAMILY_SURVEY_ONLY",
        "fasm_sha256": actual_hash,
        "tilegrid_sha256": hashlib.sha256(grid_file.read_bytes()).hexdigest(),
        "total_tiles": len(grid), "total_site_entries": len(site_rows),
        "total_fasm_feature_lines": sum(feature_count_by_tile.values()),
        "unknown_bit_annotations": unknown_annotations,
        "site_types": site_types, "tile_types": tile_types,
        "restrictions": [
            "Site entries describe available architecture, not instantiated cells.",
            "Each RAMB36 and its RAMB18 sub-sites may overlap in physical capacity; do not add their counts.",
            "Tile FASM features do not establish site occupancy, LUT/FF usage or PIP ownership.",
            "No-encountered FASM features do not establish DSP/BRAM free status.",
            "No Ethernet, AXI, clock, IOB, or fan function is attributed by this report.",
            "Original bitstream is never altered.",
        ],
    }
    return report, site_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fasm", type=Path, required=True)
    parser.add_argument("--tilegrid", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--expected-sha256", default=FACTORY_FASM_SHA256)
    a = parser.parse_args()
    for f in (a.fasm, a.tilegrid):
        if not f.is_file():
            parser.error("missing input: " + str(f))
    if not a.outdir.is_dir():
        parser.error("output directory must exist: " + str(a.outdir))
    report, rows = survey(a.tilegrid, a.fasm, a.expected_sha256)
    json_out = a.outdir / "ebaz27-site-evidence.json"
    csv_out = a.outdir / "ebaz27-site-evidence.csv"
    json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with csv_out.open("w", newline="", encoding="utf-8") as fd:
        fields = ["tile", "tile_type", "site", "site_type", "grid_x", "grid_y",
                  "tile_has_fasm_features", "tile_fasm_feature_lines", "site_utilization"]
        writer = csv.DictWriter(fd, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print("EBAZ27 SITE DEFINITION / FASM FAMILIES")
    print("physical tiles:", report["total_tiles"])
    print("site entries (NOT occupied cells):", report["total_site_entries"])
    print("FASM feature lines:", report["total_fasm_feature_lines"])
    print("unknown bit annotations:", report["unknown_bit_annotations"])
    print("SITE TYPE | TOTAL SITES | SITES IN TILES WITH FASM")
    for typ, values in report["site_types"].items():
        print("%s | %d | %d" % (typ, values["site_entries"],
                                values["site_entries_in_tiles_with_fasm"]))
    print("KEY TILE TYPES | TILES | WITH FASM | FEATURE LINES")
    for typ in ("CLBLL_L", "CLBLL_R", "CLBLM_L", "CLBLM_R", "BRAM_L", "BRAM_R",
                "DSP_L", "DSP_R", "INT_L", "INT_R", "RIOB33", "RIOI3"):
        if typ in report["tile_types"]:
            x = report["tile_types"][typ]
            print("%s | %d | %d | %d" % (typ, x["total_tiles"],
                                         x["tiles_with_fasm"], x["feature_lines"]))
    print("REPORT:", json_out)
    print("REPORT:", csv_out)
    print("EBAZ27_SITE_EVIDENCE_PASS (NOT UTILIZATION PASS)")


if __name__ == "__main__":
    main()
