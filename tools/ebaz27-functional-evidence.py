#!/usr/bin/env python3
"""EBAZ-27.9: conservative FPGA primitive-configuration evidence inventory.

Inputs are private factory.fasm + the Project X-Ray XC7Z010 tilegrid.
Never interprets an encoded feature as an occupied cell or safely free region.
No NAND / FPGA access. Results exclude LUT INIT contents and full FASM lines.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re

EXPECTED_SHA256 = "f22e32fc1608a9cee8ce30757b7d8f2856b3a307492534b02aafa7b90738b66b"
FEATURE = re.compile(r"^([A-Za-z0-9_]+_X\d+Y\d+)\.([^\s#]+)")
UNKNOWN = re.compile(r'unknown_bit\s*=\s*"([^"]+)"')
LUT_INIT = re.compile(r"^(SLICE[LM]_X[01])\.([ABCD])LUT\.INIT(?:\[|$)")
FF_CFG = re.compile(r"^(SLICE[LM]_X[01])\.([ABCD])FF\.")
FF_MUX = re.compile(r"^(SLICE[LM]_X[01])\.([ABCD])FFMUX\.")
BRAM_DATA = re.compile(r"(?:^|\.)(?:INIT|INITP)_[0-9A-F]+(?:\[|$)")
GLOBAL_CLK = re.compile(r"BUFGCTRL\.(BUFGCTRL_X\d+Y\d+)\.IN_USE$")
MMCM = re.compile(r"(?:^|\.)MMCME2_ADV\.")
OUTPUT_DIR = "ebaz27-functional-evidence"


def classify(kind, suffix):
    """Evidence markers, NOT primitive utilization."""
    flags = []
    if kind.startswith("CLBL"):
        if LUT_INIT.search(suffix):
            flags.append("lut_init")
        if FF_CFG.search(suffix):
            flags.append("ff_attribute")
        if FF_MUX.search(suffix):
            flags.append("ffmux")
        if "PRECYINIT" in suffix or "CARRY4" in suffix:
            flags.append("carry_setting")
    if kind.startswith(("BRAM_L", "BRAM_R")):
        if BRAM_DATA.search(suffix):
            flags.append("bram_init")
        else:
            flags.append("bram_configuration")
    if kind.startswith(("INT_L", "INT_R")):
        flags.append("interconnect_feature")
    if kind.startswith(("RIOB", "RIOI", "LIOB", "LIOI")):
        flags.append("io_configuration")
    if "BUFGCTRL" in suffix and suffix.endswith(".IN_USE"):
        flags.append("bufg_explicit_in_use")
    if MMCM.search(suffix):
        flags.append("mmcm_configuration")
    return flags


def process(fasm_file, grid_file, expected_sha256):
    tilegrid = json.loads(grid_file.read_text(encoding="utf-8"))
    if not isinstance(tilegrid, dict) or len(tilegrid) < 1000:
        raise ValueError("STOP: tilegrid missing or unexpectedly small")
    tile_data = defaultdict(Counter)
    global_counters = Counter()
    per_type = defaultdict(Counter)
    lut_labels = set()
    ff_labels = set()
    ffmux_labels = set()
    bufg_labels = set()
    unknown_frames = Counter()
    other_examples = []
    feature_example_by_type = defaultdict(list)
    hashobj = hashlib.sha256()
    with fasm_file.open("rb") as f:
        for raw in f:
            hashobj.update(raw)
            text = raw.decode("utf-8", "replace").strip()
            if not text or text.startswith("#"):
                continue
            # Strip optional assigned binary INIT value. Never export bit patterns.
            key = text.split("=", 1)[0].strip() if not text.startswith("{") else text
            match = FEATURE.match(key)
            if match:
                tile, suffix = match.groups()
                meta = tilegrid.get(tile)
                if meta is None:
                    raise ValueError("STOP: feature tile not present in tilegrid: " + tile)
                kind = meta.get("type", "UNKNOWN")
                global_counters["fasm_features"] += 1
                per_type[kind]["feature_lines"] += 1
                tile_data[tile]["feature_lines"] += 1
                if len(feature_example_by_type[kind]) < 4:
                    feature_example_by_type[kind].append(suffix)
                flags = classify(kind, suffix)
                for flag in flags:
                    global_counters[flag + "_lines"] += 1
                    per_type[kind][flag + "_lines"] += 1
                    tile_data[tile][flag + "_lines"] += 1
                m = LUT_INIT.search(suffix)
                if m and kind.startswith("CLBL"):
                    lut_labels.add((tile, m.group(1), m.group(2)))
                m = FF_CFG.search(suffix)
                if m and kind.startswith("CLBL"):
                    ff_labels.add((tile, m.group(1), m.group(2)))
                m = FF_MUX.search(suffix)
                if m and kind.startswith("CLBL"):
                    ffmux_labels.add((tile, m.group(1), m.group(2)))
                m = GLOBAL_CLK.search(suffix)
                if m:
                    bufg_labels.add((tile, m.group(1)))
                continue
            bits = UNKNOWN.findall(text)
            if bits:
                global_counters["unknown_bit_annotations"] += len(bits)
                for bit in bits:
                    unknown_frames[bit.split("_")[0].lower()] += 1
            else:
                global_counters["unclassified_noncomment_lines"] += 1
                if len(other_examples) < 12:
                    other_examples.append(text[:180])
    fasm_hash = hashobj.hexdigest()
    if expected_sha256 and fasm_hash != expected_sha256.lower():
        raise ValueError("STOP: factory.fasm checksum mismatch: " + fasm_hash)
    if global_counters["unclassified_noncomment_lines"]:
        raise ValueError("STOP: unexpected FASM records: " + repr(other_examples))
    global_counters["explicit_lut_init_labels"] = len(lut_labels)
    global_counters["ff_with_attribute_labels"] = len(ff_labels)
    global_counters["ffmux_labels"] = len(ffmux_labels)
    global_counters["bufg_explicit_in_use_labels"] = len(bufg_labels)
    global_counters["unknown_frames"] = len(unknown_frames)

    rows = []
    for tile, counts in sorted(tile_data.items()):
        meta = tilegrid[tile]
        row = {
            "tile": tile, "tile_type": meta.get("type"),
            "grid_x": meta.get("grid_x"), "grid_y": meta.get("grid_y"),
            "available_site_definitions": len(meta.get("sites", {}) or {}),
            "feature_lines": counts["feature_lines"],
        }
        for flag in ("lut_init", "ff_attribute", "ffmux", "carry_setting",
                     "bram_init", "bram_configuration", "interconnect_feature",
                     "io_configuration", "bufg_explicit_in_use", "mmcm_configuration"):
            row[flag + "_lines"] = counts[flag + "_lines"]
        row["site_utilization"] = "UNKNOWN_NOT_PROVEN"
        rows.append(row)

    report = {
        "status": "FEATURE_EVIDENCE_ONLY_NOT_UTILIZATION",
        "input": {
            "fasm_sha256": fasm_hash,
            "tilegrid_sha256": hashlib.sha256(grid_file.read_bytes()).hexdigest(),
            "fasm_name": fasm_file.name,
        },
        "counters": dict(global_counters),
        "by_tile_type": {
            typ: {
                "feature_counts": dict(counts),
                "sample_feature_names_not_values": feature_example_by_type[typ],
            }
            for typ, counts in sorted(per_type.items())
        },
        "bufg_explicit_in_use_local_labels": [
            {"tile": t, "local_bufg_site": s} for t, s in sorted(bufg_labels)
        ],
        "unknown_frames_by_address": dict(sorted(unknown_frames.items())),
        "caveats": [
            "LUT INIT presence does NOT prove an instantiated or connected LUT.",
            "FF attribute and FFMUX settings do NOT prove an occupied or active FF.",
            "BRAM configuration and INIT do NOT measure allocated or filled BRAM.",
            "BUFG IN_USE feature is stronger evidence of enabling but does NOT prove route dependencies.",
            "Feature names must be tied to tilegrid sites and known routes before functional attribution.",
            "Unknown bits remain unresolved; no SAFE_FREE site or region may be inferred.",
            "This report does not extract netlist, AXI connections, pad mapping, timing or DFX.",
        ],
    }
    return report, rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fasm", required=True, type=Path)
    p.add_argument("--tilegrid", required=True, type=Path)
    p.add_argument("--outdir", required=True, type=Path)
    p.add_argument("--expected-sha256", default=EXPECTED_SHA256)
    a = p.parse_args()
    for path in (a.fasm, a.tilegrid):
        if not path.is_file():
            p.error("input not found: " + str(path))
    if not a.outdir.is_dir():
        p.error("outdir must already exist: " + str(a.outdir))
    report, rows = process(a.fasm, a.tilegrid, a.expected_sha256)
    jp = a.outdir / (OUTPUT_DIR + ".json")
    cp = a.outdir / (OUTPUT_DIR + ".csv")
    jp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if rows:
        with cp.open("w", newline="", encoding="utf-8") as f:
            wr = csv.DictWriter(f, fieldnames=list(rows[0]))
            wr.writeheader()
            wr.writerows(rows)
    print("EBAZ27 FUNCTIONAL FEATURE EVIDENCE")
    print("FASM SHA256:", report["input"]["fasm_sha256"])
    for k, v in sorted(report["counters"].items()):
        print("%s: %s" % (k, v))
    print("BUFCTRL .IN_USE LOCAL LABELS:", len(report["bufg_explicit_in_use_local_labels"]))
    for obj in report["bufg_explicit_in_use_local_labels"][:16]:
        print(" ", obj["tile"], obj["local_bufg_site"])
    print("JSON:", jp)
    print("CSV:", cp)
    print("EBAZ27_FUNCTIONAL_EVIDENCE_PASS (NOT UTILIZATION PASS)")


if __name__ == "__main__":
    main()
