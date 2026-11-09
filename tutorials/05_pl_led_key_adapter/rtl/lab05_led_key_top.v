`timescale 1ns/1ps
// Vivado non-project top. Internal configuration clock requires no PS FCLK.
module lab05_led_key_top(
    input  wire key1_n, key2_n, key3_n, key4_n,
    output wire led1, led2, led3, led4
);
    wire cfgmclk;
    STARTUPE2 #(
        .PROG_USR("FALSE"),
        .SIM_CCLK_FREQ(0.0)
    ) startup_clock (
        .CFGMCLK  (cfgmclk),
        .CFGCLK   (),
        .EOS      (),
        .PREQ     (),
        .CLK      (1'b0),
        .GSR      (1'b0),
        .GTS      (1'b0),
        .KEYCLEARB(1'b1),
        .PACK     (1'b0),
        .USRCCLKO (1'b0),
        .USRCCLKTS(1'b1),
        .USRDONEO (1'b1),
        .USRDONETS(1'b1)
    );

    wire [3:0] leds;
    key_led_core #(.PHASE_LSB(23)) logic_i (
        .clk   (cfgmclk),
        .key_n ({key4_n, key3_n, key2_n, key1_n}),
        .led   (leds)
    );
    assign {led4, led3, led2, led1} = leds;
endmodule
