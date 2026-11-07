`timescale 1ns/1ps
// Self-checking functional simulation of the synthesizable logic.
// STARTUPE2 is tested separately through Vivado implementation, not here.
module tb_ebaz24_led_core;
    reg clk = 1'b0;
    reg enabled = 1'b0;
    wire led_green_n;
    wire led_red_n;
    always #5 clk = ~clk;

    ebaz24_led_core #(.DIV_BIT(3)) dut (
        .clk(clk),
        .enabled(enabled),
        .led_green_n(led_green_n),
        .led_red_n(led_red_n)
    );

    task expect_leds;
        input green_n;
        input red_n;
        begin
            if (led_green_n !== green_n || led_red_n !== red_n) begin
                $display("EBAZ24_TB_FAIL at t=%0t: got green_n=%b red_n=%b expected=%b%b",
                    $time, led_green_n, led_red_n, green_n, red_n);
                $fatal(1);
            end
        end
    endtask

    initial begin
        #1;
        expect_leds(1'b1, 1'b1); // startup: both off
        @(negedge clk);
        enabled = 1'b1;
        #1;
        expect_leds(1'b0, 1'b1); // green on, red off
        repeat (7) @(posedge clk);
        #1;
        expect_leds(1'b0, 1'b1);
        @(posedge clk);
        #1;
        expect_leds(1'b1, 1'b0); // red on after 8 cycles
        repeat (8) @(posedge clk);
        #1;
        expect_leds(1'b0, 1'b1); // green on again after 16 cycles
        @(negedge clk);
        enabled = 1'b0;
        #1;
        expect_leds(1'b1, 1'b1); // both off
        $display("EBAZ24_LED_CORE_TB_PASS");
        $finish;
    end
    initial begin
        #5000;
        $fatal(1, "EBAZ24_TB_TIMEOUT");
    end
endmodule
