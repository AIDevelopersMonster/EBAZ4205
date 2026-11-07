# EBAZ4205 LAB-05. REFERENCE XDC ONLY.
# Pin numbers were obtained from ZX_BulbuLator Step 0 and Step 2.
# Not electrically verified on the particular 660269A_Y13 PCB.
# Apply ONLY after verifying power rails, bank voltages and connector pinout.
set_property -dict { PACKAGE_PIN D18 IOSTANDARD LVCMOS33 } [get_ports led1]
set_property -dict { PACKAGE_PIN H18 IOSTANDARD LVCMOS33 } [get_ports led2]
set_property -dict { PACKAGE_PIN E19 IOSTANDARD LVCMOS33 } [get_ports led3]
set_property -dict { PACKAGE_PIN K17 IOSTANDARD LVCMOS33 } [get_ports led4]
set_property -dict { PACKAGE_PIN P19 IOSTANDARD LVCMOS33 PULLUP true } [get_ports key1_n]
set_property -dict { PACKAGE_PIN T19 IOSTANDARD LVCMOS33 PULLUP true } [get_ports key2_n]
set_property -dict { PACKAGE_PIN U20 IOSTANDARD LVCMOS33 PULLUP true } [get_ports key3_n]
set_property -dict { PACKAGE_PIN U19 IOSTANDARD LVCMOS33 PULLUP true } [get_ports key4_n]
set_property CFGBVS VCCO [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]
