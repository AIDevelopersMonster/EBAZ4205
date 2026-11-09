# Vivado Tcl: cd tutorials/05_pl_led_key_adapter, then:
# vivado -mode batch -source scripts/build.tcl
# This ONLY BUILDS a bitstream; it does not program any board.
set here [file normalize [file dirname [info script]]]
set lab [file normalize [file join $here ..]]
set out [file join $lab build]
file mkdir $out
read_verilog [file join $lab rtl key_led_core.v]
read_verilog [file join $lab rtl lab05_led_key_top.v]
read_xdc [file join $lab constraints 660269A_Y13_REFERENCE.xdc]
synth_design -top lab05_led_key_top -part xc7z010clg400-1
opt_design
place_design
route_design
report_drc -file [file join $out drc.txt]
report_timing_summary -file [file join $out timing.txt]
report_utilization -file [file join $out utilization.txt]
write_bitstream -force [file join $out lab05_led_key_z010_UNVERIFIED.bit]
puts "LAB05_BUILD_COMPLETE: compile only; physical hardware test NOT done"
