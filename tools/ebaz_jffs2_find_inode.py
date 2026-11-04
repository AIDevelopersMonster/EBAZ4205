#!/usr/bin/env python3
r"""EBAZ4205: read-only JFFS2 inode and directory-record investigation.

Usage in Windows PowerShell:
    py -3 .\ebaz_jffs2_find_inode.py "$env:USERPROFILE\EBAZ4205_NAND_BACKUP\mtd6_allrootfs.bin" 981

Never opens /dev/mtd*, never writes to image or NAND. Python stdlib only.
"""

import argparse
from collections import defaultdict
from pathlib import Path
import struct
import sys
import zlib

MAGIC_INODE = b"\x85\x19\x02\xe0"
MAGIC_DIRENT = b"\x85\x19\x01\xe0"
KNOWN_NODE_OFFSET = 0x019DB640
EXPECTED_IMAGE_SIZE = 64 * 1024 * 1024


def jffs2_crc(data):
    """Matches Linux crc32(0,...), NOT zlib.crc32(data,0)."""
    return (zlib.crc32(data, 0xFFFFFFFF) ^ 0xFFFFFFFF) & 0xFFFFFFFF


def u32(buf, offset):
    return struct.unpack_from("<I", buf, offset)[0]


def crc_result(expected, actual):
    return "PASS" if expected == actual else "FAIL"


def inspect_inode_at(image, at, wanted):
    print("\n== JFFS2 RAW INODE AT 0x%08X ==" % at)
    if at + 68 > len(image):
        print("Node offset is beyond image length.")
        return
    if image[at:at + 4] != MAGIC_INODE:
        print("No valid little-endian JFFS2 raw-inode magic at this offset.")
        return
    total = u32(image, at + 4)
    expected_hcrc = u32(image, at + 8)
    actual_hcrc = jffs2_crc(image[at:at + 8])
    ino = u32(image, at + 12)
    ver = u32(image, at + 16)
    mode = u32(image, at + 20)
    isize = u32(image, at + 28)
    frag_offset = u32(image, at + 44)
    csize = u32(image, at + 48)
    dsize = u32(image, at + 52)
    compression = image[at + 56]
    expected_dcrc = u32(image, at + 60)
    expected_ncrc = u32(image, at + 64)
    actual_ncrc = jffs2_crc(image[at:at + 60])
    print("inode=%d%s version=%d mode=0%o file_size=%d" % (
        ino, " [requested]" if ino == wanted else " [different inode]", ver, mode, isize))
    print("totlen=%d fragment_file_offset=0x%X stored_size=%d unpacked_size=%d compression=%d" % (
        total, frag_offset, csize, dsize, compression))
    print("header_crc: stored=0x%08X actual=0x%08X %s" % (
        expected_hcrc, actual_hcrc, crc_result(expected_hcrc, actual_hcrc)))
    print("node_crc:   stored=0x%08X actual=0x%08X %s" % (
        expected_ncrc, actual_ncrc, crc_result(expected_ncrc, actual_ncrc)))
    if total < 68 or at + total > len(image) or csize > total - 68:
        print("Cannot safely calculate data CRC: invalid sizes or truncated node.")
        return
    actual_dcrc = jffs2_crc(image[at + 68:at + 68 + csize])
    print("data_crc:   stored=0x%08X actual=0x%08X %s" % (
        expected_dcrc, actual_dcrc, crc_result(expected_dcrc, actual_dcrc)))
    print("(A different CRC from the live boot log can mean the image was made at a different time.)")


def parse_dirents(image):
    found = []
    pos = 0
    while True:
        pos = image.find(MAGIC_DIRENT, pos)
        if pos < 0:
            break
        if pos + 40 > len(image):
            break
        total = u32(image, pos + 4)
        parent = u32(image, pos + 12)
        version = u32(image, pos + 16)
        ino = u32(image, pos + 20)
        size = image[pos + 28]
        # Directory names must be nonempty and fit in the complete node.
        if (size and 40 + size <= total <= 4096 and pos + total <= len(image)
                and jffs2_crc(image[pos:pos + 8]) == u32(image, pos + 8)
                and jffs2_crc(image[pos:pos + 32]) == u32(image, pos + 32)
                and jffs2_crc(image[pos + 40:pos + 40 + size]) == u32(image, pos + 36)):
            name = image[pos + 40:pos + 40 + size].decode("utf-8", "replace")
            found.append((pos, parent, version, ino, name, image[pos + 29]))
        pos += 4
    return found


def make_paths(parent, current_names, history, seen=None, limit=4):
    if parent == 1:
        return [""]
    if limit <= 0 or parent in (seen or set()):
        return ["/<ancestry-loop-or-depth-limit:%d>" % parent]
    seen = set(seen or ())
    seen.add(parent)
    matches = current_names.get(parent) or history.get(parent, [])
    if not matches:
        return ["/<unknown-parent-inode:%d>" % parent]
    paths = []
    for rec in matches[:6]:
        _offset, pino, _ver, _ino, name, _typ = rec
        for prefix in make_paths(pino, current_names, history, seen, limit - 1):
            paths.append(prefix + "/" + name)
            if len(paths) >= 8:
                return paths
    return paths


def main():
    ap = argparse.ArgumentParser(description="Read-only JFFS2 inode and dirent analysis")
    ap.add_argument("image", type=Path, help="Path to mtd6_allrootfs.bin NAND dump")
    ap.add_argument("inode", type=int, nargs="?", default=981)
    ap.add_argument("--node-offset", type=lambda x: int(x, 0), default=KNOWN_NODE_OFFSET)
    args = ap.parse_args()
    if not args.image.is_file():
        ap.error("Image not found: %s" % args.image)
    image = args.image.read_bytes()
    print("Image:", args.image, "(%d bytes)" % len(image))
    if len(image) != EXPECTED_IMAGE_SIZE:
        print("WARNING: expected a 67108864-byte mtd6 data dump", file=sys.stderr)
    print("Requested inode:", args.inode)

    inspect_inode_at(image, args.node_offset, args.inode)
    print("\n== SCANNING VALID DIRECTORY RECORDS ==")
    records = parse_dirents(image)
    print("Valid raw dirents (header, node and name CRC pass):", len(records))
    latest_by_name = {}
    for rec in records:
        offset, pino, version, ino, name, typ = rec
        key = (pino, name)
        old = latest_by_name.get(key)
        if old is None or (version, offset) > (old[2], old[0]):
            latest_by_name[key] = rec

    active_names = defaultdict(list)
    historical_names = defaultdict(list)
    for rec in records:
        if rec[3]:
            historical_names[rec[3]].append(rec)
    for rec in latest_by_name.values():
        if rec[3]:
            active_names[rec[3]].append(rec)
    for values in active_names.values():
        values.sort(key=lambda x: (-x[2], x[0]))
    for values in historical_names.values():
        values.sort(key=lambda x: (-x[2], x[0]))

    target = sorted(historical_names.get(args.inode, []), key=lambda r: (r[1], r[4], -r[2]))
    print("Dirents pointing to inode %d: %d" % (args.inode, len(target)))
    for rec in target[:40]:
        offset, pino, version, ino, name, typ = rec
        newest = latest_by_name[(pino, name)]
        status = ("latest dirent still points here" if newest[3] == ino
                  else ("later deletion (ino=0)" if newest[3] == 0
                        else "later replacement by inode %d" % newest[3]))
        candidates = make_paths(pino, active_names, historical_names)
        print("flash=0x%08X parent=%d version=%d name=%r type=%d: %s" % (
            offset, pino, version, name, typ, status))
        for path in candidates[:4]:
            print("  candidate path: %s/%s" % (path, name))
    if len(target) > 40:
        print("... %d more records omitted" % (len(target) - 40))
    if not target:
        print("No surviving dirent for this inode in the BACKUP. It may have been")
        print("garbage-collected, orphaned, or absent in this image snapshot.")

    print("\nNOTE: dirents in a raw image include obsolete history. Paths are")
    print("candidates, NOT proof that a named file exists in current Linux.")
    print("No writes to image or NAND performed.")


if __name__ == "__main__":
    main()
