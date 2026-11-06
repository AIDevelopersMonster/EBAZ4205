# EBAZ-20 — Стандарт ARM toolchain для собственных программ EBAZ4205

**Статус:** WSL2-компилятор установлен и обнаружен; ARM ELF и запуск на плате ещё требуют проверки. Не следует считать бинарник протестированным на EBAZ4205 до аппаратного запуска.

## 1. Целевая платформа

| Компонент | Зафиксированное значение |
|---|---|
| Плата / SoC | EBAZ4205 / Xilinx Zynq-7000 XC7Z010 |
| CPU | 2x ARM Cortex-A9, ARMv7-A |
| Расширения CPU | VFPv3, NEON |
| Linux | PetaLinux 2016.4; kernel 4.6.0-xilinx |
| Архитектура userspace | armv7l; hard-float ABI требуется подтвердить аппаратным smoke-тестом |
| PL | AXI BRAM controller at 0x40000000; DT window 0x2000 bytes |
| Отладка | UART 115200 8N1 и SSH с ключом |
| WSL2 host | Ubuntu 24.04 на CHUWI |
| GCC фактически обнаружен | arm-linux-gnueabihf-gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0 |
| Путь GCC | /usr/bin/arm-linux-gnueabihf-gcc |

**Выбор:** GNU/Linux EABI hard-float (`arm-linux-gnueabihf`), не `arm-none-eabi` (для bare-metal) и не `aarch64-linux-gnu` (для ARM64). Для первой лаборатории используем статическую компоновку, поскольку современный динамически связанный glibc-бинарник может не запускаться с библиотеками PetaLinux 2016.4.

## 2. Установка на CHUWI в WSL2

```bash
sudo apt update
sudo apt install -y \
  gcc-arm-linux-gnueabihf \
  libc6-dev-armhf-cross \
  binutils-arm-linux-gnueabihf \
  make git file
```

Дополнительные пакеты только по необходимости: `g++-arm-linux-gnueabihf` для C++, `gdb-multiarch` для GDB, `qemu-user` для неаппаратной проверки пользовательского ARM-кода. Установка в WSL2 не меняет NAND платы.

## 3. Обязательный аудит toolchain

В WSL2:

```bash
command -v arm-linux-gnueabihf-gcc
arm-linux-gnueabihf-gcc --version | head -n 1
arm-linux-gnueabihf-gcc -dumpmachine
arm-linux-gnueabihf-gcc -print-sysroot
arm-linux-gnueabihf-gcc -print-file-name=libc.a
command -v arm-linux-gnueabihf-readelf
dpkg-query -W gcc-arm-linux-gnueabihf libc6-dev-armhf-cross binutils-arm-linux-gnueabihf
```

Ожидаем target triplet `arm-linux-gnueabihf`. Значение `-print-sysroot` равное `/` в Debian/Ubuntu cross-GCC **не обязательно ошибка**: библиотеки и заголовки могут лежать в multiarch-каталогах. Доказательство корректности — реальная сборка и проверка ELF. `libc.a` должен разрешаться в существующий файл, а не возвращаться буквально `libc.a`.

## 4. Политика сборки

Параметры начального этапа:

```text
-mcpu=cortex-a9 -mfpu=neon -mfloat-abi=hard
-O2 -Wall -Wextra -Wpedantic -Werror
-static
```

Статическая сборка не требует новых библиотек на плате, но может увеличивать размер ELF. Для динамических приложений позднее нужен sysroot **из конкретной работающей PetaLinux 2016.4** либо совместимая старшая/младшая ABI-матрица с проверкой `readelf -V`, `readelf -l`, `readelf -d`. Не используйте автоматически динамическую glibc из Ubuntu 24.04 против старого rootfs.

Контрольный пример находится в [software/ebaz20-bram-reader](../software/ebaz20-bram-reader/README.md).

```bash
git clone https://github.com/AIDevelopersMonster/EBAZ4205.git
cd EBAZ4205/software/ebaz20-bram-reader
make clean
make check
```

Критерии `make check`:
- ARM ELF32, машина ARM;
- `Tag_ABI_VFP_args: VFP registers` (hard-float);
- отсутствует `INTERP` в Program Headers;
- отсутствует `NEEDED` в Dynamic Section;
- вывод `EBAZ20_ARM_STATIC_ELF_CHECK_PASS`.

**Граница проверки:** `make check` — аудит формата файла на WSL2, а не запуск программы на EBAZ4205.

## 5. Безопасная доставка и запуск — без NAND

На штатной PetaLinux **не считать `/tmp` временной памятью автоматически**: в очищенном rootfs он был ссылкой на `/var/tmp`, находящийся в JFFS2 на NAND. Поэтому создаём отдельную явно смонтированную RAM-файловую систему.

На EBAZ4205 по SSH (root), при подключенном UART:

```sh
mkdir -p /mnt/ebaz20-ram
mount -t tmpfs -o size=8m,mode=700 tmpfs /mnt/ebaz20-ram
cat /proc/mounts | grep ebaz20-ram
```

Если каталог уже смонтирован, сначала проверьте его тип и не монтируйте повторно.

Передача бинарника из **WSL2 CHUWI** через SSH без зависимости от удалённого `scp`:

```bash
cd ~/EBAZ4205/software/ebaz20-bram-reader
ssh -x -i ~/.ssh/ebaz4205_ecdsa -o IdentitiesOnly=yes \
  root@192.168.1.77 'cat > /mnt/ebaz20-ram/ebaz20-bram-reader' \
  < build/ebaz20-bram-reader
ssh -x -i ~/.ssh/ebaz4205_ecdsa -o IdentitiesOnly=yes \
  root@192.168.1.77 'chmod 700 /mnt/ebaz20-ram/ebaz20-bram-reader'
```

Команда предполагает, что SSH-ключ `~/.ssh/ebaz4205_ecdsa` доступен **именно в WSL2**; ранее ключ также использовался в Windows PowerShell. Если его нет в WSL2, не копируйте приватный ключ в публичные каталоги: используйте уже работающий Windows SSH-клиент с защищённым ключом и подходящий безопасный способ переноса.

На плате:

```sh
/mnt/ebaz20-ram/ebaz20-bram-reader --help
/mnt/ebaz20-ram/ebaz20-bram-reader --words 16
```

Сначала `--help`: она не обращается к `/dev/mem`. После её успешного выполнения и только при подключенном UART проведите чтение 16 слов. Сопоставьте с журналом EBAZ-20.8/20.9. При изменении слов возможна работа логики PL, но это требует дальнейшего доказательства. Отсутствие изменений не доказывает, что область не обновляется.

**Осторожно:** MMIO даже в режиме чтения иногда вызывает ошибку шины или зависание, если AXI slave не отвечает. Используйте только ранее проверенный адрес `0x40000000`, без записи.

После испытаний на плате:

```sh
umount /mnt/ebaz20-ram
```

Только после завершения процесса и прекращения использования файлов. Это не касается NAND и не изменяет U-Boot.

## 6. Стандарт приёмки каждого приложения

1. **BUILD_PASS:** компилятор завершил сборку с кодом 0, без подавленных ошибок.
2. **ELF_ABI_PASS:** ELF32 ARM hard-float, ожидаемая компоновка, записан SHA-256.
3. **HOST_TRANSFER_PASS:** бинарник доставлен в RAM-раздел; при необходимости сравниваются хеши.
4. **TARGET_EXEC_PASS:** приложение реально запущено на Zynq ARM.
5. **HARDWARE_FUNCTION_PASS:** функциональный эффект подтверждён измерением, а не только печатью статуса.
6. **REGRESSION_PASS:** NAND, загрузка, Ethernet и SSH остались работоспособными.

Для каждой лаборатории сохраняем команду компиляции, версию компилятора, исходники, SHA-256 ELF, вывод аппаратной проверки и ограничения. Исходники и документы можно публиковать; не публикуйте секреты SSH, дампы NAND или специфические персональные конфигурации.

## 7. Открытые вопросы

- Убедиться, что собранный статический hard-float ELF запускается на текущей PetaLinux (только аппаратный тест даст PASS).
- Проверить способ безопасной доставки через WSL2 или Windows SSH.
- Если понадобится динамическая компоновка, создать проверенный sysroot из установленных rootfs-библиотек без публикации приватного образа.
- До MMIO-записей определить назначение данных BRAM и существующих потребителей FPGA.
