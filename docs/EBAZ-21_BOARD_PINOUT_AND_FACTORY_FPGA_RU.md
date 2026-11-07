# EBAZ-21 — физические порты, распиновка и штатная конфигурация FPGA

> **Актуализация справочника (07.11.2026):** SDHC 16 ГБ с VFAT уже обнаружена и автоматически смонтирована на нашем экземпляре при NAND boot; обе кнопки SW2/SW3 успешно испытаны. Ранние строки ниже со статусом `UNKNOWN`/«не проверено» — **историческая инвентаризация до испытаний**. Актуальный итог: [матрица PASS](VERIFICATION_MATRIX_RU.md).

**Дата:** 2026-11-07. **Плата:** EBAZ4205, XC7Z010. **Источники:** наша аппаратная инвентаризация в `docs/EBAZ-20_SYSTEM_INVENTORY_RU.md` и открытые XDC/схемы по ссылкам ниже. **Статусы:** PASS = проверено на нашем экземпляре; REFERENCE = задокументировано другими авторами; UNKNOWN = не подтверждено у нас. Чужой XDC описывает *проект/переходник автора*, не обязательно заводской bitstream.

## Постоянные источники физических схем

- [xjtuecho: принципиальная схема EBAZ4205-SCH.pdf (1 лист)](https://github.com/xjtuecho/EBAZ4205/blob/master/HW/ebaz4205/EBAZ4205-SCH.pdf) — опубликованная схема; перед электрическим подключением сверить с установленной ревизией.
- [xjtuecho: оригинальная PCB и инструкции импорта Altium/KiCad](https://github.com/xjtuecho/EBAZ4205/tree/master/HW/ebaz4205); [исходная PCB Elrori](https://github.com/Elrori/EBAZ4205/blob/master/ebit.pcb).
- [darktjm: подробная разводка разъёмов DATA1/2/3 и Ethernet](https://github.com/darktjm/ebaz/blob/master/ebaz.xdc); [реализация Ethernet EMIO](https://github.com/darktjm/ebaz/blob/master/ebaz-eth.v).
- [tomorrow56: таблица pin assign](https://github.com/tomorrow56/EBAZ4205_tutorial/blob/main/tutorials/ebaz4205_pin_assign.csv), [сводный XDC](https://github.com/tomorrow56/EBAZ4205_tutorial/blob/main/tutorials/ebaz4205_merged.xdc).
- [mwalle: карта платы](https://gist.github.com/mwalle/d8291e241075d82d1d420afa9302bd91).
- [xjtuecho: Hardware Build States — опциональные компоненты](https://github-wiki-see.page/m/xjtuecho/EBAZ4205/wiki/Hardware-Build-States.-What-you-may-or-not-have-fitted-on-your-board.).

## Наш экземпляр — что действительно работало

| Узел | Наблюдение | Статус |
|---|---|---|
| ARM Cortex-A9 x2, Linux 4.6.0-xilinx | `/proc/cpuinfo`, `uname`; MemTotal 252032 kB | PASS |
| DDR | 256 MiB номинально, 246 MiB видит Linux | PASS для Linux RAM |
| NAND 128 MiB | MTD0–8, корень mtd6 JFFS2 64 MiB | PASS |
| Ethernet, DHCP, SSH | активен `eth0`, Dropbear по ключу | PASS |
| PS UART | `ttyPS0` 115200, U-Boot и Linux console | PASS |
| PL UARTLite | `ttyUL2` `0x42c00000`, IRQ 166, драйвер uartlite, ранее обмен подтверждён | PASS |
| AXI BRAM | `0x40000000`, DT window 8 KiB, 2048x32, mode EXTERNAL, single-port=1; команда `devmem` и собственная ARM программа успешно прочитали 128 байт | **PASS только чтение 128 байт** |
| Конфигурация PL | `/dev/xdevcfg` и отдельный NAND `mtd5` 8 MiB; по нашим журналам U-Boot загружает PL bitstream до Linux | PASS для механизма загрузки, **содержимое файла логически не реконструировано** |
| SD | PS MMC в Linux `e0100000`; наличие и пайка слота на конкретной плате не подтверждены | UNKNOWN физически |
| GPIO, LED, FAN, DATA, JTAG | существуют в опубликованных схемах/XDC, на нашем экземпляре ещё не сделаны прозвонка/фото и прикладные тесты | REFERENCE |

## Физические интерфейсы платы — что может быть доступно

| Интерфейс | Ориентиры по разъёмам/сигналам | Что проверить до подключения |
|---|---|---|
| RJ45 10/100, PHY IP101G | Линии MII/MDIO идут через PL, критично для SSH | Тактирование PHY 25 MHz (Y3 может отсутствовать), режим EMIO и конфигурация PS7; **не заменять штатный bitstream по SSH вслепую** |
| UART (PS) | Консоль `ttyPS0`; физическое место зависит от установленной обвязки | Только 3.3 V TTL, не RS232; GND, RX/TX и направление по фото |
| FPGA UART на DATA1 | В сторонних проектах UART FPGA RX H16=DATA1_6, TX H17=DATA1_11 | Это не означает, что именно `ttyUL2` физически заведён на эти контакты в штатном bitstream; нужна проверка |
| JTAG | TCK F9, TMS J6, TDI G6, TDO F6 (специализированные выводы, не user GPIO) | Физическая площадка/штырьки и питание Vref; не путать с PS UART |
| DATA1/DATA2/DATA3 | Три разъёма с шагом 2.0 mm, номинально 20 позиций, смесь IO и питания/земли | Смотреть `hardware/EBAZ4205_DATA_CONNECTORS_PINMAP.csv`, не считать все 20 контактами GPIO |
| Разъёмы вентиляторов | J3: SPEED V13, PWM U12; J5: SPEED V15, PWM V12 (darktjm XDC) | Проверка физической схемы/назначения/уровней, мотор напрямую к FPGA не подключать |
| Индикаторы на плате | Зеленый W13 и красный W14 в darktjm; ETH LED PHY, PWR и DONE — отдельные | Некоторые светодиоды не GPIO; RGB LED из других проектов относится к дочерним платам |
| SD / microSD | SDIO контроллер PS; slot/резисторы и boot-страпы могут отсутствовать | Сначала фото обеих сторон и проверка установленности/режима загрузки |
| HDMI/VGA/LCD/PS2 | **Не встроенные штатные порты**, доступны через внешние переходники DATA с собственными цепями | HDMI TMDS 3.3 V, трассировка дифпар, согласование, защита и проверка bank voltage |
| Питание | Плата была майнинговым контроллером, в репозиториях встречаются изменения питания | Не подавать питание по внешним DATA без электрической схемы и измерения; зафиксировать текущий штатный источник |

### Карта выводов из независимого XDC darktjm (REFERENCE, НЕ замена заводской схеме)

Файл `hardware/EBAZ4205_DATA_CONNECTORS_PINMAP.csv` содержит **42 идентифицированных сигнальных контакта**: DATA1=14, DATA2=14, DATA3=14, с ball pin и банком. Отсутствующие контакты в XDC не объявлены свободными, а часть несёт питание или землю (сверка со схемой обязательна).

Контакты GPIO на одном и том же банке могут быть одновременно использованы Ethernet и внешней периферией. Конфликт **не определяется только по совпадению номера DATA**: проверять `PACKAGE_PIN` и `IOSTANDARD`. Особенно: H16/H17 (внешний PL UART по примеру), H18/K17/E19 (LED дочерней платы), T19/P19/U20/U19/V20 (кнопки DATA3), T20/R18/N17/R19/P20 (LCD DATA3), F19/F20/D19/D20/B19/B20/A20/C20 (HDMI дочерней платы).

В другом tutorial встречается системный CLK N18 33.33 MHz, а darktjm пишет `XTAL 5 (not present)`. **Это проектные различия и/или аппаратные варианты. Не использовать N18 как гарантированный внешний oscillator без проверки на нашей плате.** Подобным образом в ранних референсных XDC встречаются разночтения нумерации DATA2. Авторские данные не являются паспортом нашего экземпляра.

## Штатная FPGA — подтвержденная функциональная карта

```text
NAND mtd5 bitstream --(U-Boot/xdevcfg during startup)--> Zynq PL
                                                        |
ARM PS / Linux -- AXI PS->PL --> 0x40000000 ... 0x40001FFF: AXI BRAM Controller v4.0
         |                       DT: memory-depth=2048 x 32 bits, EXTERNAL, single-port=1
         |                       mmap(/dev/mem) 32 words / 128 bytes READ PASS, WRITES NOT TESTED
         |
         +--- AXI PS->PL --> 0x42C00000: Xilinx UARTLite
         |                      /dev/ttyUL2, driver bound, 16-byte Linux resource
         |
         +--- GEM Ethernet --> EMIO / PL pins --> PHY IP101G --> RJ45
         |                      Ethernet physically works; exact current RTL not extracted
         |
         +--- PS UART0/1, DDR, NAND, SDIO and other PS peripherals
```

**Достоверно:** работали ARM/Linux+Ethernet/SSH, PS UART и PL UARTLite; чтение 128 байт с AXI BRAM; U-Boot и xdevcfg позволяют конфигурировать PL. **Вероятно:** текущий PL содержит как минимум согласованную с Device Tree логику UARTLite и BRAM controller; внешнюю ETH-MII коммутацию. **Не установлено:** полная netlist, IP-cores, принадлежность/значение 0x43/0x01/0x08…, физический источник этих слов, PL-side доступ к BRAM, обработка прерываний BRAM, остальные неописанные в DT периферийные блоки и все физически выведенные FPGA UART линии.

### Первые 16 слов BRAM (реальная плата, только чтение)

| Offset (hex) | 00 | 04 | 08 | 0C | 10 | 14 | 18 | 1C | 20 | 24 | 28 | 2C | 30 | 34 | 38 | 3C |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Value (hex) | 43 | 01 | 08 | 08 | 08 | 08 | 00 | 00 | 3F | 0E | 1E | 1E | 00 | 00 | 00 | 00 |

Слова +0x40..+0x7C = 0. Значение `0x43` **не названо** ни сигнатурой протокола, ни ASCII-командой: это неизвестные данные, возможная адресная таблица майнингового приложения. Ни запись, ни независимый PL-master не тестировались.

## Как извлекать знания о существующем PL, не разрушая систему

1. Снять локальный NAND dump `mtd5` **только чтение** и сохранить вне GitHub вместе с SHA-256, геометрией/плохими блоками. НЕ исполнять `nandwrite`, `flash_erase`, `saveenv`, `cat bit > /dev/xdevcfg`.
2. Снять `printenv` U-Boot и фактические длины/адреса загрузки bitstream; сохранить копию DTB и декомпилировать на ПК (dtc).
3. Сравнить содержимое mtd5 по заголовку/IDCODE/параметрам битового потока, затем — при наличии нужных средств — извлечь конфигурационную метаинформацию. Дизассемблирование bitstream в исходную RTL-схему в общем случае **невозможно**, нельзя заявлять, что RTL восстановлен.
4. Для внешних портов: фото обеих сторон и ревизии, наличие Y3, SD, переключателей и заводских доработок; визуально подтвердить номера DATA и линий питания; прозвонка при выключенном питании.
5. Эксперименты с новым проектом сначала synth/place-route в Vivado offline, проверка XDC и EMIO Ethernet + безопасного boot recovery, затем временная загрузка, не перепрошивая NAND.

## Степень готовности интерфейсов к проектам

- **Сейчас:** user-space ARM программа, AXI BRAM только чтение, ранее проверенный UARTLite, сеть.
- **После подтверждения/безопасного обновления PL:** AXI4-Lite регистры с версией и ACK, двунаправленный BRAM mailbox, аппаратная криптография/ DSP / GPIO.
- **После проверки разъемов:** LCD ST7789, HDMI/VGA, кнопки/LED, buzzer, PS/2, отдельная плата интерфейсов.

**Источники нашей проверки:** [EBAZ-20 inventory](EBAZ-20_SYSTEM_INVENTORY_RU.md), [ARM BRAM-reader](../software/ebaz20-bram-reader/README.md), [общий атлас](EBAZ-21_COMMUNITY_PROJECTS_REVIEW_RU.md).
