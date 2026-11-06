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
