#!/bin/sh
set -eu
BIN=${1:-build/ebaz20-sntp}
READELF=${2:-arm-linux-gnueabihf-readelf}
[ -s "$BIN" ] || { echo "FAIL: binary missing" >&2; exit 1; }
command -v "$READELF" >/dev/null 2>&1 || { echo "FAIL: missing $READELF" >&2; exit 1; }
"$READELF" -h "$BIN" | grep -q 'Machine:.*ARM' || { echo "FAIL: not ARM" >&2; exit 1; }
"$READELF" -h "$BIN" | grep -q 'Class:.*ELF32' || { echo "FAIL: not ELF32" >&2; exit 1; }
"$READELF" -A "$BIN" | grep -q 'Tag_ABI_VFP_args: VFP registers' || { echo "FAIL: not ARM hard-float ABI" >&2; exit 1; }
if "$READELF" -l "$BIN" | grep -q 'INTERP'; then echo "FAIL: interpreter present" >&2; exit 1; fi
if "$READELF" -d "$BIN" | grep -q '(NEEDED)'; then echo "FAIL: dynamic dependencies present" >&2; exit 1; fi
sha256sum "$BIN"
echo EBAZ20_SNTP_ARM_STATIC_ELF_CHECK_PASS
