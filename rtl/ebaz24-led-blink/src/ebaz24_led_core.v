// SPDX-License-Identifier: MIT
// EBAZ-24.1: synthesizable two-LED active-low antiphase generator.
`timescale 1ns/1ps
module ebaz24_led_core #(
    parameter integer DIV_BIT = 24
) (
    input  wire clk,
    input  wire enabled,
    output wire led_green_n,
    output wire led_red_n
);
    reg [DIV_BIT:0] count = {(DIV_BIT+1){1'b0}};
    always @(posedge clk) begin
        if (!enabled)
            count <= {(DIV_BIT+1){1'b0}};
        else
            count <= count + 1'b1;
    end
    // Both LEDs are wired active-low. During startup, both stay off.
    assign led_green_n = enabled ? count[DIV_BIT]  : 1'b1;
    assign led_red_n   = enabled ? ~count[DIV_BIT] : 1'b1;
endmodule
