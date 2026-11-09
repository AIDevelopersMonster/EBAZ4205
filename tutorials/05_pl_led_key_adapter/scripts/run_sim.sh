#!/bin/sh
# Run from anywhere; requires iverilog + vvp. No hardware interaction.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
lab=$(CDPATH= cd -- "$here/.." && pwd)
mkdir -p "$lab/build"
iverilog -g2012 -s tb_key_led_core -o "$lab/build/tb_key_led_core.vvp"   "$lab/rtl/key_led_core.v" "$lab/tests/tb_key_led_core.v"
vvp "$lab/build/tb_key_led_core.vvp"
