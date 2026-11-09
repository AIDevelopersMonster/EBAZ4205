# EBAZ-28 — безопасная загрузка Linux с отсутствующей PL и поэтапным возвратом периферии

**Дата:** 2026-11-09. **Статус:** архитектурное решение / подготовка аудита; экспериментальный DTB, новая PL, драйверы-заглушки, аппаратные тесты **не созданы и не проверены**. Не путать с `EBAZ27_*_PASS`: EBAZ-27 дал доказательства *частичной физической маршрутизации*, не готовую PL.

## Цель

На базе действующей EBAZ4205/XC7Z010 (Linux 4.6.0-xilinx, PetaLinux 2016.4, NAND/JFFS2, PS UART) получить минимальный, **контролируемый холодный старт**, при котором отсутствие большей части заводской PL не вызывает попыток доступа драйверов и программ к отсутствующим AXI/EMIO-устройствам. Затем постепенно вернуть совместимые аппаратные блоки без переноса майнинговой логики.

**Не подменять назначение:** «Linux успешно загрузился» ≠ «прошивка полностью восстановлена». Полная прошивка включает согласованные PS init/FSBL, U-Boot, Linux kernel, DTB, rootfs, PL bitstream и физическую обвязку платы.

## Аппаратный инвариант

| Объект | Достоверно известно из EBAZ-20/21/25 | Правило |
|---|---|---|
| PS7 / DDR3 | 256 MiB номинально, MemTotal ~246 MiB, Linux работает | PS DDR controller и init от FSBL/U-Boot должны **сохраниться**. Это не логика, заменяемая PL-заглушкой |
| PS UART | `ttyPS0`, штатный TTL 3.3 V | Основной recovery и boot console, независимый от UARTLite |
| NAND / JFFS2 | `mtd5` — заводской bitstream; `mtd6` — рабочая 64 MiB JFFS2; есть резервные копии | **Не** изменять NAND, U-Boot environment и FSBL в начальных фазах |
| AXI BRAM controller | `0x40000000–0x40001FFF`, DT `xlnx,axi-bram-ctrl-4.0`, EXTERNAL, 2048×32; ARM только читал 128 байт | Не делать MMIO без подтверждённого ответчика AXI; активного bound kernel driver по EBAZ-20 нет |
| UARTLite | `0x42C00000`, `/dev/ttyUL2`, Linux драйвер `uartlite`, IRQ 166 | В PS-only DT временно отключить; не делать фиктивный успешный UART |
| Ethernet | PS GEM0 через PL EMIO/MII/MDIO → PHY IP101G; PHY clock зависит от реальной обвязки | В PS-only boot **не рассчитывать на Ethernet/SSH**; вернуть ранним реальным аппаратным этапом |
| FAN J3/J5 | Справочная разводка: J3 PWM U12/SPEED V13, J5 PWM V12/SPEED V15 | Отсутствие PL может изменить вращение вентиляторов! До холодного boot испытания обеспечить физически безопасное питание/управление и контроль температуры |
| ASIC | Заводская специфическая майнинговая логика не нужна новой системе | Не переносить |

## Первый реальный аппаратный рубеж — LED + PS UART + устойчивый Linux (EBAZ-28.1A)

**Решение:** первый пользовательский образ PL должен быть максимально малым, с двумя штатными LED (по референсному EBAZ-21 XDC: зелёный W13, красный W14, **active-low**, проверить назначение конкретной ревизии платы), но не должен прерывать работу PS UART/DDR. Отсутствующие PL устройства **не должны перечисляться как действующие** в тестовом DTB.

Две стандартные топологии, выбор после проверки реального DT/конфигурации ядра:

**Вариант A — минимальный и более безопасный для первого cold boot: PS GPIO → EMIO → PL output pins → LED.** Контроллер GPIO уже расположен в PS на `0xE000A000`, специальный AXI slave не нужен, Linux использует `gpio-zynq` (проверить `CONFIG_GPIO_ZYNQ` и действующий gpiochip). В PL требуются только маршруты EMIO GPIO к W13/W14, без AXI interconnect; изменения PS7 MIO/UART/DDR должны быть исключены или проверены побитно/регистрово. Это всё ещё требует отдельного корректного PL bitstream и подтверждённой раскладки GPIO EMIO в действующем DT.

**Вариант B — требуемая полноценная периферия в PL: PS M_AXI_GP0 → AXI Interconnect → AXI GPIO (2 output) → W13/W14.** АХI GPIO имеет стандартный driver `gpio-xilinx` с обычным `compatible = "xlnx,xps-gpio-1.00.a"` для старых ядер, **не путать** с именем IP `axi_gpio`. Адрес (например, `0x41200000`) лишь **предложение**, не заводской адрес: выбрать после проверки полной карты MMIO/AXI. В Device Tree нужен верный `reg`, `gpio-controller`, `#gpio-cells = <2>`, clocks и свойства контроллера, и два LED под `compatible = "gpio-leds"`, `gpios = <&... 0/1 GPIO_ACTIVE_LOW>`. Для доступности через `/sys/class/leds` нужно подтвердить `CONFIG_GPIO_XILINX`, `CONFIG_LEDS_GPIO`, `CONFIG_LEDS_CLASS` в **реальном** Linux 4.6; их наличие не доказывается существованием документации. Никакого AXI-GPIO DT node до появления работающего AXI slave в соответствующем адресе; иначе риск MMIO hang.

**Последовательность испытаний:** 1) read-only snapshot kernel config/device tree/driver/clock/address + возможность RAM-only cold boot/recovery; 2) HDL offline synth/place/route/DRC/STA и XDC; 3) при надёжном UART и безопасном питании/охлаждении загрузить пробный bitstream через U-Boot **до старта Linux**, без записи NAND, альтернативный DTB с выключенными недоступными AXI UARTLite, BRAM, GEM0/EMIO Ethernet (включить после возврата PHY); 4) проверить `ttyPS0` логин, DDR, стабильность Linux и GPIO LED; 5) при желании заменить PS GPIO EMIO на стандартный AXI GPIO, добавить LED trigger heartbeat. **Нельзя** называть наличие светодиодов защитой от ошибок шин AXI: драйверы и другие программы не должны обращаться к незавершённым PL адресам.

**Важно:** при PS-only отсутствии PL определённость PWM вентиляторов отдельно не гарантирована. Перед испытанием обеспечить безопасное охлаждение, не выводить логические уровни вентиляторов «по умолчанию» из предположений. Предварительное состояние: `EBAZ28-LED-PSUART-BOOT=PENDING`.

Проверенные внешние интерфейсы: документация Xilinx `Documentation/devicetree/bindings/gpio/gpio-xilinx.txt` для Linux 4.x, `leds-gpio.txt`, Xilinx Zynq GP GPIO/EMIO tutorial и AMD UG585.

## EBAZ-28.1B — стандартный AXI GPIO вместо LED blinker: локальный статический PASS (2026-11-09)

На CHUWI пользователь развернул `EBAZ28_AXI_GPIO_first_boot.zip` в `$HOME\\EBAZ4205` и выполнил `py hardware/ebaz28-axi-gpio/contract_test.py` — **15 проверок PASS**, итог **`EBAZ28_AXI_GPIO_CONTRACT_CHECK_PASS (STATIC ONLY, NOT VIVADO)`**. Этот тест сверяет статические текстовые признаки Tcl/XDC/DT, а не строит схему FPGA и не гарантирует работу Linux. В локальном комплекте также имеются `add_axi_gpio_to_ps7.tcl`, `ebaz28_leds_reference.xdc`, `ebaz28-axi-gpio-legacy.dtsi.in`, `read_only_target_inventory.sh`, `README_RU.md`. Эти файлы **локально распакованы**, но их наличие в публичной истории GitHub пока не установлено.

**Выбранный контракт:** PS7 `M_AXI_GP0` → AXI Interconnect → **Xilinx AXI GPIO v2.0** (2 output bits, no IRQ). Предлагаемая новая база MMIO **`0x41200000`**, регистры `GPIO_DATA+0x00`, `GPIO_TRI+0x04`; reset DATA=`0x3` (active-low LEDs оба OFF), TRI=`0x0` (output). Бит 0: красный W14, бит 1: зелёный W13 **по референсному XDC**, физическую ревизию и напряжение PL bank подтвердить до программирования. Аппаратной мигалки, счётчика, heartbeat или заданного периода **нет**. Доступ: стандартный kernel gpio-xilinx; существующий Linux 4.6 — `/sys/class/gpio`, при соответствующих CONFIG; `gpio-leds` опционален и занимает выводы как клиент.

**Тонкость спецификации PG144:** для GPIO, настроенного как output, чтение `GPIO_DATA` не обязательно отражает записанный логический уровень (PG144 описывает чтение нулей для выходных битов). Поэтому `mmap()/devmem` readback DATA нельзя считать аппаратным доказательством фактического состояния LED; использовать драйверную модель и/или проверку физического уровня, сохраняя раздельную диагностику.

**Гейты перед загрузкой:** проверить физический PS UART, штатный PS7/DDR3 init, полный Device Tree и реально доступный `CONFIG_GPIO_XILINX`, свободный новый AXI диапазон, Vivado `validate_bd_design` / synth / place-route / DRC / STA, отсутствие AXI проб из Linux к несуществующим адресам; отдельный DTB для теста с отключёнными зависимыми устройствами; наличие безопасного управления вентиляторами и сценария **cold** recovery. Никаких hot `/dev/xdevcfg` и записей NAND. Все Vivado/DTB/FPGA/boot проверки **PENDING**.

Следующий **read-only** шаг: выполнить на штатной Linux через PS UART `hardware/ebaz28-axi-gpio/read_only_target_inventory.sh` (либо его команды вручную, без копирования в NAND), собрать реальные сведения о gpiochip, driver bindings, bootargs, ttyPS и MMIO map.

## EBAZ-28.1C — анализ Linux 4.6 GPIO/PS UART/MMIO: READ-ONLY PASS (плата, 2026-11-09)

По действующей заводской системе `root@zedboard-zynq7` получен следующий реальный **read-only** вывод:

- `uname -a`: `Linux zedboard-zynq7 4.6.0-xilinx #5 SMP PREEMPT Mon May 8 14:36:49 CST 2017 armv7l`.
- `/proc/cmdline`: `console=ttyPS0,115200 root=/dev/mtdblock6 rootfstype=jffs2 noinitrd rw rootwait` — основная консоль и загрузка NAND JFFS2 не должны нарушаться.
- `/dev/ttyPS0`, `/dev/ttyPS1` существуют; `/proc/iomem` содержит PS UART `e0000000-e0000fff` и `e0001000-e0001fff`.
- `/sys/class/gpio` существует, зарегистрирован `gpiochip906` → `/devices/soc0/amba/e000a000.gpio/gpio/gpiochip906` (**PS Zynq GPIO**, а не новый AXI GPIO в PL). `/proc/iomem` показывает `e000a000-e000afff`.
- `/proc/config.gz` подтверждает `CONFIG_GPIOLIB=y`, `CONFIG_GPIO_SYSFS=y`. В выводе фильтра `CONFIG_GPIO_XILINX` нет; каталог `/sys/bus/platform/drivers/gpio-xilinx` отсутствует. **Стандартный драйвер для PL AXI GPIO в текущем ядре не обнаружен**, несмотря на работоспособность подсистемы GPIO. Драйвер доступен в Linux 4.6 через `CONFIG_GPIO_XILINX` и имеет совместимость DT `xlnx,xps-gpio-1.00.a`. Для PL AXI GPIO потребуется модуль, собранный под точную конфигурацию ядра при `CONFIG_MODULES=y`, либо альтернативное ядро с поддержкой.
- `/proc/iomem`: `42c00000-42c0000f : uartlite`, `e000b000-e000bfff : /amba/ethernet@e000b000`; `0x41200000` *не перечислен*, но отсутствие диапазона в `/proc/iomem` **не доказывает**, что он не занят в физической карте или разрешён для нового IP. Требуется проверка Device Tree, AXI memory map и PS7 design.
- DDR3 работоспособна при текущем заводском PS init; **не изменять** настройки DDR в новой PL и не делать выводов о допустимости полного PS7 replacement без проверки.

**Решение**: сохранить стандартный **PL Xilinx AXI GPIO v2.0**, `M_AXI_GP0` → AXI Interconnect → `AXI GPIO`, proposed base `0x41200000`, output bits 0/1 → W14/W13 (active-low, сверить на реальной PCB). Отсутствие драйвера не повод переходить на blink/counter или нестандартное ПО. Для первого теста при условии безопасного cold boot GPIO можно держать выключенным в DT, а поддержанный драйвер добавить после отдельной проверки. Не делать `devmem` по адресу будущего PL до появления подтверждённого AXI slave.

**Следующий read-only контроль** (из работающей системы): `cat /sys/class/gpio/gpiochip906/base`, `cat /sys/class/gpio/gpiochip906/ngpio`, `cat /sys/class/gpio/gpiochip906/label`; `zcat /proc/config.gz | grep -E 'GPIO_XILINX|GPIO_ZYNQ|MODULES|OF_GPIO|OF_DYNAMIC'`; `ls -la /sys/bus/platform/drivers | grep -i gpio`; `ls /lib/modules/$(uname -r) 2>/dev/null`; `ls /proc/device-tree/amba_pl`; `cat /proc/mtd`. Только чтение — **не** `echo N > /sys/class/gpio/export` и **не** `devmem`.

Контроль состояний: `EBAZ28_FACTORY_LINUX_GPIO_BASELINE_PASS` = установлен действующий PS GPIO и GPIO framework; `EBAZ28_AXI_GPIO_KERNEL_DRIVER_PASS` = **PENDING**; `EBAZ28_NEW_PL_BOOT_PASS` = **PENDING**; `EBAZ28_LINUX_GPIO_BOOT_PASS` = **PENDING**. Безопасный вентилятор/PS-UART recovery и отдельный DTB — обязательные условия перед заменой заводской PL.

## Три различных вида заглушек (не смешивать)

1. **DTB-safe (первый выбор):** в *альтернативном*, отдельно загружаемом DTB пометить зависимые PL-узлы `status = "disabled"`; до проверки точных путей live DT не писать готовые overlay/DTS адреса по памяти. Так не создаются соответствующие platform devices и не запускаются обычные `probe()` в Linux. Отдельно проверить GEM0 (это PS IP, но его физические линии идут через EMIO/PL), UARTLite, возможные прочие неизвестные PL потребители. Пустой `/proc/modules` **не значит**, что драйверов нет: часть встроена в ядро.
2. **Software shim/diagnostic stub (по необходимости):** пользовательский shim или тестовый драйвер для заведомо обнаруженного потребителя. Не объявлять оборудование функционирующим, не возвращать фальшивые `READY`/успех/данные. Для неподдержанного доступа сообщать `ENODEV`/`EOPNOTSUPP` либо ограниченную согласованную модель с таймаутами; `-EPROBE_DEFER` может приводить к повторным probe и не является универсальным escape.
3. **Аппаратная AXI4-Lite-заглушка в новой PL:** только после проверки карты PS/PL, clocks, reset. Реализовать корректное завершение всех каналов запросов/ответов и явный безопасный статус `NOT_PRESENT/NOT_READY` в *собственном* versioned IP. Не пытаться «выдавать» её за заводской UARTLite/BRAM с несовместимыми регистрами. AXI error `SLVERR/DECERR` допустим только при осознанном поведении CPU/драйвера; ошибка на `/dev/mem` сама может породить exception. Отсутствие AXI slave на PS→PL пути потенциально блокирует CPU и не исправляется программной заглушкой после обращения.

**Важный риск:** при `/dev/xdevcfg` в старой Linux происходил сброс PL и зависание; «driver stubs» не делают это безопасной операцией, особенно при работе GEM0/EMIO и доступах CPU к PL. **Запрет hot-reload PL**, как минимум до отдельной разработки reset isolation/quiesce.

## Профили boot и последовательность

### EBAZ-28.0: baseline и режим recovery — только чтение

На заводской Linux через физический PS UART снять:
- `uname -a`, `cat /proc/cmdline`, `cat /proc/mtd`, `cat /proc/iomem`, `cat /proc/interrupts`.
- Доступные PL Device Tree nodes `/proc/device-tree/amba_pl/*`: `compatible`, `status`, `reg`, `interrupts`, `clocks`, `resets`, `phy-*`; `status` отсутствует → нормативно `okay`.
- Реальные platform-driver bindings в `/sys/bus/platform/devices` (отдельно `42c00000`, `40000000`, `e000b000`), `dmesg` по relevant failures и UART/IP101G/BRAM, службы/`getty`, прямые MMIO потребители.
- В лаборатории на CHUWI установить вариант безопасного *RAM-only boot* с проверенным возвратом к заводскому образу при холодном перезапуске. **Не предполагать**, что U-Boot умеет SD boot/FDT замены до просмотра его actual `help`, `printenv` и доступных kernel/DTB images.

Критерий: исходный boot и recovery видны на `ttyPS0`, сохранены адреса/драйверы/DTB, есть ручной план отката.

### EBAZ-28.1: PS-only SAFE BOOT

Использовать оригинальную **работающую** инициализацию DDR/PS от загрузчика. Создать альтернативный DTB, где **точно установленные** PL устройства и PS GEM, зависящий от PL EMIO, выключены. Временный тестовый kernel/rootfs только после проверки способа RAM-only загрузки; не трогать NAND. Даже если U-Boot не загружает PL, консоль должна быть на PS UART (требует проверки bootargs). Не считать `init=/bin/sh` достаточным: probe platform devices обычно выполняется раньше init.

Критерий `PS_ONLY_BOOT_PASS`: cold boot, интерактивная `ttyPS0`, DDR/meminfo, NAND-rootfs, нет MMIO timeout/SError/hang, устойчивость в течение контролируемого теста. Ethernet не требуется, ssh не требуется. Проверка вентиляторов — независимый stop-gate.

### EBAZ-28.2: MINIMAL AXI PL и безопасные регистры

Выпустить новую PL со стабильными PS FCLK/reset, AXI interconnect и своим простым диагностическим AXI4-Lite IP. Реальные UARTLite и BRAM включать только если сохраняется корректная карта/семантика/IRQ. Заглушка «честно не готов» лучше фальшивого READY. Если ядро отключило все PL узлы в DT, AXI dummy не обязателен для самого первого PS-only boot.

Критерий: read/write/timeout/error test на отдельном IP уже **в тестовом образе**, без воздействия на factory bitstream, DRC/STA/timing/physical test.

### EBAZ-28.3: Ethernet и обязательные контракты

Вернуть GEM0↔EMIO↔MII/MDIO↔IP101G, проверенную PHY 25 MHz с реальным pinout, затем включить соответствующий DT node. Сначала линк/carrier/PHY ID, затем DHCP/ICMP/SSH. После — AXI BRAM `0x40000000` 8 KiB и UARTLite `0x42C00000` с согласованным `clock-frequency`, IRQ и доступностью Linux. Не реиспользовать неизвестные factory BRAM данные как spec API.

### EBAZ-28.4: PWM/tach и дополнительные блоки

Проверить реальные сигналы вентиляторов; обеспечить PWM безопасной полярности, допустимые электрические уровни, watchdog/failsafe для потери управляющего такта, tach count/IRQ при необходимости. Не рассчитывать, что высокая/низкая логика обязательно соответствует полному вращению без осциллографа/проверки схемы. Затем LED/GPIO/пользовательские модули.

## Stop-gates

- **STOP** при изменении vendor PS clock/DDR init без аппаратного расчёта/валидации.
- **STOP** при отсутствии UART recovery, потере сохранённого factory NAND backup или изменении `mtd5`/`mtd6` в ранних фазах.
- **STOP** при неизвестной реакции вентилятора на отсутствие PL PWM, недостаточном охлаждении или неопределённых электрических уровнях.
- **STOP** при попытке горячего PCAP/xdevcfg во время работы Linux/EMIO или при доступах в PL.
- **STOP** при AXI-заглушке, которая возвращает фальшивый успех или удерживает VALID/READY без гарантированного завершения транзакций.
- **STOP** при непроверенных `compatible`, `reg`, IRQ и DTB заменах.
- Не объявлять `BOOT_PASS` до фактического лога CHUWI + платы. Все состояния здесь **PENDING**.

## Исходные сведения и ссылки

- [EBAZ-20 — системная инвентаризация](EBAZ-20_SYSTEM_INVENTORY_RU.md)
- [EBAZ-21 — пины и заводская PL](EBAZ-21_BOARD_PINOUT_AND_FACTORY_FPGA_RU.md)
- [EBAZ-25 — совместимая собственная PL](EBAZ-25_COMPATIBLE_PL_RECONSTRUCTION_RU.md)
- [EBAZ-27 — форензика bitstream и частичные графы](EBAZ-27_FACTORY_PL_RESOURCE_MAPPING_RU.md)
- [Devicetree Specification §2.3.4: `status`](https://devicetree-org.github.io/devicetree-specification/)
- [Linux kernel: Platform Devices and Drivers](https://docs.kernel.org/driver-api/driver-model/platform.html)
- [AMD UG585: Zynq-7000 PS/PL + DDR](https://docs.amd.com/r/en-US/ug585-zynq-7000-SoC-TRM)
