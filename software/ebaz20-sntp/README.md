# EBAZ-20: SNTP bootstrap for Zynq Linux

**Status:** host build and simulated UDP tests PASS; **ARM cross-build and EBAZ4205 hardware tests PENDING**. Nothing installed into NAND or Linux init.

Our board's `nxp,pcf8563` RTC in Device Tree fails probe, so Linux boots with an invalid clock (2010). The kernel system clock can be set via NTP without an external RTC. The board only has `rdate`, which uses RFC868 Time Protocol, **not NTP**.

This C program performs a **single SNTPv4 UDP query**, defaults to numeric Cloudflare server `162.159.200.1:123` to avoid DNS, checks response correlation / stratum / delay / reasonable year, then prints the estimated UTC. It **never changes system time by default**. Explicit `--apply` sets `CLOCK_REALTIME` as root.

**Limitations:** unauthenticated SNTP, not cryptographically trusted time, no long-term drift control; old 32-bit time support limited to before 2038. May fail if UDP/123 is blocked. Not suitable for security-critical production timekeeping.

## Ubuntu WSL2: cross-compile

```sh
cd ~/EBAZ4205/software/ebaz20-sntp
make clean && make check
```

The output `build/ebaz20-sntp` must be a fully static ARM ELF32 hard-float Cortex-A9 binary. Compare its SHA256 on the board. A successful cross-build does not establish hardware PASS.

## Transfer to RAM only

The main `/dev` mount is a **64-KiB tmpfs**; do not transfer your ELF directly into it. On the board (UART/root):

```sh
grep ' /dev/ebaz20-ram ' /proc/mounts || {
  mkdir -p /dev/ebaz20-ram
  mount -t tmpfs tmpfs /dev/ebaz20-ram -o size=8m,mode=0700,exec
}
```

On WSL2 (SSH host identity already verified):

```sh
ssh -T -x root@192.168.1.77 'cat > /dev/ebaz20-ram/ebaz20-sntp.new && chmod 700 /dev/ebaz20-ram/ebaz20-sntp.new && mv /dev/ebaz20-ram/ebaz20-sntp.new /dev/ebaz20-ram/ebaz20-sntp' < build/ebaz20-sntp
sha256sum build/ebaz20-sntp
ssh -T -x root@192.168.1.77 '/bin/busybox.nosuid sha256sum /dev/ebaz20-ram/ebaz20-sntp'
```

Stop if SHA differs.

## Hardware tests

On the board, first **query only**:

```sh
/dev/ebaz20-ram/ebaz20-sntp --server 162.159.200.1
date -u
```

Successful output should contain `EBAZ20_SNTP_QUERY_PASS` and `EBAZ20_SNTP_DRY_RUN_PASS`. Confirm UTC is plausible and compare to a trusted independent source. Only then, explicitly set the volatile kernel system clock:

```sh
/dev/ebaz20-ram/ebaz20-sntp --server 162.159.200.1 --apply
date -u
```

`EBAZ20_SNTP_CLOCK_SET_PASS` is the *expected* status, not yet observed on real hardware. Setting CLOCK_REALTIME does **not** write RTC, NAND, bitstream or Device Tree. **Do not enable auto-start until real-board tests pass.** After that, use bounded retries after DHCP acquires the lease; don't rely on a fixed sleep.

## Host mock tests

```sh
cc -O2 -std=c11 -Wall -Wextra -Wpedantic -Werror -o sntp-host-test sntp_clock.c
python3 test_sntp_host.py
```

Host-only simulated UDP server passes valid response, invalid stratum rejection, invalid response token rejection. This is **not** a live NTP network test.

References: [EBAZ Linux boot audit](../../docs/EBAZ-20_BOOT_INIT_CPU_AUDIT_RU.md), [Cloudflare public NTP](https://developers.cloudflare.com/time-services/ntp/usage/).

## SysVinit service: staged install (EBAZ-20.33)

**Stage 0: prerequisites already observed on board:** 64 MiB JFFS2 root has 49.6 MiB available; binary size 512.8 KiB; `eth0` uses DHCP; runlevel-5 starts networking from `S01networking`; on-board SNTP clock update already passed with verified SHA256 `e5b2f839223f9ac8e42e314bb1d984259248260837e5eb01d787e775e998d3eb`.

**Stage 1: install persistent binary, but DO NOT enable service yet** (EBAZ4205 UART as root):

```sh
mkdir -p /usr/local/sbin
cp /dev/ebaz20-ram/ebaz20-sntp /usr/local/sbin/ebaz20-sntp
chmod 700 /usr/local/sbin/ebaz20-sntp
sha256sum /usr/local/sbin/ebaz20-sntp
```

The hash must exactly match the above. A single copy to JFFS2 is a persistent NAND write; only proceed with existing rescue backup and UART.

**Stage 2: transfer SysV script from Ubuntu WSL2** (using the key installed in that WSL user account):

```sh
cd ~/EBAZ4205
git pull
ssh -T -x -i ~/.ssh/ebaz4205_ecdsa -o IdentitiesOnly=yes root@192.168.1.77 \
  'cat > /etc/init.d/ebaz20-sntp && chmod 700 /etc/init.d/ebaz20-sntp' \
  < software/ebaz20-sntp/ebaz20-sntp-init
```

**Stage 3: first manual service test before autostart** (board UART):

```sh
sh -n /etc/init.d/ebaz20-sntp
ls -ld /run
/etc/init.d/ebaz20-sntp start
sleep 15
/etc/init.d/ebaz20-sntp status
cat /run/ebaz20-sntp.log
date -u
```

Expected `PASS`, `EBAZ20_SNTP_CLOCK_SET_PASS`, and correct UTC. If not PASS, inspect the log rather than enabling startup. This is a one-shot background service: 24 attempts spaced 10 seconds apart, capped at approx. four minutes, only acts with an IPv4 lease and default route. Log and status are under RAM-backed `/run` (verify mount), not NAND.

**Stage 4: only after manual test PASS, enable autostart** (board UART):

```sh
ln -s ../init.d/ebaz20-sntp /etc/rc5.d/S30ebaz20-sntp
ls -l /etc/rc5.d/S30ebaz20-sntp
```

**Rollback before/after reboot**:

```sh
rm -f /etc/rc5.d/S30ebaz20-sntp
```

Remove only this link (not /etc/init.d script or the binary). Full reboot verification: inspect `/run/ebaz20-sntp.state`, `/run/ebaz20-sntp.log`, `date -u`, Ethernet IP/route, and Dropbear SSH. `S30` follows networking and dropbear but its child starts in the background, so it will not hold up the SysVinit sequence. Leave `networking`, `udhcpc`, `dropbear`, `mdev` unchanged.

**Safety limits:** the script does not continuously discipline clock drift, lacks NTP authentication and depends on public UDP/123. Changes are written to JFFS2 for persistence; avoid mass edits and monitor the JFFS2 summary warning previously observed. Do not claim BOOT_AUTOSYNC_PASS until a real post-reboot verification.


## Verified autonomous NAND boot: EBAZ-20.37

**HARDWARE PASS — 2026-11-07.** The static ARM32 program was installed at `/usr/local/sbin/ebaz20-sntp` on JFFS2 with verified SHA256 `e5b2f839223f9ac8e42e314bb1d984259248260837e5eb01d787e775e998d3eb`. The `/etc/init.d/ebaz20-sntp` script was syntax checked, manually tested PASS, and linked from `/etc/rc5.d/S30ebaz20-sntp`. After an actual EBAZ4205 NAND reboot, volatile `/run/ebaz20-sntp.log` showed `network ready, attempt=1`, `EBAZ20_SNTP_QUERY_PASS` (Cloudflare IPv4 `162.159.200.1`, stratum 3, RTT 5.0ms) and `EBAZ20_SNTP_CLOCK_SET_PASS` at `2026-11-07 07:57:36 UTC`. Service `status` returned `PASS` and `date -u` showed `Sat Nov 7 07:58:22 UTC 2026`. IPv4 `192.168.1.77` remained configured on eth0.

**Status:** `EBAZ20_SNTP_AUTOBOOT_PASS`. This validates unattended one-shot clock bootstrapping with a functioning network; it does not fix optional physical RTC, provide authenticated time, or continuously discipline clock skew. If the WAN/NTP service is unavailable during the bounded retries, the system clock can stay incorrect. Preserve `/etc/rc5.d/S30ebaz20-sntp` for autonomous use; rollback (if needed) is removing that symlink only.
