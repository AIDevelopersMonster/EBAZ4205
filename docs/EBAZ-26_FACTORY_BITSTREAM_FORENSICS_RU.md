# EBAZ-26 — реинжиниринг заводской конфигурации PL (XC7Z010)

**Статус на 2026-11-08:** EBAZ26-HEADER-PACKET-PASS по пользовательскому логу; *не* доказано восстановление внутренних LUT/BRAM/DSP или исходной схемы. Никаких действий по записи NAND/PL не проводится.

## Наблюдение по локальному заводскому образу

- Файл `mtd5_factory_20261108.bin`, NAND MTD5 dump, 8,388,608 B; локальная копия совпала по SHA256 `c0e787f2caf0b4c9287680ba2737b0778404e9af0222262634a14dad69ea3884` с ранее снятой копией.
- Заголовок Xilinx .bit начинается с offset 0. Проект `top_ctrl;UserID=0XFFFFFFFF;Version=2016.4`, part `7z010clg400`, timestamp `2017/10/17 09:59:49`.
- Начало payload — offset 104, payload length = 2,083,740 B; SYNC `AA995566` на offset `0x98` (=152); IDCODE `0x03722093` → XC7Z010.
- Обработано 146 пакетов, FDRI writes = 520,352 words, команда DESYNC обнаружена; эти цифры не являются utilization.
- После bitstream (offset 2,083,844) до конца NAND-раздела остаётся область; последний не-`FF` байт заканчивается offset 2,949,120 (`0x2D0000`). Её содержание **пока не определено**.

## Read-only этап 2

Инструмент: [`tools/ebaz26-extract-and-map.py`](../tools/ebaz26-extract-and-map.py).

На локальной Windows:

```powershell
$Factory = 'C:\GitHub\EBAZ4205-Backup\mtd5_factory_20261108.bin'
python C:\GitHub\EBAZ4205\tools\ebaz26-extract-and-map.py \
    $Factory \
    --analysis C:\GitHub\EBAZ4205-Backup\ebaz26-analysis.json
```

PowerShell обратные косые черты в примере выше означают пути Windows, **не** перенос строк; при копировании команды исполнить одной строкой либо поставить PowerShell backtick перед новой строкой. Инструмент **не изменяет оригинал**, допускает перезапуск, проверяет SHA256 и выводит локальные файлы:

- `ebaz26_factory_top_ctrl_2017-10-17.bit` — выделенные байты 0..(104+2083740) из NAND;
- `ebaz26_factory_layout.json` — SHA256 выделенного bitstream и статистика хвоста по 64 KiB.

**Не помещать заводскую прошивку в публичный GitHub.**

## Следующий исследовательский уровень

[Project X-Ray](https://github.com/f4pga/prjxray) и [prjxray-db](https://github.com/f4pga/prjxray-db/tree/master/zynq7) имеют настройки `settings/zynq7010.sh` для `xc7z010clg400-1` и `utils/bit2fasm.py` для преобразования `.bit` в FASM при наличии C++ `bitread` и базы устройства. Разворачивать в отдельной Linux/WSL среде; не следует путать типичную потребность в старом Vivado для **fuzzers** с декодированием уже существующего bitstream. Результат будет частичным из-за неполноты feature database; даже карта занятости не позволяет безопасно добавить logic к закрытому bitstream без пересборки полной PL.

Рекомендуемый последующий анализ: feature counts по CLB, BRAM, DSP, IOB, clock и routing; попытка установить цепи PS↔PL и AXI по сравнению с Linux Device Tree / mmap; выводить отдельный уровень достоверности для каждого класса признаков. **Пока не выполнять patching или bitstream-reassembly.**

## Результат этапа 2 — выделение .bit (пользовательский протокол 2026-11-08)

- Файл `ebaz26_factory_top_ctrl_2017-10-17.bit` создан локально, **2,083,844 байта**.
- SHA256 `c94da9922272a6e8fdfe43c987f9ec85685d4409c1b9abe1e9b0ffe88490066a`.
- Образ MTD5 по-прежнему 8,388,608 байт, исходный SHA256 проверен.
- Выделенный `.bit` занимает offset `0x000000..0x1FCC04` (конец не включён); далее `0x1FCC04..0x200000` ровно 13,308 байт `FF`.
- В `0x200000..0x2D0000` расположен отдельный плотный участок 832 КиБ (851,968 байт), `FF` встречается примерно по 2,400–2,520 раз на каждые 64 КиБ, `00` почти отсутствует. Назначение пока **UNKNOWN**.
- Остаток `0x2D0000..0x800000` содержит `FF` в пределах снимка.
- **Нельзя** считать вторую область «второй прошивкой FPGA» или «сжатым кодом» без дальнейшей идентификации.

### Безопасная дополнительная проверка

[tools/ebaz26-tail-probe.py](../tools/ebaz26-tail-probe.py) — только read-only анализ локальной копии, SHA256-gated: 64-байтные примеры первых страниц, гистограмма, энтропия, распространённые сигнатуры и посекторная статистика.

```powershell
git -C C:\GitHub\EBAZ4205 pull --ff-only
python C:\GitHub\EBAZ4205\tools\ebaz26-tail-probe.py C:\GitHub\EBAZ4205-Backup\mtd5_factory_20261108.bin
```

### Декодирование конфигурации через Project X-Ray

Наличие в prjxray-db точного `zynq7/xc7z010clg400-1/part.yaml` и `settings/zynq7010.sh` подтверждено. Следующая отдельная работа на Linux/WSL — `bitread` + `utils/bit2fasm.py` → `factory.fasm` с протоколом доли нераспознанных признаков. Нужны зависимости и сборка Project X-Ray; состояние инфраструктуры пока **PENDING**, FASM и его измерения отсутствуют.
