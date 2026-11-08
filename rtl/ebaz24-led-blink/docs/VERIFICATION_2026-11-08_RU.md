# EBAZ-24.1 — протокол первой Vivado-сборки (2026-11-08)

**Источник результатов:** вывод Vivado 2025.2.1 и PowerShell, предоставленный оператором платы; результаты не воспроизводились автором документа на независимом ПК.

| Проверка | Результат | Статус |
|---|---|---|
| Цель проекта | XC7Z010CLG400-1, EBAZ4205 | согласно исходникам |
| Vivado генерация bitstream | `EBAZ24_BUILD_GENERATED` | **PASS** |
| Размер `.bit` | 2 083 883 байт | **PASS (файл создан)** |
| SHA256 `.bit` | `F191C7B1289ECB6AAEF2803459E5CA8D680B03272B60F09ADD271129C966469A` | зафиксирован |
| Setup WNS | +12.630 ns | **PASS** |
| Setup TNS | 0.000 ns, 0 failing endpoints | **PASS** |
| Hold WHS / THS | +0.254 ns / 0.000 ns | **PASS** |
| Pulse Width WPWS / TPWS | +7.000 ns / 0.000 ns | **PASS** |
| Timing coverage | no_clock=0, unconstrained_internal_endpoints=0 | **PASS** |
| I/O timing no_output_delay | 2 — автономные LED outputs, без внешнего timing interface | осознанное ограничение |
| DRC ZPS7-1 | `Warning: PS7 block required` (1) | **WARNING, НЕ закрыто** |
| Полевые испытания PCAP / LED / Ethernet rollback | Нет данных | **PENDING** |

## Разбор предупреждения

Vivado сообщает: `[DRC ZPS7-1] PS7 block required: The PS7 cell must be used in this Zynq design in order to enable correct default configuration.`

В текущем проекте PS7 отсутствует **намеренно**: используется только автономная PL-логика с `STARTUPE2.CFGMCLK` и двумя LED. Но это **не следует называть чистым DRC PASS**. Для стенда, на котором PS уже инициализирован загрузчиком Linux, такое PL-only применение является обоснованным экспериментом, однако точная совместимость с аппаратной конфигурацией платы пока не подтверждена.

## Подтверждение формата и канала загрузки

Официальная AMD Adaptive Computing Wiki описывает старый драйвер `xilinx_devcfg` и команду `cat bitstream.bit > /dev/xdevcfg`; для новых систем с FPGA Manager требуются `.bin` и другой интерфейс. Источник: https://xilinx-wiki.atlassian.net/wiki/spaces/A/pages/18841750/Solution+Zynq+PL+Programming

## Следующий этап — только локальный PS UART

1. Не изменять NAND, в частности раздел заводской FPGA (в текущих заметках `mtd5`; фактический `/proc/mtd` перепроверить).
2. Убедиться, что питание можно отключить физически и холодная загрузка восстанавливает заводской PL и Ethernet.
3. Проверить `ls -l /dev/xdevcfg`, `cat /proc/mtd`, штатное SD mount и `prog_done`.
4. Копировать `.bit` на SD, затем **сверить SHA256 на самой EBAZ4205**.
5. При подтверждении готовности — передать `.bit` в `/dev/xdevcfg` из локального UART-терминала. Ethernet/SSH и AXI IP старого bitstream могут исчезнуть; Linux может зависнуть.
6. При необходимости произвести полное power-cycle, проверить восстановление штатных PHY/Ethernet и NAND/Linux.
7. Только после физического наблюдения зафиксировать HARDWARE PASS.

**Важное уточнение:** положительный STA говорит лишь о выполнении заданных временных ограничений; он не доказывает правильность распиновки, совместимость Ethernet или успех загрузки FPGA.
