# EBAZ-20 — Аудит и исправление загрузки Linux, служб и ARM Cortex-A9

**Статус: OPEN — сначала только диагностика, никаких изменений на плате.**
**Основание:** пользователь отметил, что успешная автономная загрузка NAND и лаборатория AXI BRAM не означают завершённой ревизии U-Boot, Linux, SysVinit, служб и процессоров.
**Плата:** EBAZ4205, Xilinx Zynq-7000 XC7Z010, dual Cortex-A9, 256 MiB DDR, NAND 128 MiB, PetaLinux 2016.4 / Linux 4.6.0-xilinx, SysVinit 2.88.

## 1. Структура загрузки, которую необходимо проверить

~~~text
BootROM
  → FSBL
  → U-Boot 2015.07
  → конфигурация PL (bitstream из NAND)
  → kernel uImage + device tree (NAND)
  → Linux 4.6.0-xilinx, root=/dev/mtdblock6, JFFS2
  → /sbin/init (SysVinit 2.88)
  → /etc/inittab → /etc/rcS.d/ и runlevel 5 (/etc/rc5.d/)
  → сети, ttyPS0 UART, Dropbear SSH, пользовательские сервисы
~~~

Последовательность выше — реконструкция по ранее наблюдавшемуся U-Boot и Linux; полная прошивочная цепочка BootROM/FSBL и фактическое назначение всех boot-разделов ещё не аудированы. Нельзя объявлять её исчерпывающе проверенной.

Рабочие критические компоненты, которые не трогаем до анализа: U-Boot environment, NAND-разделы, bitstream, bootargs, rootfs mtd6, UART, Ethernet PHY/autoneg, DHCP, Dropbear, host keys и authorized_keys.

## 2. Подтверждённые наблюдения и гипотезы

| Объект | Подтверждено | Предположение / проверка |
|---|---|---|
| NAND Linux | Автономная загрузка и JFFS2 mount, runlevel 5, работающие сеть и SSH | Последовательность всех boot-шагов и нет ли задержек или гонок |
| /proc/modules | При прежней инвентаризации список загруженных модулей ядра был пуст | Отдельно проверить builtin-драйверы kernel и текущий список; пустой список не означает «нет драйверов» |
| /etc/rcS.d/S95cgminer.sh | Имя от майнера; содержимое после очистки используется для поднятия Ethernet PHY | Нельзя просто отключить; затем перенести функцию в правильно названный init-script |
| /etc/rc5.d/S05eth-autoneg | Используется для повторного запуска DHCP после появления линка | Проверить порядок, наличие дублирования и возможность более корректного network-init |
| DHCP | В логе отмечена ранняя ошибка lease до поднятия Ethernet PHY, затем DHCP получает адрес | Гонка по времени или несогласованный порядок настройки PHY и udhcpc |
| /dev | На работающей плате есть devtmpfs, перекрытый 64-KiB tmpfs по /dev | Найти init-script, осуществляющий повторный mount, и проверить последствия исправления |
| inetd | Процесс наблюдался при отключённых пунктах /etc/inetd.conf | Кандидат для отказа от автозапуска, если нет активных потребителей |
| Dropbear SSH | Доступ по ключу, опции -s -j -k и работающая сеть | Сохранять, пока не подтверждён постоянный UART rescue и сеть после повторных загрузок |
| CPU | ARM Cortex-A9, два логических ядра, kernel SMP | Проверить online/present, /proc/interrupts, SMP startup, clock/cache/cpufreq и режимы idle |
| Kernel | 4.6.0-xilinx, PetaLinux 2016.4 | Не удалять builtin-драйверы «как модули»; это требует конфигурации и сборки kernel |
| xauth | Сообщение xauth: command not found в SSH | Скорее настройка X11 forwarding на SSH-клиенте; не ошибка boot-init |

Часть положений о bootscripts и CPU была подтверждена в прошлой лаборатории, но перед правками необходимо получить актуальные оригиналы файлов и свежий вывод платы.

## 3. Этап A: сбор текущей карты загрузки — только чтение

**Выполнять на EBAZ4205 по UART или SSH.** Не применять update-rc.d, kill, reboot, chmod, rm, mount или модификацию NAND в этой фазе.

~~~sh
echo "=== BOOT AND INIT ==="
uname -a
cat /proc/cmdline
cat /etc/inittab

echo "=== RUNLEVEL LINKS ==="
ls -l /etc/rcS.d
ls -l /etc/rc5.d

echo "=== RUNNING PROCESSES ==="
ps

echo "=== MOUNTS ==="
cat /proc/mounts
~~~

Перед публикацией полного вывода удалять секреты (если обнаружатся); сам набор команд не читает приватные ключи и пароли.

## 4. Этап B: CPU и драйверы — только чтение

~~~sh
echo "=== CPU INFO ==="
cat /proc/cpuinfo

echo "=== CPU PRESENT/ONLINE ==="
for f in /sys/devices/system/cpu/present /sys/devices/system/cpu/online /sys/devices/system/cpu/cpu1/online; do
    if [ -r "$f" ]; then echo "$f"; cat "$f"; fi
done

echo "=== SMP INTERRUPTS ==="
cat /proc/interrupts

echo "=== KERNEL MODULES ==="
cat /proc/modules
ls -ld /lib/modules /lib/modules/* 2>&1

echo "=== CLOCKS / CPUFREQ AVAILABILITY ==="
for f in /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor; do
    if [ -r "$f" ]; then echo "$f"; cat "$f"; fi
done
~~~

Отсутствие /sys cpufreq не означает, что частота CPU не определена: драйвер CPU frequency может отсутствовать, тогда анализировать нужно DT/clock framework/регистры через разрешённые интерфейсы.

## 5. Этап C: аудит конкретных сценариев и служб — только после A

После получения перечня init-ссылок прочитать **реальные** файлы, на которые они указывают, и составить матрицу зависимостей. Приоритеты:
- кто монтирует tmpfs на /dev поверх devtmpfs, зачем и безопасно ли это убрать;
- что реально делают S95cgminer.sh и S05eth-autoneg, как они связаны с eth0/udhcpc;
- кто запускает inetd, и какие сервисы активны;
- кто запускает syslog/klogd, Dropbear, getty, mdev/udev, mountall и networking;
- какие задачи были удалены из майнингового комплекса, но оставили битые ссылки или пустые демоны;
- проверка runlevel order и boot timings;
- какие драйверы встроены в ядро, какие доступны модулями, какие реально нужны аппаратуре;
- нужны ли какие-то ограничения для SMP, DMA, cache coherency и AXI при дальнейшей разработке.

Нельзя судить по имени скрипта о его назначении. **Особенно S95cgminer.sh нельзя отключать без переноса Ethernet-инициализации.**

## 6. Матрица решений перед изменениями

Каждому пункту присвоить одну категорию:
- **KEEP-CRITICAL** — критично для NAND boot, PS/PL, UART, сети, доступа или восстановления;
- **KEEP-OPTIONAL** — полезно, но может быть отключено только после зависимости и регрессионного теста;
- **RENAME/REFACTOR** — функциональность нужна, но имя/порядок скрипта некорректны;
- **DISABLE-CANDIDATE** — явно ненужное, но отключается только обратимым способом;
- **UNKNOWN** — недостаточно данных, не изменять.

На основе матрицы готовить offline patch, diff и rollback, затем staged-тест. Не удалять сразу файлы, даже если в названии «cgminer». Предполагаемые приоритеты: (1) дублирующий /dev mount; (2) скрипты PHY/DHCP; (3) пустой inetd; (4) лишние демоны; (5) CPU/clock/power management; (6) пересборка kernel — только при подтверждённой необходимости.

## 7. Безопасность и условия приёмки

- До изменения автозапуска — независимая работающая UART, резервный снимок текущей rootfs и проверенная процедура RAM-rescue EBAZ-19. Не пересобирать и не перепрошивать mtd6 ради отключения одного сервиса.
- **Одна логическая правка за итерацию**, с контрольным диффом и планом возврата.
- Для живой NAND любая запись в /etc меняет JFFS2: сначала предпочтительно работать с копией в WSL2/staging и оценивать rollback; для нужных правок использовать только подтверждённую последовательность.
- Проверять минимум: U-Boot → JFFS2 mount → runlevel → UART prompt → оба CPU online (если должны быть активны) → eth0 link → DHCP → SSH-key login → PL/AXI BRAM read-only sanity check.
- Критерии не считать пройденными по одной строке PASS; фиксировать оригинальный UART boot log после изменения и результат повторной загрузки.
- Ни при каких обстоятельствах не выполнять вслепую saveenv, flash_erase, nandwrite, system reboot, перемонтирование /dev, удаление сетевых скриптов или изменение /etc/inittab по предложенному плану без анализа текущей конфигурации.

## 8. Исходные материалы

- [EBAZ-19 — JFFS2 rebuild, RAM rescue и автономная NAND boot](EBAZ-19_CLEAN_JFFS2_REBUILD_RU.md)
- [EBAZ-20 — inventory, UARTLite, AXI BRAM, ARM app](EBAZ-20_SYSTEM_INVENTORY_RU.md)
- [EBAZ-20 — ARM toolchain](EBAZ-20_ARM_TOOLCHAIN_RU.md)
- [EBAZ-20 — AXI статья](EBAZ-20_AXI_ARM_FPGA_PRACTICAL_RU.md)

**Текущее состояние:** EBAZ-20 BOOT/CPU AUDIT OPEN, baseline пока не собран. По его результатам назначить EBAZ-20.17+ и реализовывать обратимые исправления.

## EBAZ-20.17 — Фактический список автозапуска, 2026-11-06

Получены `/proc/cmdline`, `/etc/inittab`, полный перечень ссылок `/etc/rcS.d` (17) и `/etc/rc5.d` (8), а также список процессов. Linux загружается с JFFS2 mtd6 в runlevel 5. Присутствуют inetd, udhcpc, dropbear, syslogd, klogd, UART getty и getty tty1. Есть потоки ядра для CPU1, включая migration/1 и ksoftirqd/1. Изменений NAND или автозагрузки в ходе диагностики нет.

Ключевые вопросы: текущая командная строка Dropbear отличается от ранее зафиксированной конфигурации ограничений; inetd требует проверки конфигурации; сценарии инициализации PHY и DHCP пока должны оставаться активными; нужно выяснить происхождение дополнительного tmpfs на /dev и необходимость tcf-agent, NFS, второй getty. Для следующего этапа прочитать исходные сценарии и конфигурацию, не отключать службы до установления зависимостей.

## EBAZ-20.18 — Анализ Dropbear, Ethernet и mountall

Пользователь передал действующее содержимое трёх критичных файлов и сценария DHCP.

- `/etc/default/dropbear` содержит `DROPBEAR_EXTRA_ARGS="-s -j -k -r /etc/dropbear/dropbear_ecdsa_host_key"`. Это требуемые ограничения, но **не доказательство фактических флагов запущенного процесса**.
- `/etc/init.d/dropbear` действительно загружает `/etc/default/dropbear` (`. /etc/default/dropbear` при доступности файла), затем использует `$DROPBEAR_EXTRA_ARGS` при `start` и `restart`; одновременно генерирует/использует RSA host key по умолчанию. В прошлом выводе BusyBox `ps` видны лишь `-r ...rsa... -p 22`; вывод `ps` способен **обрезать аргументы по ширине**, так что наличие или отсутствие `-s -j -k` следует проверять исключительно по `/proc/<pid>/cmdline`.
- `/etc/rcS.d/S95cgminer.sh`: только `ethtool -s eth0 autoneg on`, `sleep 2`, `exit 0`. Историческое название не означает запуск майнера. Пока сохранять.
- `/etc/rc5.d/S05eth-autoneg`: при аргументе `start` выполняет `sleep 1`, `ethtool -s eth0 autoneg on`, `sleep 2`, затем отправляет `SIGUSR1` процессу из `/var/run/udhcpc.eth0.pid` при наличии непустого файла. Пока сохранять: это рабочая схема восстановления сети после гонки PHY/DHCP.
- `/etc/rcS.d/S03mountall.sh`: вызывает `mount -at nonfs,nosmbfs,noncpfs 2>/dev/null` (монтирует подходящие записи `/etc/fstab`), при необходимости пересоздаёт `/dev/initctl`, затем отправляет `SIGUSR1` PID1 и вызывает `swapon -a`. Откуда возникло второе 64-KiB tmpfs-монтирование на `/dev`, пока не установлено: необходимо читать `/etc/fstab` и `/etc/init.d/populate-volatile.sh`.

Контроль: **никаких правок текущей NAND**, не перезапускать Dropbear и не удалять сетевые сценарии, пока не получена карта зависимостей. Следующий read-only блок: 1) полные аргументы процессов Dropbear из procfs; 2) `/etc/fstab`; 3) `/etc/init.d/populate-volatile.sh`.

## EBAZ-20.19 — Dropbear verified, /dev overlay source still unknown

Based on actual board output supplied 2026-11-06:

- `/proc/{833,879,930,931}/cmdline` contains full Dropbear arguments `-r /etc/dropbear/dropbear_rsa_host_key -p 22 -s -j -k -r /etc/dropbear/dropbear_ecdsa_host_key` for all inspected processes. Hence the SSH concern raised from abbreviated BusyBox `ps` output is RESOLVED: password login is disabled by `-s`, and TCP local/remote forwarding is disabled by `-j`/`-k`. Do not restart Dropbear merely to fix this non-issue.
- `/etc/fstab` defines `/dev/root` mounted on `/`, proc, devpts, `/run` tmpfs and `/var/volatile` tmpfs. It contains NO `/dev` tmpfs entry. The earlier supposition that `S03mountall.sh` loads the 64-KiB `/dev` overlay from fstab is NOT supported.
- `/etc/init.d/populate-volatile.sh` is a generic config-driven file/dir/link/bind-mount manager reading `/etc/default/volatiles` (with cached operations possible); no direct mount of `/dev` as tmpfs appears in the inspected script. Examine config and cached operations before excluding its influence.
- Prior `/proc/mounts` listed two mounts over `/dev`: kernel `devtmpfs`, then a 64-KiB `tmpfs`, which masks the former. This may be deliberate mdev init behavior; **not enough evidence to call it erroneous**. Investigate `/etc/init.d/mdev`, `/etc/default/volatiles/*`, `/etc/volatile.cache`, other init scripts without changing files or unmounting `/dev`.
- The copied 64-KiB ELF problem previously observed is fully compatible with an intentionally small `/dev` tmpfs; do not store program binaries in `/dev` directly.

Next read-only command set on board: `cat /etc/init.d/mdev`, `ls -l /etc/default/volatiles`, `grep -n ' /dev\|mount\|tmpfs' /etc/default/volatiles/* /etc/volatile.cache 2>/dev/null`, `cat /proc/mounts | grep ' /dev '`. Then CPU online/interrupt audit before changing init/service ordering.

## EBAZ-20.20 — Причина повторного монтирования /dev установлена

Вывод реальной платы подтверждает точную причину второго /dev mount: содержимое `/etc/init.d/mdev` начинается с `mount -t tmpfs tmpfs /dev -o size=64k,mode=0755`, затем создаёт `/dev/pts` и `/dev/shm`, монтирует devpts, создаёт `/dev/mdev.seq`, записывает `/sbin/mdev` в `/proc/sys/kernel/hotplug`, выполняет `mdev -s` и при необходимости восстанавливает FIFO `/dev/initctl`. Этот скрипт запускается через `/etc/rcS.d/S04mdev`. Первоначальный devtmpfs ядра перекрывается 64-KiB tmpfs из mdev-скрипта.

`/etc/fstab` НЕ содержит /dev, поэтому источник не mountall/fstab. `populate-volatile.sh` обслуживает файлы и ссылки из `/etc/default/volatiles`, а grep `/etc/volatile.cache` не обнаружил инструкций монтирования /dev. Проблема усечения ARM ELF при передаче через /dev (ровно 65536 байт) объясняется ограничением размера этого tmpfs, не ошибкой GCC или AXI.

Важное ограничение: наличие повторного монтирования само по себе не доказывает неисправность; mdev обеспечивает создание узлов устройств и hotplug. **Не** убирать S04mdev, не делать `umount /dev` в работающей системе и не менять NAND без аудита зависимостей и возможности отката. Целевая стратегия: сохранить работающую baseline, исследовать необходимость tmpfs поверх devtmpfs и сохранение работы mdev без повторного mount.

Следующая read-only проверка: текущие `cat /proc/sys/kernel/hotplug`, `/dev` key nodes and mounts, `/sys/devices/system/cpu/{present,online}`, `/proc/interrupts`; затем изучить действительный `modutils.sh`, `inetd.busybox` и `/etc/inetd.conf` до отключения каких-либо служб.

## EBAZ-20.21 — SMP online, GIC interrupts and mdev hotplug

Board read-only inspection on 2026-11-06:

- `/proc/sys/kernel/hotplug` = `/sbin/mdev`, consistent with `/etc/init.d/mdev` configuring the kernel hotplug handler.
- `/sys/devices/system/cpu/present` = `0-1` and `/sys/devices/system/cpu/online` = `0-1`: both Cortex-A9 processors are present **and online**. `/proc/cpuinfo` shows both as ARMv7, CPU implementer 0x41, part 0xc09, variant 0x3, revision 0, NEON and VFPv3/vfpd32 features. BogoMIPS 666.66 does **not** prove 666 MHz clock speed.
- `/proc/interrupts` has CPU0/CPU1 columns. TWD local timer IRQ18 counters: CPU0=1,233,119; CPU1=7,333,859. IPI2 (rescheduling) CPU0=859,373; CPU1=1,134,056. Ethernet eth0 IRQ148 CPU0=1,442,723, CPU1=0. UART IRQ145 CPU0=356, CPU1=0; MMC0 IRQ149 CPU0=52, CPU1=0. Err=0. Counters are accumulated since boot, not CPU utilization or rate measurements; device IRQ distribution may reflect IRQ affinity, and zero counts for a driver don't prove it is unnecessary.
- Device nodes present in the mdev-mounted /dev: `/dev/console` c5,1, `/dev/mem` c1,1, `/dev/mtd6` c90,12, `/dev/mtdblock6` b31,6, `/dev/null` c1,3, `/dev/ptmx` c5,2, `/dev/ttyPS0` c247,0, and `/dev/pts/{0,1}`. Active mdev is therefore functional. **Do not unmount /dev or disable mdev in a live SSH session.**
- Additional security check needed: `mdev` init script previously applied chmod 777 to `/dev/shm` rather than 1777; inspect effective mode and mount before interpreting this as a problem. Don't change it yet.

Next read-only gate: inspect actual CPU frequency availability, current IRQ affinity / CPU utilization counters and optional SysV services (inetd, tcf-agent, module loader), distinguishing candidates from required kernel infrastructure. No services stopped or NAND/bitstream modified.

## EBAZ-20.22 — inetd, TCF, modutils and CPU frequency

Based on actual board commands (2026-11-07 local project time; received as user console output):

- `cpu0/cpufreq/*freq` scan displayed no readable files. Thus cpufreq sysfs did not provide frequency in this run; no conclusion on actual clock or governor is justified.
- `/proc/stat` showed CPU0 and CPU1 accumulating both user and system time (CPU0 user 151432 system 93784 idle 7942829; CPU1 user 109854 system 91360 idle 7987232). Both cores are executing work; these are cumulative counters, not a contemporaneous load percentage.
- `/etc/inetd.conf`: all possible `echo`, `chargen`, `discard`, `daytime`, `time`, `telnet`, `ftp` entries are commented. `/etc/init.d/inetd.busybox` starts `/usr/sbin/inetd` without explicit alternate config path. The previous `ps` showed running inetd. Candidate for reversible removal from SysV boot after confirming no live sockets/alternate config. Not yet disabled.
- `/etc/init.d/tcf-agent`: when executable `/usr/sbin/tcf-agent` exists, invokes `tcf-agent -d -L- -l0` from `start` under runlevel 5. Initial `ps` had no unambiguous tcf-agent process; determine existence and current status before classification. Remote debug agent should not remain enabled without a development purpose; candidate only, not yet disabled.
- `/etc/init.d/modutils.sh`: conditionally loads `/etc/modules` and `/etc/modules-load.d/*.conf`, using `modprobe` or `insmod`, and may run depmod if modules.dep is absent. Earlier `/proc/modules` was empty; that alone does not establish unnecessary module loading setup. Must inspect actual module lists and built-in drivers before removal.
- Dropbear, mdev, networking and logging remain critical. No NAND, mount, daemon or kernel configuration changes made.

Next diagnostic gates (read-only): `ls -l /usr/sbin/tcf-agent`, `pidof tcf-agent`, `netstat -lnt`, `netstat -lnu`, `cat /etc/modules`, `ls -la /etc/modules-load.d`, and inspect current effective `inetd` args via `/proc/PID/cmdline` if PID stable. The initial optimization should be a reversible, separately validated SysV startup change to inetd, not deletion of the binary or live stopping of services.
