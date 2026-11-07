# EBAZ-21 — Атлас внешних проектов EBAZ4205 и план повторного использования

> **Актуализация справочника (07.11.2026):** Ранние разделы этого атласа отражают состояние исследования **до аппаратных проверок SD и SW2/SW3**. На нашем экземпляре SD и кнопки теперь имеют PASS; актуальная [матрица](VERIFICATION_MATRIX_RU.md). Все ссылки на проекты других авторов являются источниками для изучения, **не доказательством совместимости с заводским bitstream**.

**Дата исследования:** 2026-11-07. **Наш репозиторий:** https://github.com/AIDevelopersMonster/EBAZ4205

## Принцип оценки

Баллы 1–5 — инженерная *полезность для нашего уже работающего экземпляра* (Linux 4.6.0-xilinx, NAND, SSH, проверенные UARTLite и чтение AXI BRAM), а не популярность GitHub. Наличие проекта не доказывает совместимость с каждой ревизией платы. При любом заимствовании проверять лицензию, версию Vivado, питание, тактирование и Ethernet через EMIO.

| Приоритет | Проект и постоянная ссылка | Что внутри | Что брать / как улучшить | Ограничение |
|---|---|---|---|---|
| **5/5** | [xjtuecho/EBAZ4205](https://github.com/xjtuecho/EBAZ4205) | Базовая аппаратная документация, [PDF-схема](https://github.com/xjtuecho/EBAZ4205/blob/master/HW/ebaz4205/EBAZ4205-SCH.pdf), [PCB/Altium/KiCad](https://github.com/xjtuecho/EBAZ4205/tree/master/HW/ebaz4205), NAND/U-Boot, Wiki | Эталонное досье платы; сверить ревизию, банки, разъёмы, режимы BOOT. MIT | Не все компоненты установлены на каждой плате; PDF опубликован, не подтверждено наличие исходной редактируемой принципиальной схемы |
| **5/5** | [darktjm/ebaz](https://github.com/darktjm/ebaz) | [ebaz.xdc](https://github.com/darktjm/ebaz/blob/master/ebaz.xdc), [ebaz-eth.v](https://github.com/darktjm/ebaz/blob/master/ebaz-eth.v), zynq-ps7.v, clock PLL, примеры и платы расширения | Эталонная таблица контактов и минимальный Ethernet-мост EMIO/MII; сделать модуль Ethernet + PHY clock с автоматической проверкой конфликтов XDC | Не найден LICENSE в корне: код **не копировать** в наш публичный проект до выяснения разрешения. Есть конфликт DATA2_4/5 и вариации плат |
| **5/5** | [KeitetsuWorks/EBAZ4205](https://github.com/KeitetsuWorks/EBAZ4205) | Vivado + PetaLinux 2021.2, GPIO demo, плата без PHY кварца Y3 | Воспроизводимая PS/PL сборка, GPIO и тактирование IP101GA от PL; сделать независимый SD-тест, не заменять NAND | Требуется установленный microSD, SD boot strap; версия инструментов и BOM отличаются. MIT |
| **5/5** | [tomorrow56/EBAZ4205_tutorial](https://github.com/tomorrow56/EBAZ4205_tutorial) | Vivado/Vitis 2024.2, LED, кнопки, PS/PL, Ethernet, HDMI/AXI4-Lite, ST7789/LVGL; [pin CSV](https://github.com/tomorrow56/EBAZ4205_tutorial/blob/main/tutorials/ebaz4205_pin_assign.csv) | Брать идеи модульного AXI4-Lite управления, тест-паттерны, MMCM/DRP, Linux-драйвер/приложение и модульное обучение; связать с нашей BRAM-лабораторией | HDL относится к примерам/платам расширения; HDMI и LCD **не встроены** в нашу базовую плату. Тактирование N18 проверить. MIT |
| **5/5** | [nightseas/ebit_z7010](https://github.com/nightseas/ebit_z7010) | Vivado/SDK 2018.3 базовый PS-проект: DDR3, SDIO, UART1, Ethernet MII через EMIO, GPIO LED; FSBL, DT, U-Boot | Образец рабочего Ethernet/PS7 и исходных boot-конфигураций; отделить минимальное ядро PS/EMIO от наших новых AXI IP | Репозиторий обозначен GPLv3-or-later; изменения/распространение требуют соблюдения GPL. Текущая NAND-система не является его образом |
| **4/5** | [har-in-air/EBAZ4205_PETALINUX](https://github.com/har-in-air/EBAZ4205_PETALINUX) | TCL генерация Vivado, PetaLinux 2022.2, SD boot, изменения Y3/X5/D24 | Забрать *метод* скриптовой сборки hardware XSA → Linux; фиксировать сборочную цепочку и детерминированные проверки | На авторской плате допаяны компоненты; LICENSE в корне не найден |
| **4/5** | [dave18/EBAZ4205-Daughter-Board](https://github.com/dave18/EBAZ4205-Daughter-Board) | Плата расширения: VGA, PS/2, SD, шаг контактов 2.54 мм, Gerber/схема | Взять концепцию переходника DATA→2.54 мм, разнести питание/сигналы и пометить контакты, добавить защиту | Для SD/PS2 нужны схемы питания и переделки 3.3 В; не повторять пайку вслепую; LICENSE в корне не найден |
| **4/5** | [alexlargacha/ebaz4205_fpga](https://github.com/alexlargacha/ebaz4205_fpga) | Vivado 2018.3, TCL создания проекта, HDL top/wrapper, constraints | Второй независимый источник методики восстановления аппаратного проекта; сравнить XDC и настройку IP | Реальную совместимость с нашим bitstream не установили; LICENSE в корне не найден |
| **3/5** | [Stavros/ebaz4205](https://github.com/Stavros/ebaz4205) | PetaLinux/Vivado 2019.1 и образ PYNQ/Jupyter | Идея удалённой Python-лаборатории FPGA; сравнить минимальный пользовательский интерфейс с тяжёлым Jupyter | 256 МиБ DDR и старые зависимости ограничивают применимость; только отдельный SD-образ; в README автор указывает GNU Licence |
| **3/5** | [ZX_BulbuLator](https://github.com/Alex-Electron/ZX_BulbuLator) | Пример большого проекта ретро-компьютера для EBAZ4205 | Возможный дальний ориентир для KonSol: видео, управление, внешние устройства; оценить расход BRAM/LUT | Большая сложность, привязка к плате расширения/ревизии; не базовый этап |
| **3/5** | [Hackaday: EBAZ4205 HDMI](https://hackaday.io/project/189164-fpgahdmi-up-to-1920x108060hz-for-35) | Физическая демонстрация вывода HDMI на EBAZ4205 | Идея компактной видеолаборатории после стабилизации PS/PL | Встроенного HDMI-разъёма на штатной плате нет; требуется переходник и корректная электрика/тайминг |

Дополнительные постоянные справочники: [распиновка mwalle](https://gist.github.com/mwalle/d8291e241075d82d1d420afa9302bd91), [xjtuecho Hardware Build States](https://github-wiki-see.page/m/xjtuecho/EBAZ4205/wiki/Hardware-Build-States.-What-you-may-or-not-have-fitted-on-your-board.), [JTAG/bitstream guide](https://github-wiki-see.page/m/xjtuecho/EBAZ4205/wiki/JTAG-configuration-and-bitstream-downloading-guide), [CodeAsm board notes](https://gist.github.com/CodeAsm/57d5856370546adbc41941ca716988f8).

## Разбивка на независимые повторно используемые блоки

| Блок | Источник | Наш статус | Правильное улучшение |
|---|---|---|---|
| A. Надёжная загрузка, сохранение NAND | Наши EBAZ-19/20 + xjtuecho + nightseas | Рабочий NAND rootfs, SSH, UART, RAM rescue описаны в нашем репо | Сохранить штатный NAND/bootloader/bitstream как контрольную точку; изменения тестировать отдельно на SD/в RAM |
| B. PS7 DDR/UART/SDIO/GEM | nightseas / KeitetsuWorks / har-in-air | DDR/UART/Ethernet под Linux работают, SD-разъём на *нашем* экземпляре не подтверждён | Автогенерация PS7 конфигурации, device tree, таблица конфликтов MIO/EMIO |
| C. Ethernet PHY/MII/EMIO и 25 MHz | darktjm / KeitetsuWorks / nightseas | Ethernet работает в текущем PL | Минимальный Ethernet-safe baseline, отдельная проверка варианта Y3 установлен/не установлен |
| D. Аппаратный паспорт и XDC | xjtuecho / mwalle / darktjm / tomorrow56 | Физическую ревизию платы ещё не сверяли по фото | Единый CSV pin → connector → bank → reserved/conflict/status, тесты XDC |
| E. UARTLite в PL | Наш EBAZ-20 | /dev/ttyUL2 0x42C00000, прежний обмен подтверждён | Протокол с версией, CRC, диагностикой, без перезаписи PL |
| F. AXI BRAM 8 KiB | Наш EBAZ-20 | 32 слова/128 байт *прочитаны* из 0x40000000 | В **собственном новом** проекте — mailbox/version/capabilities/handshake и тест без изменения штатной BRAM |
| G. AXI4-Lite управление новыми IP | tomorrow56 | Не реализовано в текущем проекте EBAZ | Компактный register map, write/readback, timeout, watchdog, тестбенч |
| H. Дисплей и игры | tomorrow56 / dave18 / Hackaday / ZX_BulbuLator | Физически не установлены/не проверены | Отдельная mezzanine-плата с безопасным питанием, видео и управлением |
| I. PYNQ / Python web UI | Stavros | Не развёрнуто | Рассмотреть после минимального работающего FPGA и оценки RAM; альтернативой может быть лёгкий веб-интерфейс |

## Рекомендуемая очерёдность

1. Зафиксировать аппаратный паспорт и наличие компонентов по фото обеих сторон. **Не изменять штатный bitstream**.
2. Получить/проверить локальную резервную копию раздела NAND bitstream `mtd5` вне GitHub и сопоставить заголовок с примером `top_ctrl` (само наличие снимка mtd6 не равно наличию снимка mtd5).
3. Собрать минимальный Vivado проект **вне штатной NAND** на базе PS/EMIO с сохранением Ethernet; сначала лишь синтез, XDC pin conflict checks и отчёт ресурса.
4. Добавить собственные AXI BRAM/mailbox и AXI4-Lite control IP с тестбенчем; осторожный аппаратный тест после обеспечения UART/JTAG recovery.
5. Разработать переходник DATA1–3 с индивидуальной проверкой напряжений, затем выбрать HDMI/LCD/VGA/игровую периферию.

## Правила происхождения и заимствования

- Таблицы сигналов и ссылки могут использоваться как справочные сведения, но перед платой расширения требуется сверка с оригинальной схемой и фактическим экземпляром.
- Лицензии: xjtuecho, KeitetsuWorks, tomorrow56 — MIT; nightseas — GPLv3-or-later; Stavros README — GNU; для darktjm, har-in-air, dave18 и alexlargacha LICENSE в корне при проверке не обнаружен. **Отсутствие LICENSE не означает свободное разрешение копировать код.**
- Не публиковать дампы NAND, заводские бинарные bitstream, закрытые ключи SSH или приватные серийные данные без отдельного правового и технического анализа.
- В проекте [EBAZ-21_BOARD_PINOUT_AND_FACTORY_FPGA_RU.md](EBAZ-21_BOARD_PINOUT_AND_FACTORY_FPGA_RU.md) сохраняется карта физических интерфейсов и границы доказанного о штатном PL.

## Актуализация 2026-11-07 — навигация и новые проверенные результаты

**Это канонический единый каталог сторонних разработок EBAZ4205.** Ссылка на него уже имеется в корневом [README](../README.md), раздел «EBAZ-21 — внешние проекты, схемы, порты и FPGA». Технические детали по отдельным узлам находятся в [EBAZ-21 аппаратная карта](EBAZ-21_BOARD_PINOUT_AND_FACTORY_FPGA_RU.md) и [EBAZ-23 PS MIO/EMIO](EBAZ-23_PS_MIO_EMIO_AVAILABLE_PINS_RU.md). Они не заменяют настоящий каталог.

**Фактические обновления относительно исторической таблицы выше:**
- На **нашем** экземпляре microSD уже работает под **NAND Linux 4.6** без смены boot strap: `mmc0: new high speed SDHC card`, `SC16G 14.8 GiB`, `/dev/mmcblk0p1`, FAT/VFAT и автоматическое монтирование в `/run/media/mmcblk0p1`. Пометка «SD не подтверждён» в разделе B выше теперь устарела.
- Оба PS MIO входа SW2 (MIO20, Linux GPIO926) и SW3 (MIO32, GPIO938) **проверены физическим нажатием**. Совместимая с BusyBox версия теста запущена **прямо с SD**: [sdcard/EBAZ4205/tests/buttons](../sdcard/EBAZ4205/tests/buttons/README.md), `EBAZ23_SD_BUTTONS_V02_PASS`.
- У нас подтверждён **только факт обнаружения/автомонтирования SD и запуска теста**; hotplug, перенос Linux rootfs на SD и использование SD вместо NAND как boot device — другие, не выполненные опыты.

### Другие известные открытые разработки, полезные для следующих этапов

| Проект | Конкретный объект изучения | Что НЕ переносить без проверки |
|---|---|---|
| [trebisky/ebaz4205_miner](https://github.com/trebisky/ebaz4205_miner) | Экспериментальные PL-дизайны `blink1` (автономное LED) и `blink2/axi_gpio.c` (управление LED через AXI GPIO); пример разделения ARM↔PL | AXI GPIO **0x41200000 относится к авторскому bitstream**, его существование в заводском PL не подтверждено; не читать/писать этот MMIO-адрес на нашей работающей плате |
| [embed-me/meta-ebaz4205](https://github.com/embed-me/meta-ebaz4205) и [ebaz4205_buildroot](https://github.com/embed-me/ebaz4205_buildroot) | Независимые системы и примеры управления LED | Их собственная ОС, Device Tree и LED-логика **не** описывают автоматически нашу штатную NAND-систему |
| [tonyho/EBAZ4205-Minimum-Board-Operating-Configuration](https://github.com/tonyho/EBAZ4205-Minimum-Board-Operating-Configuration) | Фотографии и минимальный вариант запуска EBAZ4205; ориентир при идентификации элементов PCB | Не считать совпадение фотографии гарантией установленной обвязки и ревизии |
| [Elrori/EBAZ4205](https://github.com/Elrori/EBAZ4205) | Опубликованная разводка платы `ebit.pcb` (уже упоминалась в аппаратной карте) | Для производства/переработки и опубликования производных файлов требуется отдельно проверить происхождение и права |
| [torvalds/linux — zynq-ebaz4205.dts](https://github.com/torvalds/linux/blob/master/arch/arm/boot/dts/xilinx/zynq-ebaz4205.dts) | **Это не сторонний проект-прошивка**, а справочный upstream Device Tree, включая SDIO0 и MIO-кнопки | Linux mainline DTS не идентичен DTB нашего заводского PetaLinux 2016.4 |

**Источник и лицензия:** в расширенной таблице выше не выполнялась новая независимая проверка лицензий каждого дополнительно названного проекта. До копирования HDL, ПО, платы или текста проверять конкретный файл LICENSE, правообладателя и условия распространения.

**Новая навигационная норма:** все новые сторонние EBAZ4205-проекты первоначально добавлять **в этот атлас** (название, ссылка, оборудование/ОС, статус проверки, применимость, лицензия); только затем включать необходимые отдельные сведения в EBAZ-21/23 и рабочие лаборатории. Не плодить конкурирующие каталоги.
