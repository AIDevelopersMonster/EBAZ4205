# EBAZ-24.1 — первая FPGA-программа для EBAZ4205

**Статус:** исходники добавлены, статический контроль выполнен на локальной копии. RTL-симуляция и Vivado synth/place/route не запускались в среде подготовки; `.bit` ещё **нет**. Испытание FPGA через PCAP **не проводилось**.

Цель: попеременно мигать **штатными LED6 EBAZ4205**: GREEN = W13, RED = W14, уровень активен при 0. Источник тактирования — `STARTUPE2.CFGMCLK` (внутренний генератор конфигурации). Проект рассчитан на `xc7z010clg400-1`.

## Содержимое

- [src/ebaz24_led_core.v](src/ebaz24_led_core.v) — синтезируемый счётчик и логика двух LED.
- [src/ebaz24_led_top.v](src/ebaz24_led_top.v) — STARTUPE2, подключение к ядру.
- [ebaz24_led.xdc](ebaz24_led.xdc) — W13/W14; справочная распиновка независимо представлена KeitetsuWorks и darktjm.
- [tb/tb_ebaz24_led_core.v](tb/tb_ebaz24_led_core.v), [test.sh](test.sh) — функциональный тестбенч для Icarus Verilog.
- [build.tcl](build.tcl) — non-project flow для Vivado: синтез, place/route, DRC, timing, `.bit`.
- [board/preflight.sh](board/preflight.sh) — **только чтение** состояния уже работающей Linux.
- [tests/static_check.py](tests/static_check.py) — структурная проверка файлов, **не аппаратная верификация**.

## Запуск на ПК

В Linux или WSL2 при установленном Icarus Verilog:

```sh
sh test.sh
```

Ожидается `EBAZ24_LED_CORE_TB_PASS`. Затем на Windows/Linux с Vivado и включённой поддержкой Zynq-7000:

```sh
vivado -mode batch -source build.tcl
```

В `build/` должны появиться `ebaz24_led_blink.bit`, `drc.rpt`, `timing_summary.rpt` и `utilization.rpt`. Проверить отчёты и `SHA256` до загрузки.

**ВНИМАНИЕ: эта конфигурация FPGA не включает Ethernet MII/EMIO и не воспроизводит заводские AXI BRAM/UARTLite. При её полной загрузке Ethernet/SSH прервутся; Linux также может зависнуть при обращениях к старым AXI-адресам.** Только локальный PS UART 115200 8N1 и физическая возможность выключить/включить питание.

## Перед экспериментом: без записи

На EBAZ4205 через локальный PS UART:

```sh
sh /run/media/mmcblk0p1/EBAZ4205/fpga/ebaz24/board/preflight.sh
```

или скопировать туда этот скрипт и выполнить. Сверить `/dev/xdevcfg`, NAND partitions, mount SD и состояние сети. Убедиться, что при обычном холодном запуске заводской U-Boot загружает сохранённый bitstream из NAND.

## Загрузка PL через Linux (только после сборки и проверок)

Скопировать битстрим на SD по адресу:

```text
/run/media/mmcblk0p1/EBAZ4205/fpga/ebaz24/ebaz24_led_blink.bit
```

В старой схеме Xilinx devcfg/PetaLinux применяется запись **`.bit`** в `/dev/xdevcfg`, но точное поведение следует проверить на установленном драйвере. Команда для **отдельного контролируемого аппаратного этапа**, не исполнять до подтверждения готовности:

```sh
BIT=/run/media/mmcblk0p1/EBAZ4205/fpga/ebaz24/ebaz24_led_blink.bit
cat "$BIT" > /dev/xdevcfg
echo "EBAZ24_XDEVCFG_RC=$?"
```

Вследствие смены PL могут перестать отвечать PL UARTLite/BRAM, а SSH будет разорван. Повторная загрузка штатного PL **после полного отключения питания** ожидается из существующей NAND, но именно этот восстановительный тест пока не проведён. Не писать в NAND, `mtd5`, U-Boot environment.

Подробный анализ рисков — [EBAZ-24 Ethernet и восстановление](../../docs/EBAZ-24_FPGA_ETHERNET_SAFE_BRINGUP_RU.md).

## Сравнение с разработками сообщества

- [Alex-Electron/ZX_BulbuLator bring-up](https://github.com/Alex-Electron/ZX_BulbuLator/tree/main/research/01-board-bringup-blink) — такой же подход CFGMCLK, но D18/H18 на внешней плате вместо W13/W14.
- [darktjm/ebaz](https://github.com/darktjm/ebaz) — MII/MDIO через EMIO, XDC штатных светодиодов.
- [KeitetsuWorks/EBAZ4205](https://github.com/KeitetsuWorks/EBAZ4205) — собственный PS7/Ethernet Vivado проект.
- [AIDevelopersMonster/Sipeed-FPGA](https://github.com/AIDevelopersMonster/Sipeed-FPGA) и [KonSol-RetroStation](https://github.com/AIDevelopersMonster/KonSol-RetroStation) — наша практика self-checking тестбенчей и отчётов синтеза, но у них другая FPGA (Gowin).

Код данной лаборатории предоставлен под [MIT](LICENSE). Лицензия не распространяется автоматически на заводские и сторонние исходники.
