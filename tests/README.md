# EBAZ4205 — тесты и протоколы приёмки

[Матрица PASS / REFERENCE / PENDING](../docs/VERIFICATION_MATRIX_RU.md) — **главный источник статуса**.

Этот каталог зарезервирован для автоматизированных и воспроизводимых проверок. Он не содержит доказательств испытаний, пока такие проверки не добавлены. Физически проверенные тесты сейчас размещены рядом с программами:

- [Тест кнопок на C](../software/ebaz23-gpio-demo/README.md).
- [Тест кнопок на SD, BusyBox sh](../sdcard/EBAZ4205/tests/buttons/README.md).
- [ARM AXI BRAM reader](../software/ebaz20-bram-reader/README.md).
- [Сетевое время SNTP](../software/ebaz20-sntp/README.md).

Применяйте принцип: `host-mock PASS` != `cross-build PASS` != `on-board hardware PASS`. Для новых сценариев сохраняйте команду, результат, ревизию и версию прошивки.
