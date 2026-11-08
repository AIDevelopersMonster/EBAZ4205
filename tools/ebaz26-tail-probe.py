#!/usr/bin/env python3
"""EBAZ-26: read-only forensic probe of the non-FF tail inside factory MTD5.

Operates only on a local copied MTD5 image. Does not access NAND/FPGA.
Prints a small set of byte samples, histogram and candidate signatures.
Does NOT claim to identify a second image without supporting evidence.

Usage:
  python tools/ebaz26-tail-probe.py C:/GitHub/EBAZ4205-Backup/mtd5_factory_20261108.bin
"""
import argparse
from collections import Counter
import hashlib
import math
from pathlib import Path

EXPECTED_SHA256 = "c0e787f2caf0b4c9287680ba2737b0778404e9af0222262634a14dad69ea3884"
BEGIN = 0x200000
END = 0x2D0000
BLOCK = 0x10000
MAGIC = (
    (b"\xaa\x99\x55\x66", "Xilinx 7-series SYNC (BE)"),
    (b"\x66\x55\x99\xaa", "Xilinx 7-series SYNC (LE)"),
    (b"\x7fELF", "ELF"),
    (b"\x1f\x8b\x08", "gzip"),
    (b"\xfd7zXZ\x00", "XZ"),
    (b"PK\x03\x04", "ZIP"),
    (b"\x27\x05\x19\x56", "U-Boot uImage"),
    (b"\xd0\x0d\xfe\xed", "FDT/FIT"),
    (b"UBI#", "UBI EC"),
    (b"UBI!", "UBI VID"),
    (b"\x85\x19", "JFFS2 little-endian magic (weak; verify)"),
)


def hexdump(buf, start=0, maxlen=64):
    out = []
    for off in range(0, min(maxlen, len(buf)), 16):
        b = buf[off:off+16]
        ascii_repr = "".join(chr(x) if 32 <= x < 127 else "." for x in b)
        out.append("%08X  %-47s  %s" % (start + off, b.hex(" "), ascii_repr))
    return "\n".join(out)


def entropy(counter, length):
    return -sum((n/length)*math.log2(n/length) for n in counter.values() if n)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("image", type=Path)
    args = ap.parse_args()
    data = args.image.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    if len(data) != 8388608 or sha != EXPECTED_SHA256:
        ap.error("STOP: factory image size or SHA256 mismatch")
    tail = data[BEGIN:END]
    counts = Counter(tail)
    print("SOURCE:", args.image.name)
    print("SIZE:", len(data), "SHA256:", sha)
    print("SECOND REGION: 0x%X..0x%X (%d bytes)" % (BEGIN, END, len(tail)))
    print("BYTE COUNTS: 0x00=%d 0xFF=%d OTHER=%d" % (
        counts.get(0, 0), counts.get(255, 0),
        len(tail) - counts.get(0, 0) - counts.get(255, 0)))
    print("DISTINCT BYTES:", len(counts))
    print("SHANNON ENTROPY (whole region, bits/byte): %.4f" % entropy(counts, len(tail)))
    print("TOP 16 VALUES:", " ".join("%02X:%d" % p for p in counts.most_common(16)))
    print("\nBOUNDARY SAMPLES (first 64 bytes):")
    for ofs in [0x1FFFC0, BEGIN, BEGIN+BLOCK, BEGIN+2*BLOCK, END-64, END]:
        print("\n  at 0x%X:" % ofs)
        print(hexdump(data[ofs:ofs+64], start=ofs))
    print("\nMAGIC CANDIDATES IN 0x200000..0x2D0000 (first 8 per type):")
    found = False
    for magic, name in MAGIC:
        hits = []
        start = 0
        while len(hits) < 8:
            pos = tail.find(magic, start)
            if pos == -1:
                break
            hits.append(BEGIN + pos)
            start = pos + 1
        if hits:
            found = True
            print(" ", name, ":", " ".join("0x%X" % x for x in hits),
                  "[weak signature]" if len(magic) <= 2 else "")
    if not found:
        print("  None of tested signatures; data type unknown.")
    print("\nPER-64KiB PROFILE:")
    for ofs in range(BEGIN, END, BLOCK):
        c = Counter(data[ofs:ofs+BLOCK])
        print("  0x%06X: 00=%5d FF=%5d other=%5d entropy=%.3f" % (
            ofs, c.get(0, 0), c.get(255, 0),
            BLOCK - c.get(0, 0) - c.get(255, 0), entropy(c, BLOCK)))
    print("\nIMPORTANT: This is byte-level triage, not decryption, HDL recovery or FPGA utilization.")
    print("Do not publish the binary NAND image or extracted factory .bit.")


if __name__ == "__main__":
    main()
