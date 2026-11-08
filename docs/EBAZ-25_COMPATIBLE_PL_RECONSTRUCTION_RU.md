# EBAZ-25 — собственная совместимая PL для заводской Linux EBAZ4205

**Статус:** архитектурное решение и аудит исходных проектов. **НЕТ** новой собранной bitstream, RTL/DRC/STA PASS или аппаратного PASS. Дата 2026-11-08.

## Цель

Собрать собственную конфигурацию XC7Z010CLG400-1, которая функционально воспроизводит минимально необходимые интерфейсы прежней PL под действующую Linux 4.6 / PetaLinux 2016.4, и только затем дополнить её новыми аппаратными модулями. **Заводские HDL-исходники Ebang неизвестны; восстановление побитовой идентичности не планируется.**

### Незаменимая периферия/контракты

| Компонент | Реальная плата / известное | Критерий совместимости |
|---|---|---|
| PS7 | XC7Z010, ARM, DDR3, NAND, SDIO, PS UART | PS конфигурация и clocks не должны расходиться с NAND FSBL/U-Boot и работающей Linux; PS не «перепрошивается» bitstream |
| GEM0 через EMIO | IP101G 100M MII, MDIO, PHY clock | Мост GEM EMIO ↔ 4-bit MII, регистры 100 Mb/s, MDIO IOBUF и тактирование PHY |
| Ethernet pins | RXCLK U14, TXCLK U15, RXD[0..3] Y16/V16/V17/Y17, RXDV W16, TXD[0..3] W18/Y18/V18/Y19, TXEN W19, MDC W15, MDIO Y14 | Никаких несовместимых I/O назначений |
| PHY 25 MHz | U18 в нескольких проектах; цепь зависит от монтажа Y3 и R1485 | Проверить реальную обвязку; источник частоты и частота действительно работают |
| AXI BRAM | Controller window 0x40000000–0x40001FFF (8 KiB), Linux ранее читал 128 B | Потребуется проверка DT/IP, конфигурации и регистров; не считать «обычный AXI BRAM» автоматически эквивалентом |
| AXI UARTLite | 0x42C00000, /dev/ttyUL2, IRQ по инвентаризации 166 | Совпадение адреса, тактирования, IRQ, peripheral compatibility и физической связи с PL |
| LED6 | Green W13, Red W14, active-low | Уже проверены в EBAZ-24.1 |
| PS UART | ttyPS0 (MIO), 115200 | Независимый физически от PL, но не от состояния Linux/AXI |

Полная Linux device-tree совместимость включает не только XDC и AXI адреса: важны драйверы, interrupts, clocks, resets, тип и версия IP, а также свойства существующего DTB.

### Открытые опорные проекты

1. **[KeitetsuWorks/EBAZ4205](https://github.com/KeitetsuWorks/EBAZ4205)** — Vivado 2021.2 Tcl block design `vivado/ebaz4205.tcl`, `PS7`, EMIO Ethernet MII/MDIO, FCLK3 25 MHz на U18, LED XDC W13/W14. Лицензия **MIT**. **Первый кандидат для изучения и допустимого заимствования с сохранением атрибуции**. **Не содержит полной заводской AXI BRAM/UARTLite совместимости**.
2. **[nightseas/ebit_z7010](https://github.com/nightseas/ebit_z7010)** — Vivado 2018.3 block design, DDR/SDIO/UART/MII через EMIO, Device Tree. Лицензия **GPL-3.0-or-later**; исследовать как независимую модель; перенос кода требует соблюдения GPL.
3. **[darktjm/ebaz](https://github.com/darktjm/ebaz)** — Ethernet module `ebaz-eth.v`, XDC PHY/LED/pinout; автор отмечает, что образец **не генерирует 25 MHz PHY clock** при отсутствующем кварце и не устанавливает GEM mode/clock. Явной лицензии в проверенных корневых файлах не обнаружено: **изучать, не копировать код без разрешения**.
4. Сводная таблица нашей платы — [EBAZ-21 BOARD PINOUT](EBAZ-21_BOARD_PINOUT_AND_FACTORY_FPGA_RU.md), результаты штатных IP [EBAZ-20 INVENTORY](EBAZ-20_SYSTEM_INVENTORY_RU.md).

## Стратегия

1. **Исходная точка**: не переписывать `mtd5` и не терять образ NAND. Повторная PL-only конфигурация EBAZ-24.1 уже выявила риск зависания Linux.
2. **Доказательная база**: снять `/proc/iomem`, `/proc/interrupts`, список platform devices / DT совместимостей, полную релевантную секцию дерева устройств, `dmesg`, `/proc/cmdline` и инвентаризацию PHY-clock, до нового PL full-load; исключить скрытые PL-драйверы.
3. **Новый Vivado 2025.2 проект**: мигрировать или воспроизвести структуру KeitetsuWorks, сверить PS7 init с фактической NAND Linux / FSBL, соединить MII/MDIO, обеспечить clock25 PHY на физически действующий вывод, LED.
4. **Восстановление AXI**: создать AXI BRAM Controller и AXI UARTLite по IP Catalog; согласовать memory map, IRQ и clock с устройствами Linux. Не объявлять совместимость до проверки отличий с заводской PL.
5. **Автоматизированная сборка**: Tcl, report_drc, report_timing, utilization, SHA256; DRC критические violations = STOP; зафиксировать PS7, clocks, reset / AXI interconnect и IP версий.
6. **Первое аппаратное испытание**: не hot-swap заводскую PL при работающих Linux-драйверах. Уточнить U-Boot команды, bootcmd, RAM адрес, приоритет источника PL, затем временно загрузить новую PL перед Linux и стартовать совместимый kernel/DT без записи NAND. При необходимости подготовить отдельный DTB на SD.
7. **Наблюдения**: физический PS UART / Linux login, Ethernet PHY carrier и ping/SSH, UARTLite, BRAM 8KiB, LED, холодный откат из NAND. Не заявлять PASS прежде фактических логов.
8. **Повторное PCAP hot-load**: только после успеха нового статического PS/PL проекта и отдельной схемы остановки/возобновления нужных драйверов. При открытии `/dev/xdevcfg` Linux 2016.4 сбрасывает PL **до передачи bitstream**, это не решается одним сохранением XDC.

### Почему недостаточно просто сохранить пины

Совпадение pinout не гарантирует (а) PS7 GEM EMIO MII/MDIO wiring, (б) FCLK3/25MHz PHY, (в) timing и регистрационные параметры GEM0, (г) совместимые memory-mapped AXI slave offsets/interrupts, (д) согласованность Device Tree и (е) отсутствие доступа активных драйверов к PL при сбросе.

### Дополнение: частичная реконфигурация

Partial Reconfiguration / Dynamic Function eXchange требует собственной **заранее спроектированной статической области PL**; имея только закрытый заводской bitstream, нельзя безопасно «вставить» туда partial module. Сначала создаётся собственная совместимая базовая платформа, уже после проектируется reconfigurable partition.
