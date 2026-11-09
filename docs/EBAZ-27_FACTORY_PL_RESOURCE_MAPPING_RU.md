# EBAZ-27 — карта ресурсов заводской FPGA и граница полезной статической PL

**Дата:** 2026-11-09. **Статус:** EBAZ-27.7 **PASS** по журналу CHUWI: заводской .bit → FASM → полный tilegrid (физические координаты и классы плиток), отчёты JSON/CSV/SVG. Все 272 unknown-bit аннотации выделены, других неклассифицированных строк нет. Восстановление цепей, оценка реального использования ресурсов, границы статической PL и аппаратная валидация **PENDING**.

## Результат EBAZ-27.5 — первый заводской FASM

- WSL Ubuntu (CHUWI), Project X-Ray, prjxray-db, `bitread` и Python `fasm/prjxray` были подготовлены; Vivado на CHUWI не установлен и не нужен для чтения `.bit`.
- Копия `/home/alex/ebaz27-xray/factory.bit` имеет **2 083 844 байта**, контрольная SHA256 **`c94da9922272a6e8fdfe43c987f9ec85685d4409c1b9abe1e9b0ffe88490066a`** по выполненному `sha256sum`.
- `/home/alex/ebaz27-xray/factory.fasm`: **259 642 строки**, `ls -lh` показывает **8,6 МиБ** (по пользовательскому логу).
- `/home/alex/ebaz27-xray/ebaz27-fasm-survey.json` создан, финальная метка `EBAZ27_FASM_SURVEY_PASS` получена.
- Анализатор сообщил `WARNING: some non-comment lines unparsed`. **Не установлены** пока количество непарсенных строк, число неизвестных конфигурационных битов X-Ray, распределение типов признаков и фактический utilisation.
- `--verbose` при работе Project X-Ray может генерировать аннотации неопознанных битов/сегментов. Требуется изучить `unparsed_examples`, а не автоматически считать все такие строки ошибками или использованными ресурсами.
- **Запрещено:** называть отсутствие FASM-признака доказательством свободного site/tile; публиковать сам `.bit`/полный `factory.fasm` без отдельной правовой оценки; удалять или патчить заводской образ.

### Фактический отчёт первичного анализа (от пользователя, 2026-11-09)

- SHA256 `factory.fasm`: `f22e32fc1608a9cee8ce30757b7d8f2856b3a307492534b02aafa7b90738b66b`.
- Всего строк: **259 642**; строк распознанных FASM-feature: **253 962**.
- Feature-строки: INTERCONNECT **171 971**; CLB **76 158**; BRAM **4 555**; IOB **890**; CLOCK **384**; OTHER_OR_UNKNOWN **4**.
- Уникальные tiles с выраженными признаками: **5 361**; из них INTERCONNECT **3 086**; CLB **2 099**; BRAM **46**; IOB **82**; CLOCK **47**; OTHER_OR_UNKNOWN **1**.
- Нераспознанные анализатором строки: **272**, примеры от Project X-Ray вида `{ unknown_bit = "00401a9e_56_20", unknown_segment = "0x00401a80", unknown_segbit = "30_1812" }`. Их следует считать **диагностическими аннотациями неизвестных битов**, а не доказательством ошибочного синтаксиса.
- Из итогов не следует утилизация CLB/LUT/BRAM, отсутствие DSP или локализация безопасно свободного региона.
- Следующий инструмент: `tools/ebaz27-tilegrid-map.py` (консервативный отчёт по полному `tilegrid.json`, классам и неизвестным аннотациям; входной эталон SHA256 FASM встроен). Не публиковать локальную полную карту без отдельной оценки.

### Следующий шлюз EBAZ-27.6 — охват декодирования

На CHUWI извлечь из отчёта ровно следующие поля: `status`, `tiles_with_expressed_features`, `feature_line_counts_by_tile_class`, `tile_counts_by_class`, `unparsed_lines`, `unparsed_examples`. По примерам разобрать природу предупреждения; отдельно подсчитать неизвестные биты и пропущенные segbits; лишь после этого сопоставлять результат с полной базой tilegrid XC7Z010.



## EBAZ-27.7 — сопоставление заводской конфигурации с полным tilegrid (2026-11-09)

Подтверждён пользовательским выводом `tools/ebaz27-tilegrid-map.py` на CHUWI:

| Класс tilegrid | Всего плиток | Плиток с FASM-признаками | Строк признаков |
|---|---:|---:|---:|
| BRAM | 360 | 46 | 4 555 |
| CLB | 2 200 | 2 099 | 76 158 |
| CLOCK | 283 | 47 | 384 |
| DSP | 40 | 0 | 0 |
| INTERCONNECT | 4 900 | 3 086 | 171 971 |
| IOB | 104 | 82 | 890 |
| OTHER_OR_UNKNOWN | 5 553 | 1 | 4 |
| **Всего** | **13 440** | **5 361** | **253 962** |

- Всего строк FASM **259 642**; SHA256 **`f22e32fc1608a9cee8ce30757b7d8f2856b3a307492534b02aafa7b90738b66b`**.
- **272** `unknown_bit`-аннотации, **0** иных неклассифицированных непустых строк, **0** feature-строк с tile, отсутствующим в tilegrid.
- Внутренние локальные артефакты: `/home/alex/ebaz27-xray/ebaz27-tilegrid.json`, `ebaz27-tilegrid.csv`, `ebaz27-tilegrid.svg`; никакой записи в FPGA/NAND.
- **Ограничение интерпретации:** ни 2 099/2 200 CLB-плиток с признаками, ни 0/40 DSP-плиток с признаками не измеряют реальные занятые LUT, регистры, DSP или маршруты. Нет основания объявлять 8 079 плиток без признаков свободными, а 5 361 плитку — занятой. Статус каждого tile `UNKNOWN_NOT_PROVEN_FREE`.
- **Контроль качества:** 5 553 `OTHER_OR_UNKNOWN` и 360 `BRAM` относятся к грубому префиксному разбору типов tilegrid. Это **не** количество блоков RAMB36 и не обоснование реального BRAM utilization. Требуется детализация исходных `tile_type` и sites.
- **Следующий этап EBAZ-27.8:** группировка CSV по точному `tile_type`, разбор `sites` и конкретных семейств FASM-признаков. Отдельно анализировать конфигурационные особенности EMIO/IOB/CLOCK/AXI и неизвестные биты, не выводя функциональные блоки из одного наличия tile feature.

## EBAZ-27.8 — детализация точных типов плиток (журнал CHUWI)

Первичный отчёт `tilegrid.csv` сгруппирован по `tile_type`. Выводы для функциональных плиток:

| Типы | Всего | С FASM-признаками |
|---|---:|---:|
| CLBLL_L/R | 700 | 676 |
| CLBLM_L/R | 1 500 | 1 423 |
| BRAM_L/R | 60 | 46 |
| DSP_L/R | 40 | 0 |
| INT_L/R | 3 200 | 3 086 |

Старая категория `BRAM=360` включала `BRAM_INT_INTERFACE_L/R=300`; реальные BRAM_L/R tile-позиции — **60**, а не 360. Аналогично `OTHER_OR_UNKNOWN=5 553` в основном служебные/пустые тайлы (в т.ч. `NULL`, `PCIE_NULL`, `VBRK`), не доступные вычислительные ресурсы. Два SLICE-site на CLB tile подразумевают 4 400 site-позиций при подтверждении полного `sites` списка, но **не утилизацию**. Выраженный FASM-признак не равен занятости ресурса; неотмеченный DSP tile не равен свободному DSP.

Инструмент следующего шага: `tools/ebaz27-site-evidence.py` (офлайн подсчёт реальных site entries по `tilegrid.sites`, группировка выраженных feature prefixes по точному tile type; SHA256 FASM проверяется, вывод JSON/CSV; каждый site имеет utilisation `UNKNOWN`). Синтетический тест парсинга и подсчёта 3 tiles / 7 sites пройден в изолированной среде автора. На реальном `tilegrid` CHUWI ожидается проверка пользователя.

## EBAZ-27.8 — подтверждённая инвентаризация site definitions (CHUWI, 2026-11-09)

Команда `tools/ebaz27-site-evidence.py` завершилась меткой **`EBAZ27_SITE_EVIDENCE_PASS (NOT UTILIZATION PASS)`**. Источники локальны: `factory.fasm`, `prjxray-db/zynq7/xc7z010/tilegrid.json`; результирующие файлы `/home/alex/ebaz27-xray/ebaz27-site-evidence.json` и `ebaz27-site-evidence.csv`.

- **13 440** физических tile-entries; **8 590** site entries, **253 962** разобранных feature lines, **272** unknown-bit аннотации.
- **SLICEL 2 900** (в tile с FASM: **2 775**), **SLICEM 1 500** (в tile с FASM: **1 423**): итого **4 400 SLICE site definitions**, но реальная занятость LUT/FF неизвестна.
- **DSP48E1 80** (в tile с FASM: **0**): это не доказательство 80 свободных DSP.
- **RAMBFIFO36E1 60** (в tile с FASM: **46**), **RAMB18E1 60** (в tile с FASM: **46**), **FIFO18E1 60** (в tile с FASM: **46**): эти виды site definitions не складывать как независимые емкости RAM.
- **BUFGCTRL 32** (в tile с FASM: **16**), **BUFHCE 48** (в tile с FASM: **48**), **MMCME2_ADV 2** (в tile с FASM: **1**), **PLLE2_ADV 2** (в tile с FASM: **0**): конфигурационная активность tile не определяет использование clock site.
- **PS7 1** (в tile с FASM: **0**), **IOB33M 48**/**IOB33S 48** (каждый по **38** в FASM tile), **ILOGICE3/OLOGICE3/IDELAYE2 по 100** (по **79** в FASM tile).
- **TIEOFF 3 240** site entries (в FASM tile: **3 086**) входят в учтённые 8 590, но не эквивалентны пользовательским LUT/slices.

### Шлюз EBAZ-27.9 — разбор конкретных FASM feature-prefixes

В `ebaz27-site-evidence.json` поле `tile_types.<TYPE>.top_feature_prefixes` содержит пары (feature prefix, число строк), а `sample_features` — несколько примеров исходных строк для точного типа. Начать с `CLBLL_L`, `CLBLM_L`, `BRAM_L`, `DSP_L`, `RIOB33`, `RIOI3`, `CLK_BUFG_BOT_R`, `CMT_TOP_L_LOWER_B`; затем изучать INIT, FF, BRAM content, PIP, clocking через реальные строки. На этом шаге **не делать** выводов о свободном region, не привязывать BRAM/IO к Ethernet или ASIC без трассировки.

## EBAZ-27.10 — функциональные признаки конфигурации (PASS на CHUWI, 2026-11-09)

Исполнен `tools/ebaz27-functional-evidence.py`; контрольная SHA256 `factory.fasm` повторно подтверждена: `f22e32fc1608a9cee8ce30757b7d8f2856b3a307492534b02aafa7b90738b66b`. Выходы локально: `/home/alex/ebaz27-xray/ebaz27-functional-evidence.json` и `ebaz27-functional-evidence.csv`. Контроль: **`EBAZ27_FUNCTIONAL_EVIDENCE_PASS (NOT UTILIZATION PASS)`**.

| Свидетельство | Подсчёт |
|---|---:|
| Распознанные строки признаков FASM | 253 962 |
| Уникальные позиции LUT с `INIT` в имени feature | 12 321 |
| Строки признаков `LUT.INIT` | 12 321 |
| Уникальные FF с хотя бы одним декодированным FF-атрибутом | 9 897 |
| Строки FF-атрибутов | 19 775 |
| Уникальные `FFMUX` labels | 10 317 |
| Строки carry-setting features | 4 818 |
| BRAM configuration feature lines | 4 555 |
| INTERCONNECT feature lines | 171 971 |
| I/O configuration feature lines | 890 |
| MMCM configuration feature lines | 42 |
| BUFGCTRL `.IN_USE` labels | 7 |
| Unknown-bit annotations | 272, распределены по 24 frame addresses |

Явные `BUFGCTRL.IN_USE` встречены для `BUFGCTRL_X0Y0`–`BUFGCTRL_X0Y6` в `CLK_BUFG_BOT_R_X82Y48`. Это **свидетельство включённых признаков**, не доказательство связности с определённой функциональной подсистемой или корректности DRC/STA.

**Критическое ограничение.** Эти числа *не* означают 12 321 занятых LUT или 9 897 занятных FF; отсутствие `BRAM.INIT` или DSP features в данном простом классификаторе не доказывает отсутствия содержимого или использования. `LUT.INIT` и FF-атрибуты могут быть выражены в нерабочих или избыточных элементах. Статус EBAZ-27-FREE-REGION остаётся PENDING.

**Следующий шаг (EBAZ-27.11):** ознакомиться с `sample_feature_names_not_values` из `by_tile_type.INT_L` и `INT_R` текущего JSON, проверить по базе X-Ray, как кодируются направленные PIP, затем отделять `PIP candidate` от не-маршрутных признаков, и только после этого пытаться строить граф маршрутов. Без извлечения tileconn/wire connectivity и проверки net attribution называть его полноценным netlist нельзя.

## EBAZ-27.11 — ориентация INT PIP и сверка с tileconn (подготовлено, CHUWI PENDING)

Пользователь предоставил строки FASM вида `INT_L_X....GFAN0.GND_WIRE`, `IMUX_L0.GFAN0`, `ER1BEG1.SS6END0`, `EL1BEG1.NL1END2`; это примеры, агрегированные по типу INT, поэтому без исходных tile coordinates их **нельзя объединять** в единую физическую цепь. В сегбитах Project X-Ray INT PIP кодируется как `<tile>.<destination_wire>.<source_wire>`. Направленное ребро-кандидат: `source_wire -> destination_wire`. `tileconn.json` описывает **фиксированную недиректную** межплиточную связность, а не включение конкретного PIP. Содержит и статические соединения, не имеющие признака FASM.

Инструмент `tools/ebaz27-int-route-evidence.py` сопоставляет конкретные пары `INT_L/R` с `tile_type_INT_L/R.json`, учитывает флаги `is_pseudo`, `is_directional`, `is_pass_transistor`, проверяет координатное соответствие `tileconn.json` и выводит компактный JSON/CSV в локальную приватную папку. Проверяет SHA256 `factory.fasm`, не экспортирует INIT LUT. До реального запуска на CHUWI статус **PENDING**; метка `PASS (NOT NETLIST)` подтверждает лишь согласование PIP-метаданных и локальных fixed-links. Подлинная атрибуция Ethernet/EMIO, AXI или ASIC и безопасная область PL — отдельные задачи.

### Исправление EBAZ-27.11: неверный путь к PIP-метаданным (2026-11-09)

Первый реальный запуск на CHUWI завершился **STOP** с `ValueError: missing input .../zynq7/xc7z010/tile_type_INT_L.json`. Это дефект пути в `tools/ebaz27-int-route-evidence.py`, а не проблема заводской FASM. Проверка каталога базы `f4pga/prjxray-db` подтвердила: `tilegrid.json` и `tileconn.json` находятся в `zynq7/xc7z010/`, а `tile_type_INT_L.json` и `tile_type_INT_R.json` — уровнем выше, в `zynq7/`. Путь исправлен: скрипт теперь ищет общие tile metadata в родительском каталоге и выводит разрешённые пути. До повторного запуска статус сверки PIP остаётся **PENDING**, не PASS.

### EBAZ-27.11 — отчёт CHUWI после исправления пути (PARTIAL, 2026-11-09)

Повторный запуск `tools/ebaz27-int-route-evidence.py` с разрешёнными PIP metadata из `zynq7/tile_type_INT_L.json` и `zynq7/tile_type_INT_R.json` завершился **`EBAZ27_INT_ROUTE_EVIDENCE_PARTIAL (NOT NETLIST)`** без исключений Python. Локальные артефакты: `/home/alex/ebaz27-xray/ebaz27-int-route-evidence.json` и `.csv`.

- Обработано **259 642** строк FASM, декодировано **171 971** feature `INT_L/R`; они имеют формат destination/source (нет несоответствующих пар).
- Сверка с PIP metadata: **171 898 точных соответствий** (INT_L: **84 825**, INT_R: **87 073**); **73 отсутствуют** в PIP metadata (INT_L: **31**, INT_R: **42**). Это ~99,96% соответствий по числу строк и **не** доказывает полноты проводников или netlist.
- Из совпавших PIP: **171 880** c `is_directional=1`, **18** c `is_directional=0`, **0** c `is_pseudo=1`; **1 215** отмечены как источники `GND_WIRE/VCC_WIRE`.
- Уникальных wire-endpoints в INT features: **284 445**; возможных fixed tileconn links, касающихся этих endpoints: **241 079**; fixed links с обоими INT-PIP endpoint: **25 692**; fixed links к другим типам плиток: **131 406**. **Это не число задействованных межплиточных соединений и не завершённый граф/netlist.**
- FASM аннотации неизвестных битов: **272**, не разрешены.
- Следующий строгий контроль: извлечь `examples.missing_pip_metadata` и **все 73** строки `NO_PIP_METADATA` из приватного CSV; группировать по `tile_type` и паре wire, затем оценить, являются ли они неполнотой X-Ray базы либо особым классом features. Не подставлять несуществующие связи и не переклассифицировать их как активные PIP без подтверждения.

### EBAZ-27.12 — все 73 прежних исключения относятся к двунаправленным PIP (исправление подготовлено)

Пользователь классифицировал 73 `NO_PIP_METADATA` записи в **11** повторяющихся `INT_L/R` парах на проводниках `LV/LVB/LH`; примеры `INT_L_X0Y17.LV_L0.LH0`, `INT_R_X...LV0.LV18`. Прямая проверка официальных `zynq7/segbits_int_l.db`, `segbits_int_r.db` и `tile_type_INT_L.json`/`tile_type_INT_R.json` подтвердила, что эти 11 пар присутствуют в segbits, но в PIP metadata записаны в **обратной ориентации** с `is_directional=0` и именами `<<->>`. Например, `INT_L.LV_L0.LH0` в segbits сопоставляется с метаданными `INT_L.LV_L0<<->>LH0`, где порядок `src_wire`/`dst_wire` противоположен направлению признака. Поэтому первоначальные 73 несовпадения возникли из-за ограничения прямого поиска в нашем анализаторе, а не из-за отсутствия 73 типов PIP.

Исправлена `tools/ebaz27-int-route-evidence.py`: разрешён **обратный поиск только если `is_directional=0`**, с отдельным статусом `BIDIRECTIONAL_REVERSED_PIP_MATCH`, счётчиком `bidirectional_reversed_matches` и контролем неоднозначных совпадений. **Реальный повторный запуск после исправления пока PENDING**. Ожидается, но ещё не доказано: `73` reverse-bidirectional matches, `0` missing metadata, `EBAZ27_INT_ROUTE_EVIDENCE_PASS (NOT NETLIST)`. Реверсивный PIP не означает, что в заводском bitstream настроены оба направления одновременно.

## Принцип проекта

Майнер не является предметом отдельной разработки. Сохраняем аппаратные функции, необходимые независимой EBAZ4205 и Linux; специфическую логику хеширования, цепочек ASIC, майнинговых протоколов, адресации и управления процессом добычи в реконструированную PL не переносим. Если она обнаружится при анализе — помечаем `MINING_SPECIFIC` и исключаем при проектировании нового **совместимого** статического образа. Исходный заводской bitstream остаётся неизменным доказательственным образцом.

**PWM вентиляторов — универсальная функция, не майнинговая.** Сохраняем возможность управления PWM и чтения тахометра, но пока не приписываем её заведомо PS GPIO, EMIO, PL или внешнему контроллеру. Сначала устанавливаем реальные цепи платы, инверсии, питание и наличие драйвера; затем выбираем PS/PL/внешний путь. Не включать силовые нагрузки напрямую от FPGA IO.

## Три разных вопроса

1. **Функциональная зависимость:** Ethernet PHY IP101G через EMIO/MII/MDIO, тактирование PHY, PS7/Linux, AXI BRAM по 0x40000000 и UARTLite по 0x42C00000 — кандидаты на `KEEP` до проверки фактических контрактов.
2. **Физическая конфигурация:** какие tiles, sites, BEL, PIP, clock routes и IOB features реально заданы исходным `.bit` — исследуем через Project X-Ray.
3. **Будущая сборка:** создаём новую собственную статическую PL, ограничиваем её Pblock и проверяем placement/routing/timing. Только после успешной пересборки базовой PL можно обсуждать DFX. Оригинальный закрытый bitstream нельзя просто «дополнить» Vivado partial bitstream.

## Классы решения

| Класс | Значение | Действие |
|---|---|---|
| `KEEP_REQUIRED` | доказан работающий общесистемный интерфейс | сохранить функциональную совместимость, физическую реализацию допускается заменить |
| `KEEP_OPTIONAL` | общеполезная функция (PWM, tachometer, GPIO, LED) | предусмотреть подключение после проверки схемы |
| `REMOVE_MINING` | достоверно специфическая часть ASIC/mining | не переносить в новую PL, с сохранением её следа в отчёте |
| `UNKNOWN` | назначение/зависимости не установлены | не удалять из действующей системы, не объявлять ресурс свободным |

`REMOVE_MINING` применяем к *новому проекту*, а не к байтам NAND. Заводские AXI данные/BRAM нельзя удалять на основании одного сходства с майнинговым протоколом: требуется трассировка потребителей Linux.

## Безопасность и доказательства

- Источник: локальный `ebaz26_factory_top_ctrl_2017-10-17.bit` (2 083 844 B; SHA256 `c94da9922272a6e8fdfe43c987f9ec85685d4409c1b9abe1e9b0ffe88490066a`). В публичный GitHub его не добавлять.
- Происхождение: `mtd5_factory_20261108.bin` (8 388 608 B; SHA256 `c0e787f2caf0b4c9287680ba2737b0778404e9af0222262634a14dad69ea3884`).
- X-Ray: собрать `bitread`, использовать точные `zynq7/xc7z010clg400-1` part/database и `bit2fasm.py`; записать версии инструментов, базы, входные SHA256, stderr, число нераспознанных bits/features.
- `tools/ebaz27-fasm-survey.py` даёт **только инвентаризацию строк FASM по именам tiles**. Наличие/отсутствие записей FASM не доказывает занятость/свободу tile: особенности базы, значения по умолчанию, статическая разводка, clocking и shared resources могут быть неочевидны.
- Исследовать полный grid (включая tiles, не попавшие в FASM), сайтизацию и маршруты; `CANDIDATE_UNUSED` выдавать лишь после сопоставления с полным tilegrid и известными ограничениями. Статус `SAFE_FREE` **запрещён** до пересборки, DRC, STA и проверки взаимодействия.
- Любой ресурс с неизвестным назначением, IOB, clock, interconnect, AXI или PS-PL зависимостью по умолчанию считать зарезервированным.
- Нет NAND writes, нет `/dev/xdevcfg` writes, нет повторного PCAP из живой Linux; заранее наблюдалось зависание при повторном программировании.

## Системные и опциональные контракты

| Функция | Физическая основа | Действие |
|---|---|---|
| PS UART / DDR / NAND / SDIO | PS | оставить конфигурацию PS согласованной с FSBL/U-Boot/Linux |
| GEM0 Ethernet | PS GEM → EMIO/PL → IP101G MII/MDIO | `KEEP_REQUIRED`; верифицировать clock 25 MHz, pins, PHY |
| AXI BRAM | 0x40000000–0x40001FFF | `KEEP_REQUIRED` до выяснения драйверных зависимостей; чтение 128 B PASS, запись не проверена |
| AXI UARTLite | 0x42C00000, ttyUL2 | `KEEP_REQUIRED` до выяснения назначения и зависимостей |
| LED6 | W13/W14, active-low | `KEEP_OPTIONAL` |
| FAN J3 | PWM U12, SPEED V13 (по референсному XDC) | `KEEP_OPTIONAL`; сверка платы обязательна |
| FAN J5 | PWM V12, SPEED V15 (по референсному XDC) | `KEEP_OPTIONAL`; сверка платы обязательна |
| Майнинговые ASIC интерфейсы | UNKNOWN до классификации | `REMOVE_MINING` после доказанной идентификации |

## Протокол EBAZ-27.1 (офлайн)

1. На WSL/Linux получить Project X-Ray и `prjxray-db`; зафиксировать git commit hash, part file и скрипт запуска.
2. Скопировать оригинальный .bit в отдельный **непубличный** каталог и проверить SHA256.
3. Преобразовать .bit → FASM средствами X-Ray, сохранить полный лог, предупреждения и код возврата. При ошибках/неполной базе статус `PARTIAL`, не `PASS`.
4. `python3 tools/ebaz27-fasm-survey.py /private/factory.fasm --json /private/ebaz27-fasm-survey.json` — инвентаризация feature lines по плиткам и грубым типам.
5. Привязать типы tiles к конкретным sites/BEL/PIP, проверить clock trees, IOB, PS-PL ports, AXI и внешние соединения. Вычислить отчёт с `UNKNOWN` и причинами, почему нельзя объявить область свободной.
6. Подготовить собственный Vivado static base с Ethernet+AXI и опциональным PWM/tach интерфейсом, затем получить `report_utilization -hierarchical`, `report_route_status`, `report_drc`, `report_timing_summary` и физическую карту ресурсов.
7. При успешном статическом проекте выделить отдельный Pblock-кандидат для user logic, проверить общие clock/routing ресурсы. DFX — отдельный этап с совместимыми static checkpoints.

## Критерии закрытия

`EBAZ27-FASM-INVENTORY-PASS`: точная part, hashes, успешный bit2fasm, сохранён список нераспознанных features, parser survey успешно завершён. **Не равен** `FREE-REGION-PASS`.

`EBAZ27-FREE-REGION-PASS`: собственная согласованная статическая реализация, физические границы, отсутствие конфликтов pin/clock/AXI, DRC/STA/route и реальный аппаратный функциональный PASS. Пока **PENDING**.

См. [EBAZ-25](EBAZ-25_COMPATIBLE_PL_RECONSTRUCTION_RU.md), [EBAZ-26](EBAZ-26_FACTORY_BITSTREAM_FORENSICS_RU.md), [EBAZ-21](EBAZ-21_BOARD_PINOUT_AND_FACTORY_FPGA_RU.md).