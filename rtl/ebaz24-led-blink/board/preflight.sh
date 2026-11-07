#!/bin/sh
# READ-ONLY EBAZ24 preflight. Can be executed on the board under BusyBox sh.
# Does not program the FPGA, write NAND or alter GPIO.
echo '=== EBAZ24 READ-ONLY PREFLIGHT ==='
echo '=== KERNEL ==='
uname -a
echo '=== PL CONFIGURATION DEVICE ==='
ls -l /dev/xdevcfg 2>&1
if [ -r /sys/class/xdevcfg/xdevcfg/device/prog_done ]; then
    cat /sys/class/xdevcfg/xdevcfg/device/prog_done
else
    echo 'prog_done path not found (driver-specific); inspect /sys/class/xdevcfg/'
    ls -l /sys/class/xdevcfg 2>&1
fi
echo '=== NAND MAP (NO WRITE) ==='
cat /proc/mtd
echo '=== SD MOUNT ==='
grep 'mmcblk0p1' /proc/mounts || true
echo '=== ETHERNET CARRIER / ROUTE ==='
if [ -r /sys/class/net/eth0/carrier ]; then
    cat /sys/class/net/eth0/carrier
fi
route -n 2>/dev/null || true
echo '=== EXPECTED USERSPACE DEVICES ==='
ls -l /dev/ttyPS0 /dev/ttyUL2 2>&1
echo '=== OPTIONAL BITSTREAM FILE ==='
if [ $# -gt 0 ]; then
    file=$1
    if [ ! -r "$file" ] || [ ! -f "$file" ]; then
        echo 'EBAZ24_PREFLIGHT_FAIL: bitstream file missing' >&2
        exit 1
    fi
    ls -l "$file"
    wc -c < "$file"
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$file"
    fi
fi
echo 'EBAZ24_PREFLIGHT_FINISHED: no programming and no hardware writes.'
echo 'NOT A PERMISSION TO PROGRAM: confirm physical UART and cold-boot rollback.'
