# ZX_BulbuLator — проверка первоисточника и применимость к EBAZ4205

**Статус:** REFERENCE (исходники третьего лица проверены в GitHub); **на нашей 660269A_Y13 электрических и PL-тестов пока нет**.

Авторский проект: [Alex-Electron/ZX_BulbuLator](https://github.com/Alex-Electron/ZX_BulbuLator).
Маршрут наших лабораторий (НЕ та же нумерация): [LAB-01…07](../tutorials/README.md).
Карточка нашей платы: [660269A_Y13](../hardware/adapters/660269A_Y13/README.md).

## Опубликованная автором карта LED/KEY

| Обозначение в таблице автора | FPGA package pin | Логический уровень | Где подтверждено |
|---|---|---|---|
| LED1 | D18 | HIGH | Step 0, раздел «Справочная информация по плате расширения»; Step 1 XDC |
| LED2 | H18 | HIGH | Step 0; Step 1 XDC |
| LED3 | E19 | HIGH | Step 0 (не используется в XDC Step 1/2) |
| LED4 | K17 | HIGH | Step 0 (не используется в XDC Step 1/2) |
| KEY1 | P19 | LOW | Step 0; Step 2 XDC как btn0 |
| KEY2 | T19 | LOW | Step 0; Step 2 XDC как btn1 |
| KEY3 | U20 | LOW | Step 0; Step 2 XDC как btn2 |
| KEY4 | U19 | LOW | Step 0; Step 2 XDC как btn3 |

**Уточнение источника:** [Step 2 README.ru](https://github.com/Alex-Electron/ZX_BulbuLator/blob/main/research/02-buttons-and-leds/README.ru.md) прямо предупреждает, что надписи KEY1–KEY4 на физическом шилде могут не совпасть с порядком подключённых BGA-контактов. Поэтому карта ниже относится к назначению выводов FPGA в авторском проекте, **не является прозвонкой нашего адаптера**.

См. также [авторский Step 0 (RU)](https://github.com/Alex-Electron/ZX_BulbuLator/blob/main/research/00-setup/README.ru.md),
[Step 1 blink.xdc](https://github.com/Alex-Electron/ZX_BulbuLator/blob/main/research/01-board-bringup-blink/blink.xdc) и
[Step 2 buttons_leds.xdc](https://github.com/Alex-Electron/ZX_BulbuLator/blob/main/research/02-buttons-and-leds/buttons_leds.xdc).
[Машиночитаемая справочная таблица](../hardware/adapters/660269A_Y13/ZX_BULBULATOR_REFERENCE_PINMAP.csv).

## HDMI — вариант автора «family B»

[Авторский HDMI XDC](https://github.com/Alex-Electron/ZX_BulbuLator/blob/main/research/03-hdmi-bars/hdmi_bars.xdc)
задаёт: Clock p/n = F19/F20; Data0 p/n = D19/D20; Data1 p/n = C20/B20; Data2 p/n = B19/A20; IOSTANDARD TMDS_33. Автор специально предупреждает о другой несовместимой разводке HDMI (family A). Наш переходник 660269A_Y13 пока не имеет электрически подтверждённой схемы: **ни family B, ни семейство A не считать нашей доказанной конфигурацией**.

## Реальные Step 1–7 авторского ZX_BulbuLator

| Шаг автора | Реализация в репозитории | К чему применить у нас |
|---|---|---|
| [Step 1](https://github.com/Alex-Electron/ZX_BulbuLator/tree/main/research/01-board-bringup-blink) | Два LED D18/H18 в противофазе, STARTUPE2/CFGMCLK без PS | Базовый тест PL через JTAG |
| [Step 2](https://github.com/Alex-Electron/ZX_BulbuLator/tree/main/research/02-buttons-and-leds) | 4 входа P19/T19/U20/U19 управляют **двумя** LED, с синхронизаторами и PULLUP | Наш LAB-05: затем расширить до четырёх LED |
| [Step 3](https://github.com/Alex-Electron/ZX_BulbuLator/tree/main/research/03-hdmi-bars) | 720p цветовые полосы через HDMI, PS FCLK0 | Наш LAB-06, после прозвонки TMDS |
| [Step 4](https://github.com/Alex-Electron/ZX_BulbuLator/tree/main/research/04-hdmi-buttons) | Кнопки переключают HDMI-тестовые изображения | LAB-06, второй этап |
| [Step 5](https://github.com/Alex-Electron/ZX_BulbuLator/tree/main/research/05-hdmi-beep) | Генерация аудио по HDMI, звуковой сигнал при отскоке квадрата | Будущая аудиолаборатория |
| [Step 6](https://github.com/Alex-Electron/ZX_BulbuLator/tree/main/research/06-zx-spectrum-128) | ZX Spectrum 128, HDMI+звук, SD boot | Будущий ретропроект, не первый аппаратный тест |
| [Step 7](https://github.com/Alex-Electron/ZX_BulbuLator/tree/main/research/07-arm-control-plane) | AXI control plane: ARM останавливает Z80, читает/пишет память Spectrum | Наш LAB-07 как пример отдельного AXI IP |

**Нумерации не смешивать:** наш LAB-01 — UART/Linux, а авторский Step 1 — FPGA LED. Наш LAB-05 — первая собственная лаборатория для нового переходника.

## Измерения до реализации

1. Прозвонить при выключенном питании сигнальные цепи кнопок, диодов, HDMI и разъёмов DATA; сохранить реальные выводы отдельно от REFERENCE.
2. Измерить питание, установить банк PL и допустимые стандарты I/O.
3. Сверить реальную ориентацию кнопок и LED относительно назначений FPGA; возможна перестановка логических имён.
4. Для PL теста подготовить JTAG и UART. На нашей NAND Linux Ethernet зависит от штатного PL; новый PL может отключить SSH. Нельзя программировать mtd5/NAND или boot straps без отдельного плана восстановления.
5. Тестировать сначала минимальную конфигурацию и фиксировать результаты. Не объявлять физический PASS по одной успешной симуляции RTL или по чужому XDC.

## Авторские права

Ссылки, фактологические данные о контактах и этапах — справочная информация. HDL в нашей новой LAB-05 написан независимо, **не является копией** исходников ZX_BulbuLator. Для прямого заимствования кода сохранять условия лицензии конкретного источника.
