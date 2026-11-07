# EBAZ4205 Developer SD — кнопки SW2 / SW3

**Проверено на физической EBAZ4205 2026-11-07:** `EBAZ23_SD_BUTTONS_V02_PASS`.

## Размещение на комплектной microSD

Штатная Linux 4.6 загружается с NAND, а SDHC-карта с VFAT автоматически монтируется по пути `/run/media/mmcblk0p1`. Раздел был обнаружен как `/dev/mmcblk0p1` (`SC16G`, 14.8 GiB, UUID `751F-7A24`).

Тест хранится на карте в:

```text
/run/media/mmcblk0p1/EBAZ4205/tests/buttons/test-buttons.sh
```

Запуск с правами уже существующего пользователя root (новых пользователей не создаём):

```sh
sh /run/media/mmcblk0p1/EBAZ4205/tests/buttons/test-buttons.sh
```

Нажать SW2 и SW3. Выход: Ctrl+C.

## Подтверждённый результат

```text
root@zedboard-zynq7:~# sh /run/media/mmcblk0p1/EBAZ4205/tests/buttons/test-buttons.sh
Ожидание нажатий SW2 и SW3. Для выхода нажмите Ctrl+C.
Нажата кнопка SW3
Нажата кнопка SW2
Нажата кнопка SW3
Нажата кнопка SW2
```

Физические связи: SW2=MIO20=Linux GPIO926, SW3=MIO32=GPIO938 при GPIO base=906. Скрипт читает только входы, проверяет направление `in`, не выставляет output и не пишет регистры FPGA/NAND. При завершении отменяет export только для тех GPIO, которые экспортировал сам.

## Совместимость BusyBox

Первая редакция ошибочно требовала `sleep 0.1`; на заводской BusyBox это не поддерживается. Исправленная редакция проверяет `sleep 0.1`, затем `usleep`/ `busybox usleep`, иначе предупреждает о переходе на `sleep 1` (удерживать кнопку около 3 секунд). **Результат PASS относится именно к исправленному скрипту на SD.**

Отдельное сообщение `sh: xauth: command not found` связано с SSH/X11 и не относится к данному тесту.

## Статус проверок

- **PASS** — SDHC определяется при загрузке NAND Linux.
- **PASS** — VFAT auto-mounted по `/run/media/mmcblk0p1`.
- **PASS** — shell-тест SW2/SW3 запускается непосредственно с microSD и регистрирует нажатия.
- **NOT TESTED HERE** — hot insertion, запись файлов на карту в рамках процедуры испытаний, управление LED через PL, смена bitstream.

Исходный ранее проверенный C-вариант: [software/ebaz23-gpio-demo/gpio_buttons.c](../../../../software/ebaz23-gpio-demo/gpio_buttons.c).
