// SPDX-License-Identifier: MIT
// EBAZ-24.1: PL-only test design, NO Ethernet MII/MDIO in this bitstream.
// EBAZ4205 LEDs: W13 green, W14 red, both active-low.
// The 7-series CFGMCLK is an internal oscillator; no PS FCLK is needed.
`timescale 1ns/1ps
module ebaz24_led_top (
    output wire led_green_n,
    output wire led_red_n
);
    wire cfgmclk;
    wire eos;

    STARTUPE2 #(
        .PROG_USR("FALSE"),
        .SIM_CCLK_FREQ(0.0)
    ) startup_oscillator (
        .CFGCLK(),
        .CFGMCLK(cfgmclk),
        .EOS(eos),
        .PREQ(),
        .CLK(1'b0),
        .GSR(1'b0),
        .GTS(1'b0),
        .KEYCLEARB(1'b1),
        .PACK(1'b0),
        .USRCCLKO(1'b0),
        .USRCCLKTS(1'b1),
        .USRDONEO(1'b1),
        .USRDONETS(1'b1)
    );

    ebaz24_led_core #(.DIV_BIT(24)) led_engine (
        .clk(cfgmclk),
        .enabled(eos),
        .led_green_n(led_green_n),
        .led_red_n(led_red_n)
    );
endmodule
