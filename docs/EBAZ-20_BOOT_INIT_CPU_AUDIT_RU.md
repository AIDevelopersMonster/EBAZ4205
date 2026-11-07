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

## EBAZ-20.23 — Candidates substantiated by live board inspection

New console data (2026-11-07):

- `/usr/sbin/tcf-agent` is absent (`ls` reports No such file or directory) and `pidof tcf-agent` is empty. Since the existing `/etc/init.d/tcf-agent` checks `test -x /usr/sbin/tcf-agent || exit 0`, its S99 runlevel-5 boot entry is **confirmed no-op**. Safe candidate for reversible removal of its startup symlink, not target script.
- `/etc/modules` and `/etc/modules-load.d` are absent and `/proc/modules` is empty. Given the real `modutils.sh` guard `[ -f /etc/modules ] || [ -d /etc/modules-load.d ] || exit 0`, the S05 startup step is **confirmed no-op for this filesystem snapshot**. Keep in mind kernel drivers can be built-in.
- `/etc/inetd.conf` lists **only commented services**; its init script launches `/usr/sbin/inetd` with default config; `pidof inetd` reports 795. `netstat -lnt` shows TCP 22 on IPv4/IPv6 and `127.0.0.1:6010`, `netstat -lnu` shows no listeners. There is no service shown that is attributable to `inetd`. **Best first candidate to disable from boot** while retaining Dropbear and the binary. TCP/6010 is consistent with an SSH X11 forwarding listener, but its owner remains unverified; do not identify it as inetd without evidence.
- The SSH daemon is independently started by `/etc/rc5.d/S10dropbear`, not by inetd (no `dropbear -i`), so disabling inetd autostart should not be confused with disabling SSH.

**Proposed change gate:** inspect exact S65 link and the SysV rcS runner, then rename only `/etc/rcS.d/S65inetd.busybox` to a hidden disabled sibling, without killing the running inetd, deleting packages or modifying network scripts. Retain an exact reverse command. This is a **proposal** until the user performs it and validates a full subsequent boot. Because /etc is in JFFS2, rename is a persistent NAND write: only after recovery readiness and UART access are confirmed. Do not combine changes to three services in one experiment. After inetd regression PASS, repeat for the confirmed no-op tcf-agent and modutils links.

Check 6010 separately via read-only inspection of `/proc/net/tcp` and `/proc/PID/fd` if needed, or from a client use SSH with X11 forwarding explicitly disabled. `-s -j -k` indicates password auth and two TCP forwarding modes disabled, not necessarily all X11 functionality. No server config change in this step.

## EBAZ-20.24 — Full UART reboot log: boot PASS, optimization validation pending

**Source:** complete UART session log provided by the user after invoking `reboot`. The preceding actual `mv` command and post-boot inetd process listing were not included; thus *inetd-disabled PASS cannot yet be claimed*.

### Confirmed reboot sequence

- Clean shutdown attempted: Dropbear, syslog/klogd and networking stopped; JFFS2 emitted `jffs2_sum_write_data: Not enough space for summary, padsize = -581` before reset. The warning requires monitoring but does not establish flash corruption; shutdown continued.
- U-Boot 2015.07 recognizes 256 MiB DRAM and 128 MiB NAND, reads bitstream from NAND offset `0x2220000` (3 MiB), kernel from `0x300000` (5 MiB) and device tree from `0x800000` (128 KiB). Bitstream header: `top_ctrl`, `7z010clg400`, payload 2,083,740 bytes. Kernel legacy-image checksum passed.
- U-Boot printed `Invalid bus 0 (err=-1)` and `spi_flash_probe() failed, using default environment`. NAND-based kernel loading succeeded. Treat U-Boot environment storage/origin as OPEN; do not use `saveenv`.
- Linux 4.6.0-xilinx `#5 SMP PREEMPT`, activated both cores (`Brought up 2 CPUs`, 1333.33 BogoMIPS total), initialized L2C-310 512KiB 8-way, global timer clocksource (333 MHz sched_clock reference, NOT a verified CPU frequency), enabled devtmpfs.
- Root parameter `root=/dev/mtdblock6 rootfstype=jffs2`, `VFS: Mounted root (jffs2 filesystem) on device 31:6`. `mtd6` is the 64-MiB `nand-allrootfs` partition (`0x02a20000..0x06a20000`); do not confuse with the separately named `nand-rootfs` mtd3.
- SysVinit 2.88 entered runlevel 5, started Dropbear and syslog/klogd; UART displayed `zedboard-zynq7 login:`. This is **NAND_BOOT_TO_LOGIN_PASS**. Post-boot SSH connection and IP assignment not evidenced in this log.
- Device Tree kernel logs show PL UARTLite ttyUL2, PS UARTs ttyPS0/ttyPS1, ARM GIC/DMA, NAND and GEM Ethernet; hardware discovery is not a justification for removing built-in kernel drivers.

### Warnings / follow-up

1. **Ethernet race persists:** `udhcpc` sent three discovers then `No lease, forking to background`. PHY twice reported `link up (100/Full)` and `unable to generate target frequency: 25000000 Hz`. Clock/PHY status and final DHCP lease must be checked read-only before editing network timing.
2. **RTC/time:** `rtc-pcf8563 0-0051 ... probe failed with error -5`, then `hctosys: unable to open rtc device (rtc0)`; boot timestamps show 2010. Investigate device-tree RTC definition and actual board presence before any driver/clock changes. Correct time matters for system logs and security protocols.
3. **JFFS2:** during shutdown `Not enough space for summary, padsize=-581`, and at boot `Empty flash at 0x00cb8d2c ends at 0x00cb9000`. No root mount failure observed. Preserve backups, inspect free space and recurrence before changing NAND.
4. **Other nonfatal messages:** `Invalid bus 0` in U-Boot; ALSA `No soundcards found` despite initialized subsystem; I2C RTC probe failed. They are not independently proof of bad hardware.
5. **Kernel services** include USB, V4L, SCSI, CAN, RTC, DMA, Xilinx PS/PL drivers built into the 2017 kernel image. These are future kernel config audit candidates, not SysV modules to disable now.

### Post-reboot acceptance commands (board UART; read-only)

~~~sh
echo '=== BOOT ==='
cat /proc/cmdline
echo '=== INETD STARTUP LINK ==='
ls -l /etc/rcS.d/*inetd*
echo '=== INETD RUNTIME ==='
pidof inetd || echo INETD_NOT_RUNNING
echo '=== ETHERNET ==='
ifconfig eth0
route -n
cat /sys/class/net/eth0/carrier
echo '=== DHCP AND SSH ==='
pidof udhcpc
pidof dropbear
netstat -lnt
echo '=== CLOCK ==='
date -u
~~~

**Acceptance criteria:** link disabled exactly as intended, no inetd process after reboot, UART console functional, Ethernet DHCP lease present, SSH key login separately proven, same JFFS2 root. First do not change tcf/modutils or other init scripts in the same cycle.

## EBAZ-20.25 — inetd autostart disabled, reboot regression PASS

Real-board post-reboot output (2026-11-07, user supplied):

- `ls -l /etc/rcS.d/*inetd*` shows `/etc/rcS.d/disabled.S65inetd.busybox -> ../init.d/inetd.busybox`. The original S65 link is absent; the target init script remains preserved. This is a persistent change to the JFFS2 root.
- `pidof inetd || echo INETD_NOT_RUNNING` returns `INETD_NOT_RUNNING`. This confirms disabling the SysV autostart worked after a full NAND boot. **INETD_DISABLE_PASS**.
- `ifconfig eth0` reports `192.168.1.77/24`, interface `UP BROADCAST RUNNING MULTICAST`, RX=1031 packets, errors=0, dropped=185, TX=1158, errors=0. `/sys/class/net/eth0/carrier` = `1`. These counters are a single snapshot; RX drops need a second time-differenced measurement before root-cause inference.
- Default route to `192.168.1.254` (metric 10) through eth0 and LAN route `192.168.1.0/24`. DHCP `udhcpc` PID 818. Dropbear PIDs 829/856/857. Working UART root shell. Network configuration and SSH server state remain functional after inetd autostart disable; an independent post-reboot SSH key-login test was not included in the output and is pending.
- `date -u` yields `Fri Jul 23 14:18:14 UTC 2010`, so **system time is incorrect**. Previous full kernel log showed `rtc-pcf8563 0-0051 ... probe failed with error -5` and `hctosys: unable to open rtc device (rtc0)`. RTC presence, current clock source, time-sync method and DT I2C description require read-only investigation before changing config or using raw I2C operations.
- The initial `Login incorrect` appeared because commands were pasted while at the UART `login:` prompt; subsequent `root@zedboard-zynq7:~#` confirms console login. It is not a failed boot.

**Change verdict:** one deliberately isolated SysV change (rename inetd startup symlink) passed the post-reboot functional checks; other startup items remain untouched. Do not disable tcf-agent/modutils or modify mdev in the same cycle; future isolated changes can follow this measured baseline. The DHCP boot ordering/race and kernel message about target 25MHz Ethernet frequency remain OPEN despite eventual successful address assignment.

**Next read-only gate:** `ls -l /dev/rtc* /sys/class/rtc`, `cat /proc/driver/rtc`, `ls -l /sys/bus/i2c/devices/0-0051`, `dmesg | grep -i -E 'rtc|pcf8563|hctosys|clock|eth0'` and `date -u`. Avoid i2c writes/scans until hardware is identified. After that decide whether to time-sync externally and then audit boot timestamps, or to fix the Device Tree RTC node in a separately reversible firmware revision.

## EBAZ-20.26 — RTC PCF8563: device-tree node exists, hardware probe FAILED

Read-only console evidence (reported 2026-11-07):

- `/dev/rtc*`: no device. `/sys/class/rtc/`: empty. `/proc/driver/rtc`: absent. No registered Linux RTC is available at this moment.
- `/sys/bus/i2c/devices/0-0051/` exists and contains `name`, `modalias`, `of_node` linking to `/firmware/devicetree/base/amba/i2c@e0004000/rtc@51`, but **does not show a successfully bound RTC driver**. A Device Tree client instance is not proof of physically fitted PCF8563.
- Kernel logs: `rtc-pcf8563 0-0051: chip found, driver version 0.4.4`; `pcf8563_write_block_data: err=-11 addr=0e, data=03`; `pcf8563_probe: write error`; `probe of 0-0051 failed with error -5`; `hctosys: unable to open rtc device (rtc0)`.
- Actual `date -u`: `Fri Jul 23 14:20:50 UTC 2010`. No valid boot-time hardware or network time synchronization has been proven.
- Relevant public old Linux RTC driver sources place the `chip found` log before the register write and before `rtc_device_register`, so the message does not authenticate a physical chip. Address `0x0E` is the PCF8563 timer-control register and `0x03` is its low-frequency selection value; the bus write failed. `-11` corresponds to EAGAIN and final probe `-5` to EIO; do not infer a specific electric/bus fault from these numeric returns alone.

Working hypotheses: carried-over Zedboard RTC node not realized on EBAZ4205, absent/unpowered physical RTC, I2C bus/transmission/configuration problem. **Not yet differentiated.** Source references for driver semantics: `https://cos.googlesource.com/third_party/kernel/+/14f09e2f9b85076133b795a2d2615f635482de1b/drivers/rtc/rtc-pcf8563.c`; PCF8563 datasheet: `https://www.nxp.com/products/PCF8563`.

Engineering decision: keep existing NAND, kernel, device tree, I2C and RTC unchanged during diagnosis. Obtain sysfs name/modalias/compatible and adapter details read-only; inspect NTP client availability and network path; establish accurate system time over network before redesigning RTC support. `i2cdetect`, `i2cset`, raw `/dev/i2c-*` access and driver bind/unbind are excluded from this stage.

Suggested read-only capture:

~~~sh
echo '=== I2C CLIENT ==='
cat /sys/bus/i2c/devices/0-0051/name
cat /sys/bus/i2c/devices/0-0051/modalias
ls -l /sys/bus/i2c/devices/0-0051/driver 2>&1
echo '=== DT RTC COMPATIBLE ==='
tr '\000' '\n' < /proc/device-tree/amba/i2c@e0004000/rtc@51/compatible
echo '=== I2C ADAPTER ==='
cat /sys/class/i2c-adapter/i2c-0/name 2>&1
echo '=== TIME CLIENT AVAILABILITY ==='
for a in ntpd ntpdate rdate busybox; do command -v "$a" 2>/dev/null || :; done
echo '=== CLOCK NOW ==='
date -u
~~~

## EBAZ-20.27 — Internet validation: RTC footprint X3/Y2 vs PCF8563 Device Tree

**External research checked 2026-11-07; no on-board changes made.**

1. Community pinout documents EBAZ4205 MIO26=`RTC_SCL` (SoC package A15), MIO27=`RTC_SDA` (D13): https://gist.github.com/mwalle/d8291e241075d82d1d420afa9302bd91
2. Community board-hardware inventory says optional X3 footprint and Y2 RTC quartz; X3 fits a DS1307-like pinout, but its 3.3V supply is not suitable for a nominal 5V DS1307, leading to the *hypothesis* PCF8523. This is not a confirmed part identification, nor proof X3/Y2 are populated: https://github-wiki-see.page/m/xjtuecho/EBAZ4205/wiki/Hardware-Build-States.-What-you-may-or-not-have-fitted-on-your-board.
3. The rebuilt KiCad schematic explicitly labels X3 as `DS1307` and Y2 as `NC` in file data. A schematic symbol/value is not an assembly/BOM confirmation: https://github.com/xjtuecho/EBAZ4205/blob/master/HW/ebaz4205/kicad/ebaz4205.kicad_sch
4. Community discussion notes X3 RTC as **possibly PCF8523** and Y2 footprint in the hardware list: https://github.com/xjtuecho/EBAZ4205/issues/13
5. I2C addresses differ: PCF8563 has 7-bit address `0x51` (NXP PCF8563 reference https://www.nxp.com/products/PCF8563), PCF8523 has default 7-bit address `0x68` (NXP PCF8523 product data sheet https://www.nxp.com/docs/en/data-sheet/PCF8523.pdf); DS1307 likewise uses `0x68`. The current EBAZ4205 Linux tree has an I2C client `rtc@51` at `i2c@e0004000`, so its configuration may be stale/unmatched to the specific EBAZ4205 assembly.
6. The old Linux `rtc-pcf8563` driver logs `chip found, driver version 0.4.4` BEFORE attempting `i2c_master_send` at register `0x0e` and BEFORE registering the RTC; **the log message does not prove a chip acknowledged I2C**. Source: https://cos.googlesource.com/third_party/kernel/+/14f09e2f9b85076133b795a2d2615f635482de1b/drivers/rtc/rtc-pcf8563.c. The failed write to reg `0x0e` value `0x03`, error `-11`, means the transfer failed; the exact physical cause cannot be determined from this code alone.
7. A PCF8563 node at address `0x51` also exists in reference Xilinx Zynq ZC706 board DTS *behind an I2C multiplexer* (not proof of direct source copied to EBAZ board): https://github.com/Xilinx/device-tree-xlnx/blob/master/device_tree/data/kernel_dtsi/2017.2/BOARD/zc706.dtsi. This reinforces the need to treat generic 2017-era device-tree peripherals skeptically.

**Conclusion:** Hardware RTC on this user's EBAZ4205 is **UNCONFIRMED**. A mismatch between current PCF8563-compatible Device Tree and community-proposed PCF8523 footprint is a **plausible, grounded hypothesis**, not a proved board-specific identification. Do not change `rtc@51` to `rtc@68` blindly. Safest next tests: inspect actual PCB X3/Y2 via clear close-up/visual inspection, read current DT compatible and I2C sysfs name, check installed time-sync clients; then design NTP-based Linux system-time setup independent of optional RTC. Avoid raw I2C reads/writes/scans, driver unbind/bind, and rewriting NAND/DT in this phase.

## EBAZ-20.28 — RTC DT identifier confirmed; only rdate client installed

User board read-only output:

- `/proc/device-tree/amba/i2c@e0004000/rtc@51/compatible` contains `nxp,pcf8563`.
- `/sys/bus/i2c/devices/0-0051/name` contains `pcf8563`.
- These two values are **the software identification generated from the Device Tree**, not independent proof that the RTC is physically populated. The previously observed I2C driver probe failed, and the Linux RTC class is empty.
- `which ntpd ntpdate rdate` reported only `/usr/sbin/rdate`. `busybox --list` reported `rdate` only. No ntpd/ntpdate appears in the searched paths or BusyBox applets.
- **Important:** rdate is not an NTP client; it typically uses the RFC 868 Time Protocol (port 37). Do not point rdate at an arbitrary public NTP server and expect success. Before use, inspect `/usr/sbin/rdate --help` or `rdate -h` on target and identify a server supporting Time Protocol; if unavailable, prefer proper NTP client delivered as a tested static ARM binary or local LAN time service under a separately approved change procedure.
- A working Ethernet route does not establish correct DNS or Internet NTP/Time Protocol availability. No writes to NAND, Device Tree or I2C made.

Next read-only gate: `/usr/sbin/rdate --help 2>&1`, `ls -l /usr/sbin/rdate`, `date -u`, `cat /etc/resolv.conf`, `cat /proc/net/route` (network configuration only, no credentials), and inspect availability of `wget`/`nc` before choosing a network time strategy. An NTP client should synchronize clock **after** network/DHCP readiness and must not be mistaken for physical RTC repair.

## EBAZ-20.29 — SNTP instead of external RTC

User confirmed physical RTC installation is not currently possible because a connector/footprint has not been located. Software clock is still available but boots at 2010. Only available BusyBox `rdate` is RFC868 protocol (not NTP). For reliable post-DHCP time bootstrapping, created minimal one-shot SNTPv4 client at [software/ebaz20-sntp](../software/ebaz20-sntp/README.md) using IPv4 UDP port 123 and numeric Cloudflare server `162.159.200.1`, avoiding DNS. Query-only by default, optional explicit `--apply` calls `clock_settime`. Mock server tests valid response and rejections PASS on host, but **cross compilation and board runtime remain unverified**. No new startup scripts installed and no NAND, FPGA, RTC, DT writes. Await ARM `make check` and then read-only SNTP query before applying clock time; once hardware PASS, design bounded retry startup after DHCP lease readiness.

## EBAZ-20.30 — ARM SNTP cross-build PASS

User completed the WSL2 arm-linux-gnueabihf static build and `check_elf.sh`. The output showed:

~~~text
sh ./check_elf.sh "build/ebaz20-sntp" "arm-linux-gnueabihf-readelf"
e5b2f839223f9ac8e42e314bb1d984259248260837e5eb01d787e775e998d3eb  build/ebaz20-sntp
EBAZ20_SNTP_ARM_STATIC_ELF_CHECK_PASS
~~~

Status: EBAZ20_SNTP_ARM_STATIC_ELF_CHECK_PASS, ELF cross-build check passed. This is NOT yet proof that the binary executes on EBAZ4205 or can receive NTP responses. Next: create/reuse private 8 MiB RAM-backed mount on `/dev/ebaz20-ram` (required because main `/dev` is 64 KiB), binary transfer directly from WSL2 using SSH stdin, compare target SHA256 exactly to the source hash above. Then execute query-only mode (`--server 162.159.200.1`, without `--apply`) and record result; only thereafter consider explicit clock change and post-DHCP startup. No NAND writes or RTC changes in build step.
