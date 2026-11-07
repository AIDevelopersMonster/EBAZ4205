#!/bin/sh
# RTL simulation on PC (requires Icarus Verilog).
set -eu
cd "$(dirname "$0")"
if ! command -v iverilog >/dev/null 2>&1 || ! command -v vvp >/dev/null 2>&1; then
    echo 'EBAZ24_SIM_NOT_RUN: install Icarus Verilog (iverilog + vvp)' >&2
    exit 2
fi
mkdir -p build
iverilog -g2012 -Wall -s tb_ebaz24_led_core \
    -o build/ebaz24_led_tb src/ebaz24_led_core.v tb/tb_ebaz24_led_core.v
vvp build/ebaz24_led_tb
