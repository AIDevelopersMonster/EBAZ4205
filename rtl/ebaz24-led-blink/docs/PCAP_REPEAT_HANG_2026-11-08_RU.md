# EBAZ-24.1 — диагностика повторного программирования PL из Linux 4.6

**Дата:** 2026-11-08. **Статус:** исследование драйвера завершено, первопричина зависания **не доказана**; дальнейшие попытки `cat > /dev/xdevcfg` без подготовки запрещены методикой лаборатории.

## Подтверждено оборудованием

- EBAZ4205: XC7Z010, Linux 4.6.0-xilinx/PetaLinux 2016.4, BusyBox.
- `/dev/xdevcfg` есть, до эксперимента `prog_done=1`.
- Bitstream `ebaz24_led_blink.bit` размер 2 083 883 байта, SHA256 `f191c7b1289ecb6aaef2803459e5ca8d680b03272b60f09add271129c966469a`, совпадает на ПК и SD.
- DRC: warning `ZPS7-1 PS7 block required`; WNS +12.630 ns, WHS +0.254 ns, TNS 0.
- Первая загрузка bitstream дала визуальное попеременное мигание LED; **появление shell prompt после загрузки не подтверждено**.
- Повторная загрузка из PS UART вывела неоднократно `alloc_contig_range: [e044, e046) PFNs busy`; shell prompt не вернулся по показанному фрагменту. Полный dmesg и итог `PCAP_RC` не представлены.
- Заводской `mtd5` 8 388 608 байт копирован на SD без записи NAND; SHA256 `c0e787f2caf0b4c9287680ba2737b0778404e9af0222262634a14dad69ea3884`.

## Что показал аудит ОС и драйвера

**Фактический исходный код версии Xilinx 2016.4:** https://github.com/Xilinx/linux-xlnx/blob/xilinx-v2016.4/drivers/char/xilinx_devcfg.c

1. `xdevcfg_open()` ещё до отправки bitstream вызывает `zynq_slcr_init_preload_fpga()` и `xdevcfg_reset_pl()` для полного bitstream. **PL сбрасывается при открытии файла `/dev/xdevcfg`**, а не только после загрузки данных.
2. `xdevcfg_write()` для **каждой** операции write выделяет `dma_alloc_coherent(dev, count+residue, ...)`, ждёт DMA-completion (1-секундный timeout в петле), затем освобождает буфер. Один `cat` порождает много последовательных write. Поэтому сообщения CMA возможны даже для файлов около 2 МиБ.
3. Двухстраничный диапазон PFN `[e044,e046)` сам по себе не доказывает нехватку 2 МиБ непрерывной памяти. Linux MM допускает временное `PFNs busy` с успешной повторной попыткой: https://lkml.rescloud.iu.edu/hypermail/linux/kernel/2304.2/03775.html
4. `xdevcfg_release()` после записи вызывает `zynq_slcr_init_postload_fpga()`. Проблема с недоступными после full PL swap AXI IP может появиться как до завершения операции, так и после.
5. В текущем PL-only проекте намеренно **нет** Ethernet EMIO/MII/MDIO, AXI BRAM `0x40000000`, UARTLite `0x42C00000` и блока PS7. Linux/DT при этом по-прежнему может считать эти устройства существующими. PS UART реализован в PS и электрически от PL не зависит, но ядро может зависнуть от AXI bus hang/driver access.

**Отдельно:** документация AMD подтверждает `cat design.bit > /dev/xdevcfg` для устаревшего xdevcfg; FPGA Manager нового Linux использует `.bin`, не переносить советы между этими интерфейсами:
- https://xilinx-wiki.atlassian.net/wiki/spaces/A/pages/18841750/Solution+Zynq+PL+Programming
- https://xilinx-wiki.atlassian.net/wiki/spaces/A/pages/18841645/Solution+Zynq+PL+Programming+With+FPGA+Manager

## Гипотезы и дисциплина проверки

| Приоритет | Гипотеза | Как проверить |
|---|---|---|
| 1 | Kernel/driver AXI bus hang после потери PL IP | Осмотр `dmesg`, `/proc/iomem`, `/sys/bus/platform/devices`, `/proc/interrupts`, device-tree; раздельный PS+PL compatible build |
| 2 | DMA coherent/CMA allocator периодически не может выделить блок | `CmaTotal/CmaFree`, kernel cmdline, ранняя и поздняя попытки, dmesg с кодом завершения |
| 3 | Зависание `xdevcfg` при повторном полном PL reset | Сверить reset, kernel version/patches и прогресс `prog_done` при доступном ядре |

`PFNs busy` не является самостоятельным доказательством отказа DMA; **сигнал UART ≠ завершение user-space syscall**.

## Следующий контролируемый этап

После холодного восстановления заводской прошивки только чтение:

```sh
uname -a
cat /proc/cmdline
grep -E 'MemFree|MemAvailable|CmaTotal|CmaFree' /proc/meminfo
dmesg | grep -i -E 'cma|alloc_contig|devcfg|xdevcfg|axi|timeout|hung' | tail -n 60
cat /proc/iomem
ls /sys/bus/platform/devices
```

При необходимости изучить U-Boot с локальным UART и нажатой клавишей остановки автобута; **только read-only**: `help fpga`, `help fatload`, `mmc list`, `printenv bootcmd`, `bdinfo`. AMD документирует `fatload mmc ...` + `fpga loadb ...`, но адрес RAM и конкретные команды надо валидировать по реальному U-Boot, не выполнять вслепую.

## Инженерное решение

- **Не отключать PS UART**, он требуется для контроля. Отключение SSH не равнозначно остановке Linux-драйвера Ethernet; команды `drop_caches`/`compact_memory` не решают конфликт Linux/PL.
- Для лабораторий с PL-only конфигурацией приоритетен **U-Boot PCAP до Linux**, без запущенных драйверов AXI и GEM; аппаратная проверка этого пути еще впереди.
- Для Linux hot-load спроектировать новый PL с согласованными Ethernet EMIO и всеми реально используемыми PL AXI IP или перед записью корректно вывести Linux-драйверы/устройства из работы (после проверки DT и sysfs). Только тогда тестировать повторное программирование, фиксируя `PCAP_RC`, `prog_done`, LED, состояние UART/SSH.
- Отложенный `nohup` запуск по SSH не устраняет этих аппаратно-драйверных причин; также не использовать `dd bs=1M` для «исправления» CMA (потребность в сплошной памяти может возрасти).
- Не записывать экспериментальный bitstream в NAND, не менять mtd5, не править U-Boot environment.

**Проверенный факт:** LED мигали. **Не подтверждено:** возвращение Linux shell после загрузки, стабильность повторной загрузки, восстановление Ethernet после power cycle по отдельному логу.
