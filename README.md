# EBAZ4205 — Xilinx Zynq ARM + FPGA Laboratory

Hardware: EBAZ4205 / XC7Z010

## Initial observations

- U-Boot 2015.07
- PetaLinux 2016.4
- Linux 4.6.0-xilinx
- Dual-core ARM Cortex-A9
- DDR: 256 MiB
- NAND: 128 MiB
- UART console: ttyPS0, 115200 8N1
- Boot source: NAND
- FPGA configuration: top_ctrl

## Milestone EBAZ-00

UART communication confirmed.
U-Boot autoboot interrupted using key 'd'.

Status: UBOOT_UART_CONTROL_PASS

## Project goals

1. Preserve factory firmware and configuration.
2. Document bootloader and memory architecture.
3. Investigate Linux without miner software.
4. Develop FPGA and ARM applications.
5. Build reproducible hardware/software laboratories.

## Safety

Do not modify the factory NAND before backup.
Do not publish unsanitized UART logs or credentials.
