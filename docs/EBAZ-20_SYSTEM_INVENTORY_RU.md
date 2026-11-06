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
