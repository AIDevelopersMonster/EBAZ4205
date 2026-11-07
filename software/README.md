# EBAZ4205 — программы для ARM Cortex-A9 под Linux

[Главная](../README.md) · [Быстрый старт](../docs/QUICKSTART_RU.md) · [Инструментарий](../docs/EBAZ-20_ARM_TOOLCHAIN_RU.md) · [Матрица результатов](../docs/VERIFICATION_MATRIX_RU.md)

Исходники для существующего Zynq PS и Linux 4.6; **не** для компиляции HDL/FPGA на самой плате. Сборка выполняется на Ubuntu/WSL2 с `arm-linux-gnueabihf-gcc`; тестирование — на аппаратной EBAZ4205.

| Программа | Суть | Проверка на нашем экземпляре |
|---|---|---|
| [ebaz23-gpio-demo](ebaz23-gpio-demo/README.md) | C-программа читает кнопки SW2/SW3 через PS GPIO sysfs | **PASS**: реальные нажатия |
| [ebaz20-bram-reader](ebaz20-bram-reader/README.md) | Статическая ARM-программа читает PS→PL AXI BRAM, без записей в MMIO | **PASS**: 32 × 32 бит = 128 байт |
| [ebaz20-sntp](ebaz20-sntp/README.md) | Клиент SNTP для установки времени Linux при сетевом доступе | **PASS**: автоматическое применение при NAND boot, см. [журнал EBAZ-20](../docs/EBAZ-20_BOOT_INIT_CPU_AUDIT_RU.md) |

## Сборка и перенос

```sh
cd ~/EBAZ4205
# выберите конкретное приложение:
cd software/ebaz23-gpio-demo
make clean && make check
```

Результат ELF из `build/` передаётся на плату через SFTP. Проверяйте хеш и архитектуру бинарника, права на исполнение и фактическое размещение. `/tmp` на нашем Linux связан с `/var/volatile/tmp` (RAM-backed), а `/dev` смонтирован отдельно с лимитом 64 КиБ; **не переносите туда крупные ELF**.

## Вариант для комплектной SD

[sdcard/EBAZ4205/tests/buttons/test-buttons.sh](../sdcard/EBAZ4205/tests/buttons/test-buttons.sh) — готовый **shell-тест**, который запускается из VFAT без компиляции; **PASS на реальной плате**. Это отдельная реализация, не бинарный файл с исходником C.

**Нельзя** менять неизвестные AXI-регистры через `devmem` или менять FPGA bitstream без карты периферии и сценария восстановления. Подробнее: [AXI](../docs/EBAZ-20_AXI_ARM_FPGA_PRACTICAL_RU.md).
