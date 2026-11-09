`timescale 1ns/1ps
module tb_key_led_core;
    reg clk = 1'b0;
    reg [3:0] keys_n = 4'b1111;
    wire [3:0] leds;
    integer i;
    always #5 clk = ~clk;

    // Small divider for simulation; actual board top uses PHASE_LSB=23.
    key_led_core #(.PHASE_LSB(2)) dut (
        .clk(clk), .key_n(keys_n), .led(leds)
    );

    task settle;
        begin
            repeat (3) @(posedge clk);
            #1;
        end
    endtask

    initial begin
        settle();
        if ((leds == 4'b0000) || ((leds & (leds - 4'd1)) != 4'b0000))
            $fatal(1, "Idle should show exactly one LED: got %b", leds);

        for (i = 0; i < 4; i = i + 1) begin
            keys_n = ~(4'b0001 << i);
            settle();
            if (leds !== (4'b0001 << i))
                $fatal(1, "Key index %0d: expected %b, got %b",
                       i, (4'b0001 << i), leds);
        end

        keys_n = 4'b0101; // KEY2 and KEY4 pressed.
        settle();
        if (leds !== 4'b1010)
            $fatal(1, "Simultaneous pressed keys failed: %b", leds);

        keys_n = 4'b1111;
        settle();
        if ((leds == 4'b0000) || ((leds & (leds - 4'd1)) != 4'b0000))
            $fatal(1, "Idle after release failed: %b", leds);

        $display("LAB05_CORE_SIM_PASS");
        $finish;
    end
endmodule
