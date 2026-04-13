// Sample SystemVerilog file for graphify extraction tests
import some_pkg::*;

module DataProcessor
  import veer_types::*;
  #(parameter WIDTH = 32)
  (
    input  logic             clk,
    input  logic             rst_n,
    output logic [WIDTH-1:0] data_out
  );

  function automatic logic [WIDTH-1:0] calc_checksum;
    input logic [WIDTH-1:0] data;
    calc_checksum = data ^ {WIDTH{1'b1}};
  endfunction

  task automatic do_reset;
    data_out <= '0;
  endtask

  SubModule sub_inst (
    .clk(clk),
    .data(data_out)
  );

endmodule

module SubModule (
  input  logic        clk,
  input  logic [31:0] data
);
endmodule
