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

## Пошаговая инструкция: UART → Linux root shell

[**EBAZ-03 — Подключение USB–TTL, перехват U-Boot клавишей `d` и загрузка Linux без майнера до приглашения `sh-4.3#`**](docs/EBAZ-03_UART_LINUX_SHELL_RU.md)

Проверено на реальной плате. Заводская NAND не изменяется; режим диагностический (`init=/bin/sh`, корневая файловая система только для чтения).

## Видео: EBAZ-19 — запуск очищенного Linux из NAND

[▶️ EBAZ4205: пересборка Linux, запись JFFS2 в NAND и успешная автономная загрузка (YouTube Shorts)](https://youtube.com/shorts/_ULPOgmIEM0)

Показан результат EBAZ-19: загрузка Linux с очищенного раздела NAND, восстановленная сеть и доступ по SSH. [Технический журнал EBAZ-19](docs/EBAZ-19_CLEAN_JFFS2_REBUILD_RU.md).

## Project goals

1. Preserve factory firmware and configuration.
2. Document bootloader and memory architecture.
3. Investigate Linux without miner software.
4. Develop FPGA and ARM applications.
5. Build reproducible hardware/software laboratories.

## Safety

Do not modify the factory NAND before backup.
Do not publish unsanitized UART logs or credentials.

## EBAZ-20 — разработка собственных ARM-программ

[Стандарт toolchain для WSL2/ARM Cortex-A9: установка, сборка, ELF/ABI, доставка и тестирование](docs/EBAZ-20_ARM_TOOLCHAIN_RU.md).

[Первое приложение: read-only AXI BRAM reader](software/ebaz20-bram-reader/README.md). Использует `/dev/mem` только на чтение по адресу `0x40000000` и не меняет NAND/FPGA. Аппаратная проверка завершена: 32 слова (128 байт) успешно прочитаны через AXI BRAM на реальной плате; код завершения 0.

## Видео: EBAZ-20 — собственная ARM-программа читает FPGA через AXI

[▶️ ARM читает FPGA! EBAZ4205 / Zynq-7000 / AXI BRAM — 128 байт, PASS (YouTube Shorts)](https://youtube.com/shorts/LdDsGtTQiSQ)

В ролике показано чтение 32 слов (128 байт) собственной программой на C, скомпилированной для ARM Cortex-A9 и запущенной под Linux 4.6.0-xilinx. Данные совпали с контрольными чтениями через `devmem`; `EBAZ20_READ32_EXIT=0`. Подтверждено **чтение** по AXI-адресу, а не запись или готовый двусторонний протокол ARM↔FPGA. [Технический журнал](docs/EBAZ-20_SYSTEM_INVENTORY_RU.md).

## Практическая статья: AXI и ARM ↔ FPGA

[**AXI в Xilinx Zynq-7000: от программы ARM до памяти FPGA — теория, адресация, протокол и EBAZ-20**](docs/EBAZ-20_AXI_ARM_FPGA_PRACTICAL_RU.md).

Статья разделяет AXI4, AXI4-Lite и AXI4-Stream, показывает каналы чтения, схему PS→PL, реальную адресную карту BRAM, `mmap()`-чтение 128 байт и план следующей лаборатории с настоящим двусторонним протоколом. Подтверждённые измерения отделены от проектных предположений.

## EBAZ-20 — ревизия загрузки, служб и Cortex-A9

[**Открыт аудит BootROM/FSBL → U-Boot → Linux → SysVinit → сетевые службы и два Cortex-A9**](docs/EBAZ-20_BOOT_INIT_CPU_AUDIT_RU.md). Сначала снимаем фактическую карту автозагрузки, содержимое `/etc/inittab`, `rcS.d`, `rc5.d`, список процессов, CPU online и mountpoints. Изменения NAND/bitstream и отключение сервисов пока запрещены. Приоритеты: наложенный 64-KiB tmpfs на `/dev`, Ethernet PHY/DHCP, пустой `inetd`, а также проверка SMP/драйверов.

## EBAZ-20 — синхронизация программных часов по SNTP

[**Клиент SNTP для Cortex-A9: исходный код, проверка ответа, установка системного времени (только по `--apply`)**](software/ebaz20-sntp/README.md). Аппаратный RTC на плате пока не подтверждён; системное время может быть установлено после получения сети. Локальная сборка/имитационные тесты PASS, кросс-сборка и испытание на EBAZ4205 ещё **PENDING**. Автозагрузка не менялась.



### EBAZ-20 — автосинхронизация системных часов: PASS

**`EBAZ20_SNTP_AUTOBOOT_PASS` (07.11.2026):** после полной загрузки из NAND PetaLinux 2016.4 самостоятельно дождалась DHCP, получила время от SNTP-сервера и установила системные часы Linux. Для этого аппаратный RTC не требуется при доступной сети. Доказательство и ограничения — в [журнале EBAZ-20.37](docs/EBAZ-20_BOOT_INIT_CPU_AUDIT_RU.md); исходники — [software/ebaz20-sntp](software/ebaz20-sntp/README.md).

## EBAZ-21 — внешние проекты, схемы, порты и FPGA

- [Атлас проектов GitHub: оценка, состав, лицензии, что заимствовать и улучшить](docs/EBAZ-21_COMMUNITY_PROJECTS_REVIEW_RU.md).
- [Аппаратная карта: схемы, физические порты, разводка и подтверждённая штатная FPGA](docs/EBAZ-21_BOARD_PINOUT_AND_FACTORY_FPGA_RU.md).
- [CSV-таблица 42 сигнальных контактов DATA1/DATA2/DATA3](hardware/EBAZ4205_DATA_CONNECTORS_PINMAP.csv) — **сторонние XDC, до подключения проверить именно нашу ревизию**.

Важный уже выполненный этап: EBAZ-20 ARM BRAM-reader прочитал 32 слова (128 байт) с адреса `0x40000000`, PASS. Программа не осуществляла запись. Для штатного bitstream и полного списка задействованных выводов требуется дальнейшая верификация. Не заменять конфигурацию PL без сохранения Ethernet EMIO и запасного UART/JTAG-доступа.

## EBAZ-22 — Commercial product / товарный комплект

[**Коммерческое ТЗ: подготовка бывшей майнинговой EBAZ4205 для перепродажи с платой расширения, себестоимость, критерии готовности, проверка спроса**](docs/EBAZ-22_COMMERCIAL_PRODUCT_BRIEF_RU.md).

Приоритет проекта — воспроизводимая подготовка комплектов и реальные продажи, а не самостоятельное исследование. Целевой закупочный ориентир 3 000 ₽, розница 4 500–6 000 ₽; расчёты не включают все накладные расходы. Каждую новую лабораторию оцениваем по добавленной покупателю функции, снижению брака и времени на подготовку.
