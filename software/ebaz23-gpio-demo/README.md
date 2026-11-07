# EBAZ-23 — SW2/SW3: только сообщения в терминале

**Статус:** исходник обновлён; сборка под ARM и запуск на нашей плате ещё не подтверждены.

Назначение: чтение кнопок через Linux 4.6 GPIO sysfs, **без управления светодиодами, скоростью или другими устройствами**. При нажатии печатается ровно:

```text
Нажата кнопка SW2
Нажата кнопка SW3
```

Программа ожидает нажатий до Ctrl+C; опционально `--seconds 25` завершает через 25 секунд. Отпускания не печатаются. Дребезг подавляется тремя последовательными чтениями (опрос каждые ~25 мс).

## Физическая привязка (подлежит подтверждению тестом)

- SW2: MIO20 → GPIO 926; SW3: MIO32 → GPIO 938 в нашем Linux (base=906).
- Кнопки active-low по [референсному Device Tree KeitetsuWorks](https://github.com/KeitetsuWorks/EBAZ4205/blob/master/linux/ebaz4205/project-spec/meta-user/recipes-bsp/device-tree/files/ebaz4205.dtsi).
- Программа использует `/sys/class/gpio/export`/`unexport` и читает `/sys/class/gpio/gpioN/value`. Это только **временные операции sysfs в ядре**; записей в NAND, FPGA или направление GPIO output нет. Сначала проверяет, что направление уже `in`; если вывод занят другим драйвером или является выходом, останавливается.

## Сборка в WSL2

```sh
cd ~/EBAZ4205
git pull
cd software/ebaz23-gpio-demo
make clean && make check
cp build/ebaz23-gpio-buttons /mnt/c/Users/CHUWI/Downloads/
```

Готовый файл в Windows: `C:\Users\CHUWI\Downloads\ebaz23-gpio-buttons`. Это **новая сборка**, старый бинарный файл с тем же именем нужно заменить. Имя сохранено, чтобы не плодить файлы.

Передать MobaXterm/SFTP на плату в **`/tmp/ebaz23-gpio-buttons`**, при условии что `df -h /tmp` подтверждает место и mount позволяет исполнение.

```sh
df -h /tmp
chmod +x /tmp/ebaz23-gpio-buttons
/tmp/ebaz23-gpio-buttons
```

При необходимости ограничить тест: `/tmp/ebaz23-gpio-buttons --seconds 25`. Выход: Ctrl+C. По нажатию каждой физической кнопки ожидаем одну строку. Если строки не появляются, не утверждать, что схема MIO подтверждена, а проверить GPIO value/input/электрическое соединение.

**Примечание о среде сборки:** пользовательская WSL2 уже содержала `arm-linux-gnueabihf-gcc`; в контейнере ChatGPT ARM кросс-компилятор недоступен, поэтому готовый ARM ELF здесь не проверен. Разработчик не должен утверждать hardware PASS до результата на плате.

**Права:** самостоятельный исходник под MIT; референс стороннего проекта [KeitetsuWorks](https://github.com/KeitetsuWorks/EBAZ4205) также MIT.
