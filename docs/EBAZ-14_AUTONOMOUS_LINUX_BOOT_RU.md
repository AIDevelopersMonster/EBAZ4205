# EBAZ-14 — Постоянная загрузка Linux без майнера, DHCP и SSH

**Проверено на плате:** EBAZ4205, Zynq XC7Z010, PetaLinux 2016.4 / Linux 4.6.0-xilinx; дата 2026-11-04.  
**Результат:** `EBAZ-14_AUTONOMOUS_LINUX_BOOT_PASS`. Штатная перезагрузка проверена по UART/SSH; **холодный старт после полного отключения питания также проверен пользователем и подтверждён им 2026-11-04**. В автономном режиме работают Linux, Ethernet, DHCP и вход SSH по ключу; майнинговые процессы отсутствуют.

> Это протокол испытанного экземпляра, **не универсальная прошивка**. Исходный NAND изменялся только после копирования. Не публиковать приватные ключи, полные дампы NAND и пользовательские `authorized_keys`. Отдельно нужны тест восстановления и холодный запуск.

## 1. Начальное состояние и диагностическая загрузка

Инструкция [EBAZ-03](EBAZ-03_UART_LINUX_SHELL_RU.md) объясняет USB–TTL 3,3 В (115200 8N1), перехват U-Boot клавишей `d` и временную загрузку с `init=/bin/sh`:

```text
zynq-uboot> setenv nandroot 'setenv bootargs console=ttyPS0,115200 root=/dev/mtdblock6 rootfstype=jffs2 noinitrd ro rootwait init=/bin/sh'
zynq-uboot> run nandboot
```

Это даёт `sh-4.3#`, но **не запускает штатные сеть и SSH**. Не сохранять окружение командой `saveenv`.

Исходный `/etc/rcS.d/S95cgminer.sh` содержал `ifconfig eth0 192.168.80.140 up` и `/opt/system/appstartup &`. Изучены `/etc/inittab` (runlevel 5), `/etc/rc5.d/S01networking`, `/etc/rc5.d/S10dropbear`, `/etc/init.d/networking`, `/etc/init.d/dropbear` и `/etc/fstab`.

## 2. Резервное копирование NAND: обязательный этап до записи

`cat /proc/mtd` подтвердил 9 разделов, `/usr/sbin/nanddump` доступен. Через SSH двоичный поток передавался на основной Windows ПК, например для корня (`mtd6`):

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\EBAZ4205_NAND_BACKUP" | Out-Null
cmd.exe /d /c 'ssh -F none -T -o IdentitiesOnly=yes -i "%USERPROFILE%\.ssh\ebaz4205_main_ecdsa" root@192.168.1.77 "/usr/sbin/nanddump -q --bb=padbad /dev/mtd6" > "%USERPROFILE%\EBAZ4205_NAND_BACKUP\mtd6_allrootfs.bin"'
$LASTEXITCODE
(Get-Item "$env:USERPROFILE\EBAZ4205_NAND_BACKUP\mtd6_allrootfs.bin").Length
Get-FileHash "$env:USERPROFILE\EBAZ4205_NAND_BACKUP\mtd6_allrootfs.bin" -Algorithm SHA256
```

Для `mtd0`–`mtd8` повторяли `nanddump` с соответствующим разделом и отдельным файлом; проверяли код `0`, размер по `/proc/mtd` и SHA-256. Для `mtd6`: **67 108 864 байта**, SHA-256 `24ACD58164235A4AF4063D08002A2E68087A42D757431AB0D1BA6F93C154BE3D`. Для `mtd0`: **3 145 728 байт**.

**Ограничение:** это дампы областей данных без OOB, не гарантируют полнофункционального восстановления с bad-block table/ECC. Для безопасного восстановительного цикла нужны отдельные инструкции и испытание восстановления. Дампы хранятся вне публичного GitHub. Наблюдалась ошибка CRC узла JFFS2; изменение NAND связано с риском.

## 3. Подготовка сети и отключение майнера

Штатный `/etc/network/interfaces` имел закомментированный `eth0`; его изменили на:

```text
auto lo
iface lo inet loopback

auto eth0
iface eth0 inet dhcp
```

Это активирует DHCP в `S01networking` через `ifup -a`.

Постоянный `/etc/rcS.d/S95cgminer.sh`:

```sh
#!/bin/sh
# EBAZ4205: Linux without miner
# Ethernet auto-negotiation
ethtool -s eth0 autoneg on
sleep 2
exit 0
```

Заводской вызов `/opt/system/appstartup &` отсутствует; бинарные файлы майнера не удаляли.

**Важно — обнаруженная ошибка первого решения:** только этого раннего `autoneg on` оказалось недостаточно. После штатной загрузки PHY показывал `carrier=0`. Ручное повторение `ethtool -s eth0 autoneg on` восстанавливало линк `100/Full`.

## 4. Исправление Ethernet после штатной сети

Создали исполняемый файл `/etc/rc5.d/S05eth-autoneg` (права 755):

```sh
#!/bin/sh
# EBAZ4205: Ethernet recovery after networking
PATH=/sbin:/usr/sbin:/bin:/usr/bin
[ "$1" = "start" ] || exit 0
sleep 1
ethtool -s eth0 autoneg on
sleep 2
if [ -s /var/run/udhcpc.eth0.pid ]; then
    kill -USR1 "$(cat /var/run/udhcpc.eth0.pid)" 2>/dev/null || true
fi
exit 0
```

Порядок выполнения: **S01networking → S05eth-autoneg → S10dropbear**. Это изменение было проверено перезагрузкой: `carrier=1`, `inet addr:192.168.1.77`, `UP BROADCAST RUNNING`, ошибок RX = 0 на момент проверки. Адрес DHCP может измениться, привязать его лучше на роутере по MAC.

## 5. Постоянный SSH через Dropbear

Штатная служба `/etc/init.d/dropbear` уже существует; менять её не потребовалось. В `/etc/default/dropbear` заменили заводской режим `DROPBEAR_EXTRA_ARGS="-B"` на:

```sh
DROPBEAR_EXTRA_ARGS="-s -j -k -r /etc/dropbear/dropbear_ecdsa_host_key"
```

`-s` отключает парольный вход SSH, `-j -k` запрещают пересылку TCP, `-r` задаёт постоянный серверный ECDSA-ключ. Штатный скрипт также использует имеющийся RSA host key.

Постоянно сохранили два **публичных** пользовательских ключа в `/home/root/.ssh/authorized_keys` (2 строки / 349 байт), права `700` на каталог и `600` на файл. Приватный ECDSA host key сохранён в `/etc/dropbear/dropbear_ecdsa_host_key` с правами `600`. **Реальные ключи в публичный репозиторий не включены.**

В диагностическом режиме `/home/root` был перекрыт двумя `tmpfs`; для записи в настоящий каталог JFFS2 использовался временный `mount --bind / /run/ebaz-plan/flashroot` (с последующим размонтированием). Нельзя записывать `authorized_keys` только во временный `tmpfs`: после перезагрузки он исчезнет.

## 6. Установка в JFFS2 и проверка

Файлы готовили в `/run/ebaz-plan`, проверяли `sh -n`, число строк и размер `authorized_keys`. Перед установкой были созданы резервные копии всех девяти разделов NAND.

Корневую файловую систему в диагностическом режиме переводили в `rw` командой `mount -o remount,rw /` (после `mount -t proc proc /proc`). Конфигурацию и ключи копировали во временные файлы рядом с назначением, выставляли права и заменяли через `mv`. После `sync` выполнено побайтовое сравнение всех пяти установленных объектов через `cmp`; получено:

```text
EBAZ_PREFLIGHT_PASS
EBAZ_NAND_CONFIG_WRITE_PASS
EBAZ_CONFIG_READBACK_PASS
```

Для `S05eth-autoneg` подтверждено `EBAZ_ETH_BOOT_FIX_PASS`.

При попытке `mount -o remount,ro /` наблюдался `Device or resource busy`; это само по себе **не является** проверкой целостности NAND. Нельзя выполнять `fuser -k -m /`: на корневом разделе находятся системные процессы. Выполнялся `sync`, затем перезагрузка с контролем UART.

## 7. Подтверждение результата после перезагрузки

В штатном загрузочном журнале:

```text
INIT: version 2.88 booting
INIT: Entering runlevel: 5
Starting Dropbear SSH server: dropbear.
```

После внесения **позднего** исправления Ethernet в UART, **без ручной настройки PHY после перезагрузки**:

```text
carrier: 1
inet addr:192.168.1.77
UP BROADCAST RUNNING MULTICAST
```

С основного компьютера выполнен вход в MobaXterm по SSH. Проверки:

```sh
ps | grep -E '[a]ppstartup|[d]wang_btc_miner|[a]ppweb|[c]gminer'
ps | grep '[d]ropbear'
```

Первая команда не вернула процессов. Вторая показала сервер и процессы сеансов с ключами `/etc/dropbear/dropbear_rsa_host_key` и `/etc/dropbear/dropbear_ecdsa_host_key`, `-p 22 -s -j -k`. Поэтому: **EBAZ-14 AUTONOMOUS LINUX BOOT PASS**.

Сообщение MobaXterm `sh: xauth: command not found` не связано с SSH-аутентификацией: в параметрах сессии отключить X11 forwarding.

## 8. Границы результата и безопасность

- **Проверены обычная перезагрузка и холодный старт после полного отключения питания.** Холодный старт подтверждён пользователем 2026-11-04; отдельный журнал именно этого включения в документе не приводится.
- Ранее на плате разрешили локальный UART-вход root без пароля — это риск при физическом доступе; старый PetaLinux не открывать из Интернета.
- Сообщение JFFS2 `wrong data CRC` остаётся предметом отдельной диагностики.
- `RX dropped` следует наблюдать отдельно, несмотря на `RX errors=0` после исправления.
- Этот протокол не гарантирует исправности всех компонентов NAND и не заменяет испытанного сценария восстановления.
