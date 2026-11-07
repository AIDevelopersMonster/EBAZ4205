# LAB-02 — две штатные кнопки SW2/SW3 через PS GPIO

**Статус: PASS для реальных SW2 и SW3 основной EBAZ4205.**

## Важно
SW2/SW3 на основной плате **не являются** четырьмя KEY1–KEY4 на переходнике 660269A_Y13. Здесь используется PS MIO20 и MIO32 (в нашем образе Linux GPIO926 и GPIO938 при gpiochip base=906), без новой конфигурации PL.

## Испытанный тест с microSD
После подготовки Developer SD и автоматического монтирования раздела:
~~~sh
sh /run/media/mmcblk0p1/EBAZ4205/tests/buttons/test-buttons.sh
~~~
Нажать SW2 и SW3, наблюдать строки «Нажата кнопка SW2» / «Нажата кнопка SW3». Завершение Ctrl+C. Скрипт проверяет направление in, не переключает GPIO в output, не прошивает FPGA и NAND. Учитывает ограничения BusyBox на дробный sleep.

## Исходники, протокол, альтернативная реализация
- [Проверенный shell-тест и фактический лог](../../sdcard/EBAZ4205/tests/buttons/README.md)
- [Исходник shell](../../sdcard/EBAZ4205/tests/buttons/test-buttons.sh)
- [Программа ARM/C с Makefile](../../software/ebaz23-gpio-demo/README.md)
- [EBAZ-23 PS MIO/EMIO](../../docs/EBAZ-23_PS_MIO_EMIO_AVAILABLE_PINS_RU.md)

**PASS:** обнаружены нажатия обеих штатных кнопок на нашей плате. Никакого вывода о работе KEY1–KEY4 переходника или LED через PL этот опыт не даёт.

