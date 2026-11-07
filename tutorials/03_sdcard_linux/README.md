# LAB-03 — SDHC в NAND-загруженной Linux

**Статус: PASS для накопителя Linux; загрузка с SD вместо NAND — UNKNOWN.**

## Цель
Проверить обнаружение и автомонтирование карты памяти без изменения загрузочного источника. На нашем экземпляре проверялась SDHC 16 ГБ, раздел VFAT.

## Проверка
~~~sh
cat /proc/partitions
cat /proc/mounts | grep mmcblk
ls -l /run/media/mmcblk0p1
~~~
На нашем экземпляре раздел /dev/mmcblk0p1 смонтирован в /run/media/mmcblk0p1. После копирования набора файлов Developer SD можно запустить протестированную программу:
~~~sh
sh /run/media/mmcblk0p1/EBAZ4205/tests/buttons/test-buttons.sh
~~~
Ожидается реакция на SW2/SW3 (не KEY1–KEY4 переходника). Доказательство и файлы: [Developer SD](../../sdcard/README.md), [фактический протокол](../../sdcard/EBAZ4205/tests/buttons/README.md).

## Границы
Не выполнять повторный mount поверх уже смонтированной карты, не форматировать её, не переключать NAND/SD boot straps. Hot insertion, SD boot и электрическая схема конкретного переходника этим тестом **не подтверждены**.

