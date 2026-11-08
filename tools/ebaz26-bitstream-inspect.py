#!/usr/bin/env python3
"""EBAZ-26: read-only triage of a Xilinx 7-series FPGA NAND partition/bitstream.

No changes to source image, no device access, and no programming commands.
Python 3 standard library only. Usage:
    python tools/ebaz26-bitstream-inspect.py mtd5_factory_20261108.bin
    python tools/ebaz26-bitstream-inspect.py mtd5_factory_20261108.bin --json report.json
"""
import argparse
import hashlib
import json
from pathlib import Path

SYNCS = [(b"\xaa\x99\x55\x66", "big"), (b"\x66\x55\x99\xaa", "little")]
REGS = {1: "FAR", 2: "FDRI", 4: "CMD", 5: "CTL0", 6: "MASK",
        7: "STAT", 9: "COR0", 12: "IDCODE", 14: "COR1",
        16: "WBSTAR", 17: "TIMER", 22: "BOOTSTS", 24: "CTL1"}
IDCODES = {0x03722093: "XC7Z010", 0x03727093: "XC7Z020"}


def locate(data, needle, cap=32):
    offsets = []
    pos = 0
    while len(offsets) < cap:
        pos = data.find(needle, pos)
        if pos < 0:
            break
        offsets.append(pos)
        pos += 1
    return offsets


def packet_info(data, sync_offset, byteorder):
    p = sync_offset + 4
    n = len(data)
    idcodes = []
    regs_seen = {}
    count_fdri = 0
    cmd_desync = False
    packet_count = 0
    reasons = []
    max_packets = 50000
    while p + 4 <= n and packet_count < max_packets:
        word = int.from_bytes(data[p:p + 4], byteorder)
        p += 4
        packet_count += 1
        kind = (word >> 29) & 0x7
        opcode = (word >> 27) & 0x3
        if kind == 1:
            reg = (word >> 13) & 0x3fff
            count = word & 0x7ff
            if opcode == 3 or p + count * 4 > n:
                reasons.append("invalid type-1 packet")
                break
            if opcode == 2:
                if reg == 2:
                    count_fdri += count
                if reg in REGS and count and count <= 32:
                    values = [int.from_bytes(data[p + i * 4:p + (i + 1) * 4], byteorder)
                              for i in range(count)]
                    regs_seen[REGS[reg]] = [f"0x{x:08x}" for x in values]
                    if reg == 12:
                        idcodes.extend(values)
                    if reg == 4 and 13 in values:
                        cmd_desync = True
            p += count * 4
            if cmd_desync:
                reasons.append("CMD DESYNC reached")
                break
        elif kind == 2:
            count = word & 0x7ffffff
            if opcode == 3 or p + count * 4 > n:
                reasons.append("invalid type-2 packet")
                break
            if opcode == 2:
                count_fdri += count
            p += count * 4
        else:
            reasons.append(f"unknown packet type {kind} at offset 0x{p-4:x}")
            break
    if packet_count >= max_packets:
        reasons.append("packet limit reached")
    return {
        "sync_offset": sync_offset,
        "byteorder": byteorder,
        "idcodes": [f"0x{x:08x}" for x in idcodes],
        "devices": [IDCODES.get(x, "unknown") for x in idcodes],
        "fdri_words_written": count_fdri,
        "desync_seen": cmd_desync,
        "packet_count": packet_count,
        "parse_end_offset": p,
        "selected_registers_last_values": regs_seen,
        "notes": reasons,
    }


def bit_header(data, sync_offset):
    """Detect optional standard Xilinx .bit metadata directly before sync."""
    anchor = b"\x00\x09\x0f\xf0\x0f\xf0\x0f\xf0\x0f\xf0"
    a = data.rfind(anchor, max(0, sync_offset - 4096), sync_offset)
    if a < 0:
        return None
    try:
        p = a
        n = int.from_bytes(data[p:p + 2], "big")
        p += 2 + n
        if data[p:p + 2] != b"\x00\x01":
            return None
        p += 2
        fields = {}
        payload_offset = None
        payload_length = None
        for _ in range(5):
            tag = data[p:p + 1]
            p += 1
            if tag == b"e":
                payload_length = int.from_bytes(data[p:p + 4], "big")
                payload_offset = p + 4
                p += 4
                break
            if tag not in (b"a", b"b", b"c", b"d"):
                return None
            ln = int.from_bytes(data[p:p + 2], "big")
            p += 2
            fields[tag.decode()] = data[p:p + ln].rstrip(b"\x00").decode("latin1", "replace")
            p += ln
        if payload_offset is None or not (payload_offset <= sync_offset <
                                           payload_offset + payload_length <= len(data)):
            return None
        return {"header_offset": a, "payload_offset": payload_offset,
                "payload_length": payload_length, "fields": fields}
    except (IndexError, ValueError):
        return None


def examine(file):
    data = file.read_bytes()
    h = hashlib.sha256(data).hexdigest()
    end_non_ff = len(data.rstrip(b"\xff"))
    end_non_00 = len(data.rstrip(b"\x00"))
    candidates = []
    for needle, byteorder in SYNCS:
        for ofs in locate(data, needle):
            item = packet_info(data, ofs, byteorder)
            item["bit_header"] = bit_header(data, ofs)
            candidates.append(item)
    candidates.sort(key=lambda x: x["sync_offset"])
    return {
        "file": file.name,
        "size_bytes": len(data),
        "sha256": h,
        "first_32_bytes_hex": data[:32].hex(" "),
        "last_non_ff_end_offset": end_non_ff,
        "last_non_00_end_offset": end_non_00,
        "sync_candidates": candidates,
        "caveat": ("This is a packet/header reconnaissance only, not a utilization estimate. "
                   "A sync or IDCODE does not prove unencrypted payload or valid full image. "
                   "Project X-Ray may decode some configuration features, but does not "
                   "automatically recover original RTL or grant safe use of free fabric."),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="local read-only NAND MTD5 dump or .bit")
    parser.add_argument("--json", type=Path, help="optional JSON report output")
    args = parser.parse_args()
    if not args.image.is_file():
        parser.error(f"not a file: {args.image}")
    report = examine(args.image)
    print(f"INPUT    {report['file']}")
    print(f"BYTES    {report['size_bytes']}")
    print(f"SHA256   {report['sha256']}")
    print(f"HEAD32   {report['first_32_bytes_hex']}")
    print(f"NON-FF END {report['last_non_ff_end_offset']} / NON-00 END {report['last_non_00_end_offset']}")
    print(f"SYNC CANDIDATES: {len(report['sync_candidates'])}")
    for cand in report["sync_candidates"]:
        print(f"  offset=0x{cand['sync_offset']:x} order={cand['byteorder']} "
              f"IDCODE={','.join(cand['idcodes']) or '?'} "
              f"device={','.join(cand['devices']) or '?'} "
              f"FDRI_words={cand['fdri_words_written']} "
              f"DESYNC={cand['desync_seen']} packets={cand['packet_count']}")
        if cand["bit_header"]:
            print(f"    .bit metadata: {cand['bit_header']}")
        if cand["notes"]:
            print(f"    parser stop: {cand['notes'][0]}")
    print("NOTE: No LUT/BRAM/DSP utilization is inferred by this tool.")
    if args.json:
        args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")
        print(f"REPORT   {args.json}")


if __name__ == "__main__":
    main()
