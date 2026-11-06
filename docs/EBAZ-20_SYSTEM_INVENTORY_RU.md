# EBAZ-20 — Безопасность, инвентаризация Zynq и интерфейс ARM/FPGA

## Исходный статус

Этап EBAZ-19 аппаратно завершён: очищенная JFFS2 автономно загружается из NAND, Ethernet получает адрес по DHCP, доступ SSH по открытому ключу проверен. Исходный образ mtd6 сохранён отдельно и сверён контрольной суммой. Временный TFTP-сервер остановлен, каталог обмена очищен, права на резервный файл ограничены пользователем, системной учётной записью и администраторами.

## Цель

1. Зафиксировать воспроизводимую инвентаризацию аппаратных и программных ресурсов работающей платы.
2. Оценить поверхность атаки устаревшей PetaLinux и составить план усиления безопасности без потери SSH/UART.
3. Определить доступные ресурсы PS/PL Zynq и текущие отображения устройств в адресном пространстве ARM.
4. Реализовать первое минимальное, обратимое взаимодействие ARM и FPGA с проверкой на оборудовании.

## Ограничения

- Начальный этап только для чтения: не изменять NAND, U-Boot, device tree, FPGA bitstream и конфигурацию сетевого доступа.
- Не публиковать приватные SSH-ключи, резервные образы NAND, пароли или содержимое закрытых файлов.
- Записывать результаты проверок отдельно от гипотез.
- Перед изменениями прошивки иметь проверенный аварийный путь загрузки и резервную копию.

## EBAZ-20.1 — Первичная инвентаризация (ожидается)

Снять из работающей Linux-системы: `uname -a`, `/proc/cpuinfo`, `/proc/meminfo`, `/proc/mtd`, `/proc/iomem`, `/proc/modules`, список интерфейсов UIO и FPGA manager, активные сетевые службы.

Статус: ожидается журнал диагностики пользователя.

## EBAZ-20.1 — Фактическая инвентаризация Linux

Проверка по работающей плате после закрытия EBAZ-19:

- ARMv7 SoC: два процессора, CPU part 0xc09 (Cortex-A9), NEON/VFPv3. Ядро 4.6.0-xilinx ARMv7, PetaLinux 2016.4.
- Память: `MemTotal: 252032 kB` (246 MiB доступно ядру), аппаратная DDR 256 MiB.
- NAND: 9 разделов `mtd0`—`mtd8`, включая `mtd6` 64 MiB, на котором расположена рабочая очищенная JFFS2.
- `/proc/iomem`: PL-совместимое UARTLite `0x42c00000-0x42c0000f`; PS UART `0xe0000000` и `0xe0001000`; GEM Ethernet `0xe000b000`; SD/MMC `0xe0100000`; devcfg `0xf8007000`; GPIO `0xe000a000`.
- `/proc/modules` пуст: загруженных модулей нет. Это не исключает встроенные в ядро драйверы.
- `/sys/class/uio` пуст, `/dev/uio*` отсутствуют; `/sys/class/fpga_manager` не существует. Это не означает отсутствия PL: битстрим загружает U-Boot.
- Команда `netstat -lntup` не поддерживается BusyBox 1.24.1 (нет опции `-p`); для следующей инвентаризации используем `netstat -lnt` и `netstat -lnu`.

Следующий шаг EBAZ-20.2 — прочитать DT/sysfs-маршрут UARTLite и список реально слушающих сетевых портов. Никаких записей в MMIO, NAND или конфигурацию пока нет.

## EBAZ-20.2 - PL UARTLite and network listening services

Hardware log confirms the PL UARTLite at 0x42c00000 is a Linux platform device under soc0/amba_pl and is bound to the uartlite driver. Its character device is /dev/ttyUL2. PS UART devices /dev/ttyPS0 and /dev/ttyPS1 exist. Legacy PL configuration device /dev/xdevcfg and sysfs class are present; neither firmware nor PL programming was attempted. No UIO device was detected in EBAZ-20.1.

BusyBox netstat -lnt showed only TCP port 22 listening on IPv4 and IPv6. netstat -lnu showed no UDP listening sockets. Process list included inetd, DHCP client, Dropbear, logging, getty, and a key-authenticated SSH session; it showed no recognized running mining process. A listening socket audit does not prove the system is free of vulnerabilities or malware.

Next safe read-only checks: inspect /proc/device-tree/amba_pl and the of_node attributes of the 42c00000.serial device; inspect active inetd configuration. Do not access MMIO registers, FPGA configuration device, or persistent NAND until the register map and rollback requirements are understood.

## EBAZ-20.3 - Device Tree and inetd inspection

- The PL device tree node contains `axi_bram_ctrl@40000000` and `serial@42c00000`.
- UARTLite compatible value: `xlnx,xps-uartlite-1.00.a`.
- UARTLite `reg`: base 0x42C00000, mapped range length 0x00010000 according to DT; Linux uartlite driver has a smaller 16-byte register resource in `/proc/iomem`.
- UARTLite `interrupts` bytes: 00 00 00 00 00 00 00 1d 00 00 00 01 (GIC SPI number 29, flags 1).
- `/etc/inetd.conf` contains only commented example services, including telnet and ftp. Prior socket audit showed TCP 22 only and no bound UDP listeners. The inetd process is present but currently provides no enabled services from this file.
- The existence of a BRAM-controller node in DT is not yet evidence of a working accessible BRAM: verify its DT compatible, reg, status and kernel binding before any MMIO experiment.

Next read-only checks: list `/proc/device-tree/amba_pl/axi_bram_ctrl@40000000/`, decode the compatible, reg and status properties, inspect `/sys/devices/soc0/amba_pl`, and check whether `/dev/mem` is available. Do not write NAND or read/write arbitrary MMIO until the BRAM map is known.

## EBAZ-20.4 — AXI BRAM Controller Device Tree inventory

- Board DT node `/proc/device-tree/amba_pl/axi_bram_ctrl@40000000`, compatible `xlnx,axi-bram-ctrl-4.0`.
- `reg` bytes `40 00 00 00 00 00 20 00` encode CPU physical base `0x40000000` and address **window size** `0x2000` (8192 bytes); **not yet proof** of backed RAM capacity or readable hardware.
- DT node has parameters `xlnx,memory-depth`, `xlnx,bram-addr-width`, `xlnx,ecc`, `xlnx,bram-inst-mode`, `xlnx,single-port-bram`, etc. Values not yet inspected.
- DT `status` property absent: per Devicetree Specification, equivalent to `okay`. Linux created the platform device `/sys/devices/soc0/amba_pl/40000000.axi_bram_ctrl`.
- `/dev/mem` exists, permissions `crw-r----- root kmem`, but no direct access has been attempted and no BRAM hardware read/write is confirmed.
- Next check is **read-only DT parameters and driver binding**. Do not touch raw MMIO or change the bitstream yet.

## EBAZ-20.5 - BRAM configuration decoded

The real board DT BRAM-controller properties decode as follows: `xlnx,memory-depth=2048`, `xlnx,bram-addr-width=11`, `xlnx,ecc=0`, `xlnx,single-port-bram=1`, `xlnx,s-axi-ctrl-data-width=32`, and `xlnx,bram-inst-mode=EXTERNAL`. The device has no `/sys/devices/soc0/amba_pl/40000000.axi_bram_ctrl/driver` symlink, i.e. no kernel driver currently bound. A final `ls -la` command was shown without its output.

Xilinx PG078 AXI BRAM Controller v4.0 (2016) and v4.1 (2019), table of BRAM addressing configurations, show that 2,048 x 32-bit words require 11 BRAM address bits and represent 8 KiB. This agrees with the Device Tree window of 0x2000 bytes at physical 0x40000000, but the actual external BRAM generator, data access and clocking have not yet been tested. `EXTERNAL` means BRAM instantiation outside the controller IP, not off-chip DRAM. `single-port-bram=1` means the controller uses one BRAM port for both reading and writing; it does not establish independent FPGA-side access to that memory.

Reference: https://docs.amd.com/v/u/en-US/pg078-axi-bram-ctrl . Next phase: read-only inspection of device sysfs, PL configuration and devmem utility availability, followed by one controlled 32-bit read only if bus responsiveness can be tested safely. No NAND, bitstream or MMIO writes.

## EBAZ-20.6 — Проверка готовности к чтению BRAM

Подтверждено в Linux: `40000000.axi_bram_ctrl` есть в `/sys/devices/soc0/amba_pl/`, но ссылка `driver` отсутствует. `/proc/iomem` не содержит диапазона 0x40000000, что совместимо с отсутствием привязанного драйвера; работоспособность BRAM этим не проверена. Доступна `/sbin/devmem` (апплет BusyBox). Интерфейс `/dev/xdevcfg` существует. `dmesg` показывает регистрацию UARTLite при 0x42c00000 и не содержит сообщений о BRAM. Устройство остается под управлением исходного bitstream, который ранее успешно загрузил U-Boot.

Следующее испытание: однократное **только чтение** 32-битного слова 0x40000000 через `/sbin/devmem`, желательно при подключенном UART; учитывать риск аппаратного зависания/ошибки шины в случае отсутствующего AXI slave. Не выполнять никаких MMIO записей, перепрограммирования PL или NAND. Значение, прочитанное один раз, доказывает лишь отклик адреса, а не полноценный двусторонний обмен PS/PL.

## EBAZ-20.7 — First hardware read of AXI BRAM address

In running Linux 4.6.0-xilinx on EBAZ4205, `/sbin/devmem 0x40000000 32` returned `0x00000043` with exit code 0. Thus a 32-bit ARM-side physical-address read at the AXI BRAM DT base completed without a reported bus error. This does **not** yet establish writable BRAM, unique backing storage, data origin, or an ARM-to-PL application protocol. Hex byte 0x43 equals ASCII 'C', but that is only a possible interpretation and is not confirmed. No MMIO writes were performed.

An `xauth: command not found` line appeared in the SSH session. It is independent of the BRAM read and likely due to optional X11 forwarding; future SSH sessions may use `ssh -x`.

Next low-risk step: read a few more aligned 32-bit words from the established DT mapping at 0x40000004, 0x40000008, 0x4000000C, and 0x40000010, recording exact results; do not modify MMIO, FPGA bitstream, NAND, or boot configuration. Only perform writes after identifying the contents and consumers of this memory and preparing a rollback plan.

## EBAZ-20.8 — Eight consecutive BRAM reads

Eight read-only 32-bit `devmem` accesses of the DT-mapped AXI BRAM address space completed with the following results:

| Offset | Read value |
|---|---|
| 0x00 | 0x00000043 |
| 0x04 | 0x00000001 |
| 0x08 | 0x00000008 |
| 0x0C | 0x00000008 |
| 0x10 | 0x00000008 |
| 0x14 | 0x00000008 |
| 0x18 | 0x00000000 |
| 0x1C | 0x00000000 |

Observed data have apparent structure but no identified schema. 0x43 is ASCII 'C' only as a possible interpretation. A successful Linux read of this location demonstrates accessible 32-bit words but not that all 8192 bytes are backed, writable, or shared with independent PL logic. No MMIO writes were performed.

Next: read the adjacent eight 32-bit words (offsets 0x20..0x3C) and repeat the initial eight word reads after a short interval to see whether the observed values change. Continue with read-only diagnostic commands only.

## EBAZ-20.9 - Second set of BRAM word reads

The board returned the following additional **read-only** 32-bit words at AXI BRAM base 0x40000000: offset +0x20 = 0x0000003F; +0x24 = 0x0000000E; +0x28 = 0x0000001E; +0x2C = 0x0000001E; +0x30, +0x34, +0x38, +0x3C = 0x00000000. The earlier reads at offsets +0x00 through +0x1C were repeated unchanged, confirming their stability across those two observations. No MMIO writes performed. Meaning and producer of these values remain unknown. Next: inspect available cross-compilation toolchain, implement a read-only mmap-based ARM utility for controlled memory snapshots, and establish a baseline before modifying PL.

## EBAZ-20.10 — WSL2 cross-toolchain check

- CHUWI WSL2 (`alex@DESKTOP-R6ITICD`) has `/usr/bin/make` and `/usr/bin/git`.
- Neither `arm-linux-gnueabihf-gcc` nor `arm-linux-gnueabi-gcc` is installed. `dpkg -l 'gcc-arm-linux*'` returns no installed packages.
- Proposed WSL-only setup: install Ubuntu package `gcc-arm-linux-gnueabihf` plus ARMHF cross libc development files; compile a tiny fully statically linked ARMv7 binary first. A static test avoids requiring the old PetaLinux 2016.4 userspace to provide newer glibc symbols.
- On-board filesystem, NAND, FPGA bitstream and access credentials must not be altered in this toolchain setup step.

## EBAZ-20.11 — ARM toolchain and first reproducible app template

Verified on CHUWI WSL2: `arm-linux-gnueabihf-gcc` 13.3.0, binary at `/usr/bin/arm-linux-gnueabihf-gcc`, `-print-sysroot` returns `/` (not necessarily erroneous for Debian multiarch cross-toolchain). Installation and ABI tests: [EBAZ-20_ARM_TOOLCHAIN_RU.md](EBAZ-20_ARM_TOOLCHAIN_RU.md). Canonical read-only ARM-to-AXI-BRAM source and build files: [../software/ebaz20-bram-reader/README.md](../software/ebaz20-bram-reader/README.md). Full static cross-build and execution on the target are **pending**, not claimed as PASS. The source code and its validation scripts were checked syntactically; no NAND or FPGA bitstream writes.

## EBAZ-20.12 — Verified ARM cross-build on CHUWI

User cloned repository to `~/EBAZ4205` on WSL2, changed to `software/ebaz20-bram-reader` and successfully ran `make clean && make check` with `arm-linux-gnueabihf-gcc` 13.3.0. Build used `-mcpu=cortex-a9 -mfpu=neon -mfloat-abi=hard -static` and strict warnings. The ELF verification script output `Class: ELF32`, `Machine: ARM`, `Version5 EABI, hard-float ABI`, `Tag_ABI_VFP_args: VFP registers` and `EBAZ20_ARM_STATIC_ELF_CHECK_PASS`. Binary SHA-256: `e05b7cd4afd711ae6c3802c74037baa93422c7b082062c7c185205c563c5ae31`. This is a verified cross-build only: target execution and hardware BRAM read remain pending. Next: transfer the ELF to an explicitly RAM-mounted filesystem, run its `--help` smoke test, then limited `--words 16` hardware read while UART remains attached. Avoid creating a supposed RAM directory in NAND-backed rootfs without first verifying the mount point.

## EBAZ-20.13 — ARM help smoke test exits zero

Following correction of the original SSH file transfer (the first ELF was truncated at 65,536 bytes in a 64-KiB /dev tmpfs), the user reports `EBAZ20_HELP_EXIT=0` from the board shell. Assuming that status was captured immediately after `/dev/ebaz20-ram/ebaz20-bram-reader --help`, the static ARM Cortex-A9 application's non-MMIO help path now runs successfully. The full SHA-256 of the newly transferred file was not included in the latest reported output, and `--words 16` is **not yet tested**. Next gate: verify the on-board ELF SHA-256 equals WSL2 original `e05b7cd4afd711ae6c3802c74037baa93422c7b082062c7c185205c563c5ae31`, then run limited read-only `--words 16` with UART available, record values and exit code.


## EBAZ-20.14 — ARM BRAM reader hardware execution PASS (2026-11-06)

On EBAZ4205 (`root@zedboard-zynq7`) the statically built, custom ARM Linux program `/dev/ebaz20-ram/ebaz20-bram-reader --words 16` completed successfully. It printed `EBAZ20_BRAM_READ_BEGIN base=0x40000000 words=16`, then 16 32-bit readings identical to previous independent BusyBox `devmem` results, and `EBAZ20_BRAM_READ_PASS`. Shell returned `EBAZ20_BRAM_READER_EXIT=0`.

| Offset | Value |
|---|---|
| 0x00 | 0x00000043 |
| 0x04 | 0x00000001 |
| 0x08 | 0x00000008 |
| 0x0C | 0x00000008 |
| 0x10 | 0x00000008 |
| 0x14 | 0x00000008 |
| 0x18 | 0x00000000 |
| 0x1C | 0x00000000 |
| 0x20 | 0x0000003F |
| 0x24 | 0x0000000E |
| 0x28 | 0x0000001E |
| 0x2C | 0x0000001E |
| 0x30 | 0x00000000 |
| 0x34 | 0x00000000 |
| 0x38 | 0x00000000 |
| 0x3C | 0x00000000 |

**Hardware verdict:** `EBAZ20_ARM_BRAM_READER_HARDWARE_PASS` for read-only ARM Cortex-A9 Linux userspace `/dev/mem` → `mmap()` → AXI-accessible address window `0x40000000–0x4000003F`. No MMIO writes, bitstream changes or NAND writes were performed in this application test.

**Limitations:** This test does not establish 8-KiB full coverage, whether the read data are changing under PL control, or independent two-way ARM↔PL synchronization. The user omitted the ELF SHA-256 output in the final test report, so target checksum equality with the WSL original `e05b7cd4afd711ae6c3802c74037baa93422c7b082062c7c185205c563c5ae31` remains to be explicitly documented. The earlier transfer was truncated at 64KiB due to the active `/dev` tmpfs; the subsequent execution used the separate 8MiB RAM-backed filesystem.

Next cautious test: verify actual target SHA-256; then expand read-only sample to 32 words (`--words 32`, 0x80 bytes) to validate adjacent addresses. Do not write any BRAM or reflash NAND.
