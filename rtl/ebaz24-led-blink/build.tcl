# EBAZ-24.1: Vivado non-project batch compilation of an FPGA-only LED demo.
# Run from anywhere: vivado -mode batch -source build.tcl
# Compiles a bitstream; NEVER programs hardware or writes to NAND.
set root [file normalize [file dirname [info script]]]
set out  [file join $root build]
file mkdir $out

read_verilog [file join $root src ebaz24_led_core.v]
read_verilog [file join $root src ebaz24_led_top.v]
read_xdc [file join $root ebaz24_led.xdc]

synth_design -top ebaz24_led_top -part xc7z010clg400-1

# CFGMCLK is an on-chip configuration oscillator, around 50-65 MHz.
# A conservative 15ns static timing period helps expose logic timing issues.
# Do not mistake this model for an externally stabilized oscillator.
set clk_pins [get_pins -hierarchical -filter {REF_PIN_NAME == CFGMCLK}]
if {[llength $clk_pins] == 1} {
    create_clock -name CFGMCLK -period 15.000 $clk_pins
} else {
    puts "EBAZ24_WARNING: expected one CFGMCLK output pin, got [llength $clk_pins]"
    puts "EBAZ24_WARNING: timing report may not constrain the internal oscillator"
}

opt_design
place_design
route_design
report_utilization -file [file join $out utilization.rpt]
report_drc -file [file join $out drc.rpt]
report_timing_summary -file [file join $out timing_summary.rpt]

set bitfile [file join $out ebaz24_led_blink.bit]
write_bitstream -force $bitfile
if {![file exists $bitfile] || [file size $bitfile] < 100000} {
    error "EBAZ24_BUILD_FAIL: bitstream missing or suspiciously small"
}
puts "EBAZ24_BUILD_GENERATED: $bitfile"
puts "EBAZ24_BUILD_SIZE_BYTES: [file size $bitfile]"
puts "EBAZ24_NOTE: no hardware test has been performed; inspect DRC/timing."
