# EBAZ-23 — две кнопки EBAZ4205 (PS GPIO) без перепрошивки FPGA

**Статус:** самостоятельная исходная программа добавлена в GitHub, **на аппаратуре ещё не проверена**; ARM cross-build также не подтверждён. Linux 4.6.0-xilinx, GPIO chip `zynq_gpio` base=906, ngpio=118. Кнопки S2 MIO20 -> Linux GPIO926, S3 MIO32 -> GPIO938 — это соединения из [схемы внешнего проекта](https://github.com/KeitetsuWorks/EBAZ4205/blob/master/linux/ebaz4205/project-spec/meta-user/recipes-bsp/device-tree/files/ebaz4205.dtsi), не подтверждённый электрический тест на нашей плате.

## Зачем свой код

Сторонний [gpio-demo.c](https://github.com/KeitetsuWorks/EBAZ4205/blob/master/linux/ebaz4205/project-spec/meta-user/recipes-apps/gpio-demo/files/gpio-demo.c) (MIT) использует `/dev/input/event0` и `/sys/class/leds/led-green`; на текущем Linux `/proc/bus/input/devices` пуст, драйвер gpio-keys в его DTB не подтверждён. Наша программа опрашивает прямые PS GPIO sysfs и не требует нового bitstream или kernel modules.

## Безопасность

- Выводы **только входы**: программа не пишет в `direction` и не управляет LED.
- Если GPIO уже настроен не как `in`, программа прекращает тест.
- `export` и `unexport` динамически создают/убирают sysfs GPIO; это изменения **состояния работающего ядра в RAM**, а не NAND или прошивки.
- Если `export` занят другим драйвером, программа не вытесняет его.
- Сигналы трактуются как **active-low** по стороннему DT; подтвердить нажатия на реальной плате.
- Не тестировать произвольные MIO, особенно NAND/bootstraps. Не пробовать пока LED 960/961: EMIO соединения в текущем PL не установлены.

## Сборка на ПК (WSL2, ранее установлен gcc-arm-linux-gnueabihf)

```sh
git pull
cd software/ebaz23-gpio-demo
make clean && make check
sha256sum build/ebaz23-gpio-buttons
```

Доставить ELF на плату по SSH/SFTP **в существующий достаточный по размеру RAM-backed mount** (например созданный раньше `/dev/ebaz20-ram`, предварительно проверить `mount`). Не переносить статический ELF в 64 KiB tmpfs на `/dev` и не записывать в NAND. Перед тестом убедиться, что загружен бинарник с тем же SHA-256.

```sh
mount | grep ebaz20-ram
chmod +x /dev/ebaz20-ram/ebaz23-gpio-buttons
/dev/ebaz20-ram/ebaz23-gpio-buttons --help
/dev/ebaz20-ram/ebaz23-gpio-buttons --seconds 25
echo GPIO_TEST_EXIT=$?
```

В течение 25 секунд по очереди нажать S2, S3 по 1–2 раза. Если появляются `PRESSED` при нажатии и `RELEASED` при отпускании — подтвердить GPIO-карту. `PASS_SOFTWARE_ONLY` в конце **не означает** проверки кнопок, если события отсутствуют; изучить счётчики `S2 presses=N; S3 presses=M`.

## Что дальше

После S2/S3 PASS — отдельная программа-драйвер состояний с регулированием периода мигания зелёного LED6G. Сначала требуется найти LED sysfs в текущем Linux, затем проверить EMIO0/EMIO1 на реально загруженном bitstream. Не подменять исходник KeitetsuWorks и не объявлять его demo установленным у нас.

## Наблюдения с текущей платы

- `/proc/bus/input/devices`: пуст.
- `/sys/class/mmc_host/mmc0`: присутствует; `/dev/mmcblk*`: отсутствует на момент проверки (SD-карта ещё не обнаружена).
- `dmesg`: SDHCI контроллер e0100000.sdhci, DMA.
- `/sys/kernel/debug/gpio`: пусто или debugfs не смонтирована; это не признак отсутствия аппаратного контроллера.
- `gpiochip906`: base=906, ngpio=118, label=zynq_gpio.

## Источники

- [KeitetsuWorks gpio-demo.c](https://github.com/KeitetsuWorks/EBAZ4205/blob/master/linux/ebaz4205/project-spec/meta-user/recipes-apps/gpio-demo/files/gpio-demo.c)
- [KeitetsuWorks GPIO Device Tree](https://github.com/KeitetsuWorks/EBAZ4205/blob/master/linux/ebaz4205/project-spec/meta-user/recipes-bsp/device-tree/files/ebaz4205.dtsi)
- [Наши PS MIO/EMIO карты](../../docs/EBAZ-23_PS_MIO_EMIO_AVAILABLE_PINS_RU.md)
