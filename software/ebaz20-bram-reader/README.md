# EBAZ-20: ARM / AXI BRAM Reader

Minimal read-only program for the EBAZ4205 board. It reads 32-bit words from the device-tree-mapped BRAM address window (base `0x40000000`, size `0x2000`) through `/dev/mem`.

## Build in Ubuntu WSL2

See [ARM toolchain setup](../../docs/EBAZ-20_ARM_TOOLCHAIN_RU.md).

```sh
sudo apt update
sudo apt install -y gcc-arm-linux-gnueabihf libc6-dev-armhf-cross binutils-arm-linux-gnueabihf make git file
make check
```

Artifact: `build/ebaz20-bram-reader`. The executable is linked with `-static`, compiled for Cortex-A9 hard-float ABI, and checked for an ARM ELF32 header, hard-float ABI and absence of an ELF interpreter and dynamic dependencies. A passing ELF check does not replace a hardware test.

## Interface

```text
ebaz20-bram-reader --help
ebaz20-bram-reader --words 16
ebaz20-bram-reader --words 2048
```

Default 16 words; argument range 1..2048. Program uses `open(O_RDONLY|O_SYNC)` and `mmap(PROT_READ)`. It does not write MMIO, NAND or FPGA configuration.

**Hardware safety:** even read-only MMIO access can hang if a PL AXI slave is absent; for initial tests use 16 words, which were already read using devmem. Keep UART connected. Do not put program binaries into NAND-backed `/tmp` inadvertently; use a temporary RAM-backed mount. Refer to the toolchain setup guide for deployment commands.


## Real-board acceptance (2026-11-06)

**PASS:** On EBAZ4205, this cross-compiled ARMv7 Cortex-A9 binary ran as `/dev/ebaz20-ram/ebaz20-bram-reader --words 16`. It printed 16 32-bit words from `0x40000000` through `0x4000003C`, identical to prior independent `devmem` reads, followed by `EBAZ20_BRAM_READ_PASS`; shell exit code `0`. No writes were performed. See [EBAZ-20 hardware journal](../../docs/EBAZ-20_SYSTEM_INVENTORY_RU.md).

**Deployment gotcha:** `/dev` is overmounted with a 64 KiB `tmpfs` on this PetaLinux build. Transferring a statically linked ELF **directly into `/dev`** truncated the file and led to misleading `Permission denied` / `Segmentation fault` symptoms. Transfer directly into a separate 8 MiB executable RAM-backed mount at `/dev/ebaz20-ram`; compare SHA-256 with the WSL-built ELF before execution. The actual target SHA checksum is still awaiting a separately recorded output.

## Hardware verification: 32 words

On 2026-11-06, the user verified `ebaz20-bram-reader --words 32` on the board: all 32 aligned 32-bit reads succeeded, first 16 equal earlier BusyBox `devmem` results, next 16 at offsets 0x40–0x7C all zero. `EBAZ20_BRAM_READ_PASS` and shell code 0. This is a **read-only 128-byte hardware test**, not a write test or a completed ARM/FPGA mailbox. Do not infer zero-valued words are unused. On-board ELF SHA-256 should still be recorded separately.
