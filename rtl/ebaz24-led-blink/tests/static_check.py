#!/usr/bin/env python3
"""Static consistency checks; do not confuse with RTL simulation or STA."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
core = (root / 'src/ebaz24_led_core.v').read_text()
top = (root / 'src/ebaz24_led_top.v').read_text()
xdc = (root / 'ebaz24_led.xdc').read_text()
tcl = (root / 'build.tcl').read_text()

assert 'module ebaz24_led_core' in core
assert 'module ebaz24_led_top' in top
assert 'STARTUPE2' in top and '.CFGMCLK(cfgmclk)' in top
assert '.USRCCLKO(1\'b0)' in top and '.USRCCLKTS(1\'b1)' in top
assert 'PACKAGE_PIN W13' in xdc and 'PACKAGE_PIN W14' in xdc
assert 'LVCMOS33' in xdc
assert 'led_green_n' in xdc and 'led_red_n' in xdc
assert 'synth_design -top ebaz24_led_top -part xc7z010clg400-1' in tcl
assert 'report_drc' in tcl and 'report_timing_summary' in tcl
assert '/dev/xdevcfg' not in tcl and 'nandwrite' not in tcl
print('EBAZ24_STATIC_CHECK_PASS (NOT RTL SIM, NOT VIVADO, NOT BOARD PASS)')
