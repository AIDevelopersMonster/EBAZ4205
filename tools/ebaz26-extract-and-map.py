#!/usr/bin/env python3
"""EBAZ-26 stage 2: extract an exact .bit from a verified NAND MTD5 backup.

Input is never modified. Output .bit and JSON remain local; do NOT commit them.
Requires only Python 3 standard library and the stage-1 JSON report.

Usage:
  python tools/ebaz26-extract-and-map.py <local-mtd5-image> --analysis <stage1-json>
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

EXPECTED_SHA256 = "c0e787f2caf0b4c9287680ba2737b0778404e9af0222262634a14dad69ea3884"
BIT_MAGIC = bytes.fromhex("00 09 0f f0 0f f0 0f f0 0f f0")
SYNC = bytes.fromhex("aa 99 55 66")
BLOCK = 65536


def sha256(buf):
    return hashlib.sha256(buf).hexdigest()


def bucket(data, start, end):
    buf = data[start:end]
    c = Counter(buf)
    return {
        "start": start, "end": end, "bytes": end - start,
        "zero": c.get(0, 0), "ff": c.get(255, 0),
        "other": len(buf) - c.get(0, 0) - c.get(255, 0),
        "distinct_byte_values": len(c),
        "sha256": sha256(buf),
        "first_16_hex": buf[:16].hex(" "),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("image", type=Path)
    p.add_argument("--analysis", type=Path, required=True,
                   help="JSON created by ebaz26-bitstream-inspect.py")
    p.add_argument("--outdir", type=Path,
                   help="local output folder; defaults to the image folder")
    args = p.parse_args()

    data = args.image.read_bytes()
    report = json.loads(args.analysis.read_text(encoding="utf-8"))
    digest = sha256(data)

    if digest != EXPECTED_SHA256 or digest != report["sha256"]:
        p.error("STOP: unexpected SHA256; do not extract from an unverified image")
    if len(data) != 8388608 or report["size_bytes"] != len(data):
        p.error("STOP: unexpected size (expected 8 MiB)")
    if not data.startswith(BIT_MAGIC):
        p.error("STOP: Xilinx .bit header magic absent at offset zero")

    matches = [c for c in report["sync_candidates"]
               if c.get("desync_seen") and "0x03722093" in c.get("idcodes", [])
               and c.get("bit_header")]
    if len(matches) != 1:
        p.error("STOP: expected exactly one XC7Z010 candidate with header and DESYNC")
    m = matches[0]
    h = m["bit_header"]
    start = int(h["header_offset"])
    payload = int(h["payload_offset"])
    length = int(h["payload_length"])
    sync = int(m["sync_offset"])
    end = payload + length
    if not (start == 0 and 0 < payload < sync < end <= len(data)):
        p.error("STOP: metadata offsets inconsistent")
    if data[sync:sync + 4] != SYNC:
        p.error("STOP: sync bytes mismatch")
    if (payload, length, sync) != (104, 2083740, 152):
        p.error("STOP: offsets unexpectedly different from documented EBAZ-26")
    if h["fields"].get("a") != "top_ctrl;UserID=0XFFFFFFFF;Version=2016.4":
        p.error("STOP: unexpected Xilinx design metadata")

    outdir = args.outdir or args.image.parent
    outdir.mkdir(parents=True, exist_ok=True)
    bitpath = outdir / "ebaz26_factory_top_ctrl_2017-10-17.bit"
    bit_bytes = data[start:end]
    if bitpath.exists():
        if sha256(bitpath.read_bytes()) != sha256(bit_bytes):
            p.error("STOP: output .bit already exists with different bytes")
        print("BIT ALREADY PRESENT (hash verified):", bitpath)
    else:
        bitpath.write_bytes(bit_bytes)
        print("BIT CREATED:", bitpath)

    active_end = len(data.rstrip(b"\xff"))
    tail_start = end
    tail = bucket(data, tail_start, len(data))
    regions = []
    pos = tail_start
    while pos < active_end:
        region_end = min(((pos // BLOCK) + 1) * BLOCK, active_end)
        regions.append(bucket(data, pos, region_end))
        pos = region_end

    result = {
        "source": args.image.name,
        "source_size": len(data), "source_sha256": digest,
        "design": h["fields"],
        "idcode": "0x03722093",
        "header_offset": start,
        "payload_offset": payload,
        "sync_offset": sync,
        "payload_length": length,
        "bit_end_offset": end,
        "extracted_bit": bitpath.name,
        "extracted_bit_size": len(bit_bytes),
        "extracted_bit_sha256": sha256(bit_bytes),
        "last_non_ff_end_offset": active_end,
        "tail": tail,
        "tail_regions_up_to_last_non_ff": regions,
        "caveat": "Not a LUT/BRAM/DSP utilization report. Input remains unmodified. Do not publish factory .bit without permission.",
    }
    jsonpath = outdir / "ebaz26_factory_layout.json"
    jsonpath.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print("BIT BYTES:", len(bit_bytes))
    print("BIT SHA256:", sha256(bit_bytes))
    print("BIT END OFFSET:", end)
    print("LAST NON-FF END:", active_end)
    print("TRAIL BYTES:", len(data) - end, "NON-FF-UP-TO:", max(0, active_end - end))
    print("TRAIL COUNTS: 00=", tail["zero"],
          "FF=", tail["ff"], "OTHER=", tail["other"])
    print("TRAIL REGIONS:")
    for x in regions:
        print("  0x%06X-0x%06X: 00=%d FF=%d OTHER=%d" %
              (x["start"], x["end"], x["zero"], x["ff"], x["other"]))
    print("REPORT CREATED:", jsonpath)
    print("NOTE: No flash or FPGA device was accessed; the factory image is unchanged.")


if __name__ == "__main__":
    main()
