#!/usr/bin/env python3
"""EBAZ-27.11: validate factory INT PIP features against X-Ray tile metadata.

READ-ONLY forensic evidence. FASM records establish configured features; PIP
metadata gives source/destination wire orientation; tileconn.json gives only
fixed inter-tile wire adjacency. This is NOT a recovered netlist, timing model,
utilization estimate, or proof of a safe/free FPGA region.

Inputs: XC7Z010 tilegrid.json, tileconn.json, tile_type_INT_L/R.json,
and the privately held factory.fasm. Outputs should remain private.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re

EXPECTED_FASM_SHA256 = "f22e32fc1608a9cee8ce30757b7d8f2856b3a307492534b02aafa7b90738b66b"
FEATURE_RE = re.compile(r"^([A-Za-z0-9_]+_X[0-9]+Y[0-9]+)\.([^\s#]+)")
UNKNOWN_RE = re.compile(r'unknown_bit\s*=\s*"([^"]+)"')
PREFIX = "ebaz27-int-route-evidence"
KINDS = ("INT_L", "INT_R")
FIELDS = ("tile", "tile_type", "source_wire", "destination_wire", "pip_feature",
          "pip_metadata_status", "pip_pseudo", "pip_directional",
          "pip_pass_transistor", "grid_x", "grid_y", "source_is_tieoff",
          "interpretation")


def checked_json(path):
    if not path.is_file():
        raise ValueError("STOP: missing input " + str(path))
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_tile_type_path(device_dir, kind):
    """Resolve X-Ray's split layout: shared tile_type files live in zynq7/.

    tilegrid.json and tileconn.json are part-specific under zynq7/xc7z010/.
    Also accepts a legacy part-local tile_type file where present.
    """
    filename = "tile_type_" + kind + ".json"
    candidates = (device_dir.parent / filename, device_dir / filename)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise ValueError("STOP: tile metadata %s not found; searched %s" % (
        filename, ", ".join(str(p) for p in candidates)))


def pip_lookup(meta, expected_type):
    if meta.get("tile_type") != expected_type:
        raise ValueError("STOP: tile_type mismatch for " + expected_type)
    result = defaultdict(list)
    for name, item in meta.get("pips", {}).items():
        src = item.get("src_wire")
        dst = item.get("dst_wire")
        if src is not None and dst is not None:
            result[(dst, src)].append((name, item))
    if not result:
        raise ValueError("STOP: no PIP records for " + expected_type)
    return result


def fixed_neighbor_index(entries):
    """Both directions of a fixed (nondirectional) tileconn link."""
    idx = defaultdict(list)
    for c in entries:
        types = c["tile_types"]
        dx, dy = c["grid_deltas"]
        for a, b in c["wire_pairs"]:
            idx[(types[0], a)].append((dx, dy, types[1], b))
            idx[(types[1], b)].append((-dx, -dy, types[0], a))
    return idx


def analyze(fasm_path, device_dir, expected_sha256, output_dir):
    # Resolve metadata before the potentially large tilegrid/tileconn reads.
    metadata_paths = {
        kind: resolve_tile_type_path(device_dir, kind) for kind in KINDS
    }
    grid = checked_json(device_dir / "tilegrid.json")
    conns = checked_json(device_dir / "tileconn.json")
    if not isinstance(grid, dict) or not isinstance(conns, list):
        raise ValueError("STOP: invalid X-Ray grid/connection database")
    lookups = {
        kind: pip_lookup(checked_json(metadata_paths[kind]), kind)
        for kind in KINDS
    }
    actual_hash = hashlib.sha256(fasm_path.read_bytes()).hexdigest()
    if expected_sha256 and actual_hash != expected_sha256.lower():
        raise ValueError("STOP: FASM checksum mismatch: " + actual_hash)

    source_count = Counter()
    dest_count = Counter()
    status_count = Counter()
    per_type = defaultdict(Counter)
    samples = defaultdict(list)
    endpoints = set()
    unique_features = set()
    unknown_bits = 0
    fasm_lines = 0
    non_int_lines = 0
    int_non_pip = 0
    csv_path = output_dir / (PREFIX + ".csv")
    with fasm_path.open("r", encoding="utf-8", errors="replace") as data, \
            csv_path.open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=FIELDS)
        writer.writeheader()
        for line in data:
            fasm_lines += 1
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if s.startswith("{"):
                unknown_bits += len(UNKNOWN_RE.findall(s))
                continue
            match = FEATURE_RE.match(s)
            if not match:
                status_count["other_fasm_record"] += 1
                continue
            tile, suffix = match.groups()
            gridinfo = grid.get(tile)
            if gridinfo is None:
                status_count["feature_tile_missing_in_tilegrid"] += 1
                continue
            kind = gridinfo.get("type")
            if kind not in KINDS:
                non_int_lines += 1
                continue
            if s.find("=") != -1:
                suffix = suffix.split("=", 1)[0].strip()
            parts = suffix.split(".")
            if len(parts) != 2 or not all(parts):
                int_non_pip += 1
                if len(samples["int_not_pair"]) < 12:
                    samples["int_not_pair"].append(s[:160])
                continue
            dst, src = parts
            key = (tile, dst, src)
            if key in unique_features:
                status_count["duplicate_fasm_pip_feature"] += 1
                continue
            unique_features.add(key)
            meta_entries = lookups[kind].get((dst, src), [])
            if len(meta_entries) == 1:
                metadata_status = "EXACT_PIP_MATCH"
                pip = meta_entries[0][1]
                pseudo = str(pip.get("is_pseudo", "UNKNOWN"))
                directional = str(pip.get("is_directional", "UNKNOWN"))
                pass_transistor = str(pip.get("is_pass_transistor", "UNKNOWN"))
                status_count["exact_metadata_matches"] += 1
                status_count["pseudo_" + pseudo] += 1
                status_count["directional_" + directional] += 1
            elif len(meta_entries) > 1:
                metadata_status = "MULTIPLE_PIP_METADATA"
                pseudo = directional = pass_transistor = "AMBIGUOUS"
                status_count["ambiguous_metadata_matches"] += 1
                if len(samples["ambiguous"]) < 12:
                    samples["ambiguous"].append(s[:160])
            else:
                metadata_status = "NO_PIP_METADATA"
                pseudo = directional = pass_transistor = "UNVERIFIED"
                status_count["missing_metadata_matches"] += 1
                if len(samples["missing_pip_metadata"]) < 12:
                    samples["missing_pip_metadata"].append(s[:160])
            tieoff = src in ("GND_WIRE", "VCC_WIRE") or src.startswith(("GND_WIRE", "VCC_WIRE"))
            if tieoff:
                status_count["tieoff_source_pip_features"] += 1
            source_count[src] += 1
            dest_count[dst] += 1
            per_type[kind]["observed_pip_features"] += 1
            per_type[kind][metadata_status] += 1
            endpoints.add((tile, src))
            endpoints.add((tile, dst))
            if len(samples[kind]) < 10:
                samples[kind].append({
                    "feature": tile + "." + dst + "." + src,
                    "direction": src + " -> " + dst,
                    "metadata": metadata_status,
                })
            writer.writerow({
                "tile": tile, "tile_type": kind,
                "source_wire": src, "destination_wire": dst,
                "pip_feature": tile + "." + dst + "." + src,
                "pip_metadata_status": metadata_status,
                "pip_pseudo": pseudo, "pip_directional": directional,
                "pip_pass_transistor": pass_transistor,
                "grid_x": gridinfo["grid_x"], "grid_y": gridinfo["grid_y"],
                "source_is_tieoff": tieoff,
                "interpretation": "CONFIGURED_FEATURE_ONLY_NO_NETLIST",
            })

    if status_count["other_fasm_record"] or status_count["feature_tile_missing_in_tilegrid"]:
        raise ValueError("STOP: invalid unexpected FASM records; inspect local output")

    coord_to_tile = {(v["grid_x"], v["grid_y"]): key for key, v in grid.items()}
    adjacent = fixed_neighbor_index(conns)
    fixed_links = set()
    fixed_links_with_both_endpoints_in_int_features = set()
    fixed_links_to_other_tile_types = set()
    for tile, wire in endpoints:
        info = grid[tile]
        kind = info["type"]
        x, y = info["grid_x"], info["grid_y"]
        for dx, dy, dest_type, target_wire in adjacent.get((kind, wire), ()):
            target_tile = coord_to_tile.get((x + dx, y + dy))
            if target_tile is None or grid[target_tile]["type"] != dest_type:
                continue
            a, b = (tile, wire), (target_tile, target_wire)
            link = tuple(sorted((a, b)))
            fixed_links.add(link)
            if b in endpoints:
                fixed_links_with_both_endpoints_in_int_features.add(link)
            if dest_type not in KINDS:
                fixed_links_to_other_tile_types.add(link)
    report = {
        "status": "INT_PIP_METADATA_AND_FIXED_NEIGHBOR_EVIDENCE_ONLY",
        "factory_fasm_sha256": actual_hash,
        "tilegrid_sha256": hashlib.sha256((device_dir / "tilegrid.json").read_bytes()).hexdigest(),
        "tileconn_sha256": hashlib.sha256((device_dir / "tileconn.json").read_bytes()).hexdigest(),
        "pip_metadata_paths": {kind: str(p) for kind, p in metadata_paths.items()},
        "fasm_lines_total": fasm_lines,
        "non_int_feature_lines": non_int_lines,
        "int_feature_rows_not_dst_src": int_non_pip,
        "unknown_bit_annotations": unknown_bits,
        "observed_int_pip_feature_count": len(unique_features),
        "unique_int_wire_endpoints": len(endpoints),
        "fixed_tileconn_links_touching_int_endpoints": len(fixed_links),
        "fixed_tileconn_links_with_both_int_pip_endpoints": len(fixed_links_with_both_endpoints_in_int_features),
        "fixed_tileconn_links_to_other_tile_types": len(fixed_links_to_other_tile_types),
        "metadata_checks": dict(status_count),
        "per_int_type": {k: dict(v) for k, v in sorted(per_type.items())},
        "top_source_wire_names": source_count.most_common(20),
        "top_destination_wire_names": dest_count.most_common(20),
        "examples": dict(samples),
        "interpretation": [
            "In INT FASM feature TILE.DST.SRC, candidate connection is SRC -> DST.",
            "Matched tile PIP metadata validates the local wire pair and flags.",
            "tileconn is fixed, non-directional adjacency, not an enabled PIP.",
            "No connected graph or end-to-end netlist has been reconstructed.",
            "Pseudo/default/unrepresented connections and unknown bits limit completeness.",
            "Cannot identify Ethernet/AXI/ASIC blocks, route ownership or safe free regions.",
            "All derived data are forensic evidence, not commands for FPGA reconfiguration.",
        ],
    }
    report_path = output_dir / (PREFIX + ".json")
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report, csv_path, report_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fasm", type=Path, required=True)
    parser.add_argument("--device-db", type=Path, required=True,
                        help="Directory zynq7/xc7z010 containing tilegrid.json and tileconn.json")
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--expected-sha256", default=EXPECTED_FASM_SHA256)
    a = parser.parse_args()
    if not a.fasm.is_file() or not a.device_db.is_dir() or not a.outdir.is_dir():
        parser.error("FASM, device database and output directory must already exist")
    report, csv_path, json_path = analyze(a.fasm, a.device_db, a.expected_sha256, a.outdir)
    print("EBAZ27 INT PIP / TILECONN EVIDENCE")
    for kind, path in sorted(report["pip_metadata_paths"].items()):
        print("PIP META %s: %s" % (kind, path))
    for key in (
        "fasm_lines_total", "observed_int_pip_feature_count",
        "int_feature_rows_not_dst_src", "unknown_bit_annotations",
        "unique_int_wire_endpoints", "fixed_tileconn_links_touching_int_endpoints",
        "fixed_tileconn_links_with_both_int_pip_endpoints",
        "fixed_tileconn_links_to_other_tile_types",
    ):
        print("%s: %s" % (key, report[key]))
    print("PIP METADATA:")
    for k, v in sorted(report["metadata_checks"].items()):
        print("  %s: %s" % (k, v))
    print("PER TYPE:")
    for k, v in sorted(report["per_int_type"].items()):
        print("  %s: %s" % (k, v))
    print("SAMPLES:")
    for kind in KINDS:
        for item in report["examples"].get(kind, ())[:4]:
            print("  %s: %s | %s" % (
                kind, item["direction"], item["metadata"]))
    print("JSON:", json_path)
    print("CSV:", csv_path)
    if report["metadata_checks"].get("missing_metadata_matches", 0) or \
            report["int_feature_rows_not_dst_src"]:
        print("WARNING: metadata mismatches or non-PIP INT features need investigation")
        print("EBAZ27_INT_ROUTE_EVIDENCE_PARTIAL (NOT NETLIST)")
    else:
        print("EBAZ27_INT_ROUTE_EVIDENCE_PASS (NOT NETLIST)")


if __name__ == "__main__":
    main()
