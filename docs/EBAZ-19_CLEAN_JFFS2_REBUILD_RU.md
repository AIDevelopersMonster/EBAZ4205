# EBAZ-19 — Чистая пересборка JFFS2 для PetaLinux EBAZ4205

**Статус на 2026-11-04:** EBAZ19_EXPORT_PASS — логический корень NAND успешно экспортирован в `rootfs_live.tar` (30 703 616 байт), структура TAR прочитана, SHA-256 записан на Windows. Следующий этап — офлайн-сборка JFFS2 в WSL/Linux. **Никакая прошивка NAND не разрешена на этом этапе.**

## Цель

Вместо поблочного копирования старой JFFS2 с повторяющимися сообщениями `wrong data CRC` создать **новую JFFS2 из логических файлов** работающего PetaLinux. Сохраняем U-Boot, ядро, Device Tree, FPGA bitstream, MTD-разметку, драйверы Zynq, сетевые скрипты и ключевой доступ Dropbear. Поскольку эти компоненты частично находятся в иных разделах, их не трогаем. Новая JFFS2 относится **только к mtd6**.

Из-за наличия повторяющихся повреждённых raw-узлов JFFS2 (наблюдались `0x019db640`, `0x02957ebc`, `0x00c90000`) нельзя объявлять весь NAND аппаратно неисправным, но нельзя и считать ручное удаление отдельных файлов полноценным лечением.

## Проверенная геометрия

| Свойство | Значение |
| --- | --- |
| Корень Linux | `/dev/mtdblock6`, JFFS2, `/sbin/init` |
| Размер mtd6 | 64 MiB (67 108 864 байта) |
| Eraseblock | 128 KiB (131 072 байта) |
| Физическая страница NAND | 2048 байт, OOB 64 |
| Размер JFFS2 data node | до 4096 байт (страница памяти ARM) |
| Endian | little-endian |

Для `mkfs.jffs2`: `-l -n -e 0x20000 -s 0x1000`. `-n` не добавляет cleanmarkers на NAND; `-s` **не** размер физической страницы NAND. Алгоритмы сжатия надо проверить относительно ядра Linux 4.6; неподтверждённый LZO не использовать.

## Безопасный порядок

### A. Экспорт логического дерева с живой платы, без записи во Flash

Выполнить на Windows команду SSH, передающую удалённый `tar` **двоичным потоком** без перекодирования PowerShell 5.1. На плате из `/run` (RAM tmpfs) временно сделать **нерекурсивный** `mount --bind / /run/ebaz19-rootview`. Тогда архивируется только базовая JFFS2, а содержимое дочерних mountpoints `/proc`, `/sys`, `/run`, `/dev` не попадает в архив как временные псевдофайлы. После экспорта bind mount снять.

В экспортируемом дереве должны присутствовать `/sbin/init`, `/etc/inittab`, `/etc/network/interfaces`, `/etc/rcS.d/S95cgminer.sh` (имя старое, содержимое теперь настройка Ethernet), `/etc/rc5.d/S05eth-autoneg`, `/etc/default/dropbear`, `/etc/dropbear/dropbear_ecdsa_host_key` и `/home/root/.ssh/authorized_keys`.

Сохранить `rootfs_live.tar`, его SHA-256, `/proc/mtd`, `/proc/cmdline`. Не публиковать архив: в нём **закрытые SSH-ключи и локальные настройки**.

Экспорт происходит из **работающей** JFFS2, поэтому не является атомарным. Ошибки чтения, прерывание SSH и повреждение tar — основания остановить работу.

### B. Офлайн-сборка на ПК Linux/WSL2

Распаковать tar **под root на Linux ext4**, сохранив числовые UID/GID, режимы, символьные ссылки и узлы устройств. **Не распаковывать корень в NTFS напрямую**, где могут быть потеряны важные метаданные.

Из очищенного дерева сформировать через mtd-utils:
- компактный `EBAZ4205-rootfs-clean-UNPADDED.jffs2`;
- отдельно 64-MiB кандидат, заполненный байтами `0xFF` до полного размера раздела: `EBAZ4205-rootfs-clean-64MiB-DO_NOT_FLASH.img`.

Не удалять автоматически спорные программы, аппаратные драйверы и библиотеки. Уже удалённые `appstartup`, `startscrip`, `btc_upgrade.tar.gz` **не должны снова появиться**. EBAZ-17 NAND snapshot сохранять отдельно без изменений.

### C. Проверки перед прошивкой

1. Прочитать весь `rootfs_live.tar` без ошибок, проверить перечень файлов, UID/GID, права и целостность важных файлов.
2. Сверить все JFFS2 header CRC, inode node/data CRC и dirent node/name CRC; не должно быть ошибок.
3. Убедиться, что создаваемая компрессия поддерживается реальным ядром 4.6.
4. Сверить дерево файлов с результатом извлечения **нового JFFS2**; CRC структуры недостаточно для доказательства эквивалентности файлов.
5. Проверить **независимую rescue-загрузку в RAM**, которая не использует mtd6 и способна получить образ извне.
6. Испытать процедуру восстановления прежнего rootfs (существующий дамп EBAZ-17 **data-only, без OOB**, сам по себе недостаточная гарантия).
7. Только после этих условий составлять **отдельный** сценарий стирания/записи лишь mtd6. Переписывать корневую NAND из Linux, загруженного с неё самой, нельзя.

**Никаких команд `flash_erase`, `nandwrite`, `nandmarkbad`, `nandtest` и `saveenv` в процедуре экспорта и офлайн-сборки нет.**

## Границы

- EBAZ-19 — инженерный лабораторный образ с текущим SSH-доступом; **не готовая клиентская прошивка**. Для продажи действует отдельная концепция [EBAZ-15](EBAZ-15_CLIENT_HANDOFF_RU.md).
- Дополнительная оптимизация служб и пакетов будет отдельным этапом; сначала добьёмся воспроизводимой чистой файловой системы.
- Технические команды и скрипты экспорта/сборки держать в репозитории без архивов, секретов и реальных образов NAND.

## EBAZ-19 v3 → v4: экспорт с CHUWI при урезанном BusyBox (2026-11-05)

- v3: `EBAZ19_SSH_HOST_IDENTITY_PASS`, затем штатный отказ `EBAZ19_ABORT: board tar lacks --exclude`. На NAND ничего не записывалось.
- v4 (подготовлен, локально проверен на синтетическом TAR, **на реальной плате пока не испытан**): прежний работающий read-only экспорт через `tar -cf - .` и SSH направляется в потоковый Python-фильтр в Ubuntu WSL2. Два известных майнинговых файла `var/dwang_btc_miner` и `var/HKDW.tar.gz` исключаются **до записи итогового TAR на диск**; их содержимое проходит зашифрованный SSH-канал, но не сохраняется в архив. Права, UID/GID и специальные записи копируются как TAR metadata.
- Скрипт строго проверяет отпечаток SSH-сервера, не перезаписывает уже существующий выходной TAR, проверяет критические пути и отсутствие двух исключённых файлов. В тесте с 80 элементами успешно сохранил 78, исключив два указанных файла; содержимое и числовые UID сохранились.
- После v4 требуется аудит любых других остатков майнера, проверка нового образа, независимая rescue-загрузка и rollback. **NAND не прошивать**.

## EBAZ-19 v4 — результат фактического экспорта (2026-11-05)

- `EBAZ19_SSH_HOST_IDENTITY_PASS` (ECDSA SHA256:05t7Y/wKCSL6FVmoTuNR6b/LerRiLeTu+zl9jnASOVA).
- `EBAZ19_STREAM_FILTER_PASS: entries_seen=891 retained=889 rejected=2`.
- Не попали в новый TAR: `/var/HKDW.tar.gz`, `/var/dwang_btc_miner`.
- `EBAZ19_SOURCE_FILTER_PASS`, `EBAZ19_TAR_STRUCTURE_PASS` (unsafe archive entries: 0), `EBAZ19_CLEAN_EXPORT_PASS`.
- Новый файл в WSL2 CHUWI: `/home/alex/EBAZ4205_EBAZ19/rootfs_clean_export.tar` (~22 MiB). Контрольная сумма сохранена локально, пока не зафиксирована в GitHub (образ не публиковать).
- Девять путей отложены на аудит перед сборкой: `lib/libappweb.so`, `etc/init.d/cgminer.sh`, `etc/rcS.d/S95cgminer.sh`, `bin/appweb`, `bin/watchdog_btc`, `var/net-snmp/snmpd.conf`, `var/snmpd.conf`, `var/snmpd`, `.cgminer`.
- `/etc/rcS.d/S95cgminer.sh` **сохранить**: несмотря на имя, он содержит настройку Ethernet PHY, не запуск майнера. Остальные восемь нуждаются в проверке ссылок из загрузочных сценариев перед удалением **только из staging**.
- Повторный запуск экспортера правильно остановлен: `EBAZ19_ABORT: output already exists`. Повторная выгрузка не требуется.
- **Статус: очищенный логический TAR получен; новая JFFS2 ещё НЕ собрана, НЕ загружалась и НЕ прошивалась.**

## EBAZ-19 v5 — офлайн-сборка, ошибка параметра --pad (2026-11-05)

Реальный запуск под Ubuntu WSL2: `EBAZ19_V5_CLEAN_TAR_PASS: kept=879 removed=10`; TAR audit PASS; required files PASS. `mkfs.jffs2` выполнился, но проверка 64-MiB образа остановлена: `EBAZ19_V5_ABORT: unexpected image size`.

Причина: в сборочном скрипте ошибочно указано `-p 0x4000000`. Опция `-p` имеет **необязательное** значение: если размер передан отдельным аргументом, он не связывается с `-p`, и утилита заполняет лишь конечный eraseblock. Корректный синтаксис: `--pad=0x4000000` (или `-p0x4000000`). Исправление не касается геометрии NAND, образа-источника или настроек Ethernet/SSH.

**Безопасное восстановление текущей сборки:** взять созданный `EBAZ4205-rootfs-clean-UNPADDED.jffs2` и добавить исключительно байты `FF` до 67108864 байт в **новый** файл `EBAZ4205-rootfs-clean-64MiB-FIXED-DO_NOT_FLASH.img` (в каталоге `build-v5`), после чего проверить структуры и CRC обоих образов скриптом `04_verify_jffs2.py` и записать SHA-256. Нельзя использовать `truncate -s`, поскольку он дополняет нулями, а не `FF`. Операцию выполнять только на WSL ext4, не трогать NAND. До independent rescue/rollback прошивка ЗАПРЕЩЕНА.

## EBAZ-19.6 — FF padding and CRC verification PASS (2026-11-05)

- `rootfs_firmware_candidate_v5.tar`: 879 records, SHA256 `a257ba577722b8b8b808cfa3a76152895a1b2967df0325d686a0c9a277204785`.
- FF-padded candidate `EBAZ4205-rootfs-clean-64MiB-FIXED-DO_NOT_FLASH.img` has exactly 67,108,864 bytes. SHA256 `7b5cbb6cb423a0bac824247baa4e9e74ea6dc5179e292593b0de7c0021326c85`.
- `JFFS2_CRC_PASS`: 7,171 nodes; 6,293 raw inode nodes; 878 dirents; zero CRC or structure errors. Compression: NONE=1663, RTIME=1, ZLIB=4629, no LZO.
- Next EBAZ-19 v6: independent read-only comparison of JFFS2 contents, metadata, and symlinks against staging TAR. No NAND writes until rescue+rollback validation.

## EBAZ-19 v6.1 — корневой inode 1 JFFS2

- Первый прогон независимого сравнения v6: `EBAZ19_V6_ROUNDTRIP_FAIL: missing metadata for JFFS2 paths: {1}`. Это ограничение **валидатора**, не новое сообщение CRC NAND.
- JFFS2 использует специальный корневой inode 1; `mkfs.jffs2` может не писать для него отдельный raw_inode. В v6.1 допускается отсутствие метаданных **только** для root inode 1, остальные inode обязаны иметь их. Метаданные UID/GID/mode/mtime самого root тогда **не подтверждены** и выделяются в отчёте.
- Исправление проверено на синтетических тестах с явным/неявным root, намеренно отсутствующим обычным inode и ошибками данных. Реальный JFFS2 ещё предстоит перепроверить. Файлы NAND/TAR/образ не менялись, прошивка запрещена до независимого rescue и rollback.

## EBAZ-19.7 — независимый round-trip JFFS2↔TAR PASS (2026-11-05)

**Результат на реальном образе:** скрипт `08_verify_roundtrip_v6_1.py` выполнил `EBAZ19_V6_SELFTEST_PASS` и `EBAZ19_V6_ROUNDTRIP_PASS`: имена, содержимое обычных файлов, пути символических ссылок, режимы, UID/GID и mtime соответствуют очищенному TAR.

| Показатель | Результат |
| --- | --- |
| Образ | `EBAZ4205-rootfs-clean-64MiB-FIXED-DO_NOT_FLASH.img` |
| SHA256 образа | `7b5cbb6cb423a0bac824247baa4e9e74ea6dc5179e292593b0de7c0021326c85` |
| SHA256 очищенного TAR | `a257ba577722b8b8b808cfa3a76152895a1b2967df0325d686a0c9a277204785` |
| Проверенных записей TAR | 879 |
| Обычных файлов | 460 |
| Обычных байтов | 22125972 |
| Каталогов | 99 |
| Символических ссылок | 319 |
| Жёстких ссылок | 1 |
| Узлов JFFS2 | 7171 |
| Компрессия | NONE 1663; RTIME 1; ZLIB 4629 |

**Ограничение:** для виртуального корневого inode 1 в JFFS2 нет отдельного `raw_inode`; атрибуты root каталога `/` не проверены. `ROUNDTRIP_PASS` не означает, что текущий старый kernel и bootloader гарантированно загрузят образ, что NAND здорова, или что отсутствует вредоносное ПО. Компоненты U-Boot, kernel, FPGA boot partitions не изменены.

**Следующий шаг EBAZ-19.8:** безопасная инвентаризация механизма загрузки и доступной RAM на действующей плате, затем подготовка и практическая проверка **независимой RAM-rescue среды** с возможностью записи и обратного восстановления только `mtd6` при ошибке. Не использовать `flash_erase`, `nandwrite`, `saveenv` до завершения независимого восстановления и подтверждения NAND write/read workflow.

## EBAZ-19.8 — RAM rescue kernel capability preflight (2026-11-05)

**Read-only SSH result from current running board**:

- Kernel: `Linux 4.6.0-xilinx`, armv7l, Zynq.
- `/proc/cmdline`: `console=ttyPS0,115200 root=/dev/mtdblock6 rootfstype=jffs2 noinitrd rw rootwait`.
- NAND `mtd6`: `04000000` bytes (64 MiB), erase size `00020000` (128 KiB); 9 MTD partitions (mtd0–mtd8). **Only mtd6 is proposed for eventual recovery, not other boot partitions.**
- `MemTotal: 252032 kB`, `MemAvailable: 235748 kB` at measurement.
- `CONFIG_BLK_DEV_INITRD=y`, `CONFIG_RD_GZIP=y`, `CONFIG_DEVTMPFS=y`.
- Filesystems `rootfs`, `ramfs`, `tmpfs`, `devtmpfs`, `nfs`, `jffs2` available.

**Conclusion:** capability preflight PASS, not yet a tested independent rescue boot. Next: inventory ARM BusyBox and dynamic-loader dependencies, MTD write/erase commands, ramdisk options, and U-Boot's bootm/TFTP path. Prepare gzip cpio rescue with `/init` in RAM, retaining UART access and read-only MTD diagnostics, then test actual boot before any mtd6 change. Existing `noinitrd` must be removed from *temporary* rescue bootargs, and U-Boot `saveenv` must never be used during testing.

## EBAZ-19.10 — ELF-deps и подготовка RAM rescue v7

Read-only ELF inspection of the verified staging TAR on CHUWI established that all five ARM binaries use the interpreter `/lib/ld-linux-armhf.so.3`. `busybox.nosuid` links `libm.so.6` and `libc.so.6`; `busybox.suid`, `nanddump`, `nandwrite` and `flash_erase` each link `libc.so.6`. The shell used on the main rootfs (`/bin/bash`) is not required for the minimal rescue: its `/bin/sh` points to BusyBox.

**RAM rescue v7 prepared but NOT tested on hardware.** Local builder `09_build_rescue_initramfs_v7.py` accepts only the v5 candidate TAR with SHA256 `a257ba577722b8b8b808cfa3a76152895a1b2967df0325d686a0c9a277204785`, extracts only allowlisted ARM executables and their link-target libraries, produces newc CPIO with `/dev/console` (5,1), gzip initramfs and U-Boot legacy ramdisk image using `mkimage`. It refuses to overwrite a previous output directory and makes no connection to the board. The CPIO file list and special device records passed synthetic offline tests. Actual ARM ELF and U-Boot image validation will occur on CHUWI after building from the real TAR.

**Next:** create the v7 rescue archive in Ubuntu WSL2; inspect actual U-Boot boot sequence using only `printenv` over UART; do not guess boot addresses or issue persistent bootloader changes. NAND remains unchanged until independent rescue-boot and rollback readiness are demonstrated.

## EBAZ-19.11 — RAM-rescue v7 assembled successfully (2026-11-05)

Status: offline-built only; no board connection, no NAND writes.

- ARM ELF dependencies PASS for BusyBox (`libc.so.6`, `libm.so.6`) and NAND utilities (`libc.so.6`); loader `/lib/ld-linux-armhf.so.3`.
- `EBAZ19_RESCUE_V7_CPIO_PASS`: 37 entries.
- `EBAZ19_RESCUE_V7_INITRD_PASS`: 1,419,057 bytes.
- `EBAZ19_RESCUE_V7_UINITRD_PASS`: 1,419,121 bytes.
- `EBAZ19_RESCUE_V7_BUILD_PASS`.
- Local path (CHUWI WSL2): `/home/alex/EBAZ4205_EBAZ19/rescue-v7`.
- Pending: verify mkimage header, inspect actual U-Boot 2015.07 environment and its loading commands from UART, load rescue using verified RAM addresses, confirm standalone shell and MTD read-only access, then validate recoverability before even considering writing mtd6. Do not use `saveenv`.

## EBAZ-19.15 — TFTP transfer of RAM rescue confirmed (2026-11-05)

- CHUWI TFTP32 serves read-only from `C:\Users\CHUWI\EBAZ4205_TFTP`, bound to `192.168.1.79` (Ethernet).
- UART U-Boot `ping 192.168.1.254` and `ping 192.168.1.79`: success after Windows inbound ICMP rule for `192.168.1.77`.
- U-Boot environment: `kernel_load_address=0x2080000`, `kernel_size=0x500000`, `devicetree_load_address=0x2000000`, `devicetree_size=0x20000`, `ramdisk_load_address=0x4000000`. Existing `nandboot` loads FPGA image before kernel+DT then executes bootm *without* initrd; it must not be called unchanged for rescue.
- `tftpboot 0x04000000 ebaz19-rescue-v7.uInitrd`: success, `Bytes transferred = 1419121 (15a771 hex)`.
- Next mandatory check `iminfo 0x04000000`, then **read-only NAND** loading existing FPGA bitstream, kernel and device tree at documented RAM addresses, temporary `bootargs` with initramfs `/init` (remove `noinitrd`; no `root=/dev/mtdblock6`). Confirm new root is RAM via UART. No NAND writes, no `saveenv`.

## EBAZ-19.17 — RAM-rescue v7 boot on real board PASS (2026-11-05)

**First hardware boot of independent rescue succeeded.** UART log confirms:

- U-Boot `iminfo 0x02080000`: `Linux-4.6.0-xilinx` legacy ARM kernel image, data size 3820688 bytes, checksum OK.
- `bootargs` in the running kernel: `console=ttyPS0,115200 rdinit=/init`, without `root=/dev/mtdblock6` and `noinitrd`.
- `bootm 0x02080000 0x04000000 0x02000000` verified kernel and `EBAZ19 RAM-RESCUE v7` initramfs checksums, relocated ramdisk to `0x0f1aa000`–`0x0f304731`, FDT to `0x0f1a4000`–`0x0f1a9b90`, and started the existing Linux 4.6 kernel.
- Kernel reported `Trying to unpack rootfs image as initramfs...`, then executed `/init`. Banner: `EBAZ-19 RAM-RESCUE v7: running in RAM (NOT mtd6)` and UART prompt `/ #`.
- NAND partitions `mtd0` to `mtd8` detected. Existing BBT was found. Four listed bad blocks at offsets `0x07f60000`, `0x07f80000`, `0x07fa0000`, `0x07fc0000` are *outside* `mtd6` (`0x02a20000`–`0x06a20000`); this is **not** a complete NAND health assessment and no BBT changes were made.
- **PASS meaning:** independent RAM rescue boot and UART shell actually operate. **Not yet established:** rescue MTD read/write access, reliable transport of original image, rollback under failure, boot with clean JFFS2 from NAND.

**Next safe phase:** while at `/ #`, verify `/proc/cmdline`, root mount, `/dev/mtd6` and tool paths, optionally perform a *read-only* 2048-byte `nanddump` into RAM. No erase, nandwrite, or saveenv. Retain original NAND backups; do not write to `mtd6` until restoration procedure can be validated and user confirms the destructive phase.

## EBAZ-19.18 — Rescue NAND read-only test PASS

On the actual EBAZ4205 board, in the independent RAM-rescue v7 at UART prompt `/ #`:

- `/proc/cmdline`: `console=ttyPS0,115200 rdinit=/init`.
- `/dev/mtd6` exists as character device major 90 minor 12; `/dev/mtdblock6` as block device major 31 minor 6.
- `/usr/sbin/nanddump`, `nandwrite`, and `flash_erase` exist in rescue; only `nanddump` was executed.
- `/usr/sbin/nanddump -q --bb=padbad -s 0 -l 0x800 -f /tmp/mtd6_readtest.bin /dev/mtd6` returned exit code 0 and produced exactly 2048 bytes in RAM.
- `grep` is not present in the minimal rescue; use `cat /proc/mounts` without piping to grep. The missing utility is not a kernel failure.

**Status:** independent rescue boot + read-only MTD6 access confirmed. This test covers only one NAND page, **not** whole-partition read integrity or recoverability. Next check the rescue Ethernet link and TFTP GET for an existing file into RAM, to establish a transport path for an eventual rollback image. No `nandwrite`, `flash_erase`, `saveenv` or NAND writes authorized.
