# EBAZ-24.1: PCB LED6 on EBAZ4205 XC7Z010CLG400-1.
# Third-party cross-check: darktjm/ebaz.xdc and KeitetsuWorks/EBAZ4205.
# Check actual hardware revision; both signals are active-low.
set_property -dict { PACKAGE_PIN W13 IOSTANDARD LVCMOS33 } [get_ports led_green_n]
set_property -dict { PACKAGE_PIN W14 IOSTANDARD LVCMOS33 } [get_ports led_red_n]

set_property CFGBVS VCCO [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]
set_property BITSTREAM.GENERAL.COMPRESS FALSE [current_design]
# Only relevant for full bitstream used in a reversible PL experiment.
set_property BITSTREAM.STARTUP.LCK_CYCLE NoWait [current_design]
set_property BITSTREAM.STARTUP.MATCH_CYCLE NoWait [current_design]
