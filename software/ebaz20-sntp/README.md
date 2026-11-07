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
