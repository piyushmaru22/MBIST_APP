import streamlit as st
import streamlit.components.v1 as components
import math
import json

# ============================================================================
# IMC SRAM VERILOG & TESTBENCH GENERATOR ENGINE
# ============================================================================

def generate_imc_verilog(depth, data_width):
    addr_width = int(math.ceil(math.log2(depth)))
    verilog_code = f"""`timescale 1ns/1ps

// ============================================================================
// Module Name: sram_{depth}x{data_width}_IMC
// Description: Synchronous In-Memory Computation (IMC) SRAM Architecture
//              Integrates Near-Memory Operand Shadow Registers (R[0], R[1]),
//              a 1-bit Implicit Toggle Flag Demux, and a 4-Bit Ripple-Carry Adder.
// Specs      : {depth} Words x {data_width} Bits (Address Width: {addr_width} bits)
// ============================================================================

module sram_16x4_IMC #(
    parameter DEPTH = {depth},
    parameter ADDR_WIDTH = {addr_width},
    parameter DATA_WIDTH = {data_width}
)(
    input                        clk,
    input                        CE,    // Chip Enable (Active High)
    input                        OEB,   // Output Enable Bar (Active Low)
    input                        CSB,   // Chip Select Bar (Active Low)
    input                        WEB,   // Write Enable Bar (Active Low)
    input                        M_C,   // Mode: 0 = Memory, 1 = Computation

    input      [ADDR_WIDTH-1:0]  A,     // Memory Address Bus
    input      [DATA_WIDTH-1:0]  I,     // Data Input Bus
    output reg [DATA_WIDTH-1:0]  O,     // Memory Read / Compute Sum Output
    output reg                   Carry  // Compute Carry-Out Overflow Flag
);

    // 1. Primary SRAM Bitcell Array
    reg [DATA_WIDTH-1:0] mem [DEPTH-1:0];

    // 2. Near-Memory Compute Periphery: Operand Registers & Implicit Toggle Flag
    reg [DATA_WIDTH-1:0] R [1:0];
    reg flag = 0;

    always @(posedge clk) begin
        if (CE) begin
            if (!CSB) begin
                if (M_C) begin
                    // IN-MEMORY COMPUTATION MODE: Single-Cycle Addition
                    {{Carry, O}} = R[0] + R[1];
                end else begin
                    // STANDARD MEMORY MODE + IMPLICIT OPERAND SNOOPING
                    case ({{WEB, OEB}})
                        2'b01: begin // Synchronous Write
                            mem[A]  <= I;
                            R[flag] <= I;     // 1:2 Demux routes I into R[0] or R[1]
                            flag    <= ~flag; // Toggles select line for next write
                        end
                        2'b10: begin // Synchronous Read
                            O <= mem[A];
                        end
                    endcase
                end
            end
        end
    end

endmodule
"""
    return verilog_code


def generate_imc_testbench(depth, data_width):
    addr_width = int(math.ceil(math.log2(depth)))
    max_combinations = (2 ** data_width) * (2 ** data_width)
    val_limit = 2 ** data_width

    tb_code = f"""`timescale 1ns/1ps

// ============================================================================
// Module Name: tb_sram_16x4_IMC_updated
// Description: Self-Checking Exhaustive Verification Testbench
// Features   : - Negedge Stimulus Driving (Zero Setup/Hold Violation Hygiene)
//              - 3-Phase Verification (Memory Init, {max_combinations}-Case IMC, Retention)
//              - Real-Time Protocol Assertion Monitor & Audit Report Export
// ============================================================================

module tb_sram_16x4_IMC_updated;

    // Parameters
    parameter DEPTH = {depth};
    parameter ADDR_WIDTH = {addr_width};
    parameter DATA_WIDTH = {data_width};

    // Testbench Signals
    reg clk;
    reg CE;
    reg OEB;
    reg CSB;
    reg WEB;
    reg M_C;
    reg [ADDR_WIDTH-1:0] A;
    reg [DATA_WIDTH-1:0] I;
   
    wire [DATA_WIDTH-1:0] O;
    wire Carry;

    // Verification Variables
    integer total_compute_tests = 0;
    integer total_memory_tests = 0;
    integer errors = 0;
    integer file_handle;
    reg [DATA_WIDTH:0] expected_sum;
    integer op1, op2, addr;

    // Instantiate the Unit Under Test (UUT)
    sram_16x4_IMC #(
        .DEPTH(DEPTH),
        .ADDR_WIDTH(ADDR_WIDTH),
        .DATA_WIDTH(DATA_WIDTH)
    ) uut (
        .clk(clk),
        .CE(CE),
        .OEB(OEB),
        .CSB(CSB),
        .WEB(WEB),
        .M_C(M_C),
        .A(A),
        .I(I),
        .O(O),
        .Carry(Carry)
    );

    // Clock Generation (10ns period -> 100 MHz)
    always #5 clk = ~clk;

    // --- ASSERTION-BASED PROTOCOL INTEGRITY MONITOR --- //
    always @(posedge clk) begin
        if (CE && !CSB) begin
            if (!WEB && M_C) begin
                $display("[PROTOCOL ASSERTION FAIL @ %0t ns] Illegal simultaneous Write (WEB=0) and Compute (M_C=1)!", $time);
                errors = errors + 1;
            end
        end
    end

    // --- HELPER TASKS FOR SYNCHRONOUS STIMULUS --- //
   
    // Task to write data to a specific address (Also loads R[flag])
    task write_mem(input [ADDR_WIDTH-1:0] write_addr, input [DATA_WIDTH-1:0] data);
        begin
            @(negedge clk); // Drive inputs on negedge to ensure posedge stability
            CE = 1; CSB = 0; WEB = 0; OEB = 1; M_C = 0;
            A = write_addr;
            I = data;
            @(posedge clk); // Wait for synchronous write & R[flag] capture
        end
    endtask

    // Task to trigger a synchronous read
    task read_mem(input [ADDR_WIDTH-1:0] read_addr);
        begin
            @(negedge clk);
            CE = 1; CSB = 0; WEB = 1; OEB = 0; M_C = 0;
            A = read_addr;
            @(posedge clk); // Wait for synchronous read to execute
        end
    endtask

    // Task to trigger synchronous In-Memory Computation
    task trigger_compute(input [DATA_WIDTH-1:0] op1_val, input [DATA_WIDTH-1:0] op2_val);
        begin
            // 2 Consecutive Write Cycles to Implicitly Load R[0] and R[1] via Flag Toggle
            write_mem({addr_width}'d0, op1_val); // Cycle 1: Loads R[0], flag: 0 -> 1
            write_mem({addr_width}'d0, op2_val); // Cycle 2: Loads R[1], flag: 1 -> 0

            // Cycle 3: Switch to Computation Mode (M_C = 1)
            @(negedge clk);
            CE = 1; CSB = 0; WEB = 1; OEB = 1; M_C = 1;
            A = {addr_width}'d0;
            @(posedge clk); // Execute single-cycle addition {{Carry, O}} = R[0] + R[1]
        end
    endtask

    // Task to deselect chip (idle state)
    task deselect_chip();
        begin
            @(negedge clk);
            CE = 0; CSB = 1; WEB = 1; OEB = 1; M_C = 0;
        end
    endtask

    // --- MAIN VERIFICATION ALGORITHM --- //
    initial begin
        $dumpfile("imc_sram_waveform.vcd");
        $dumpvars(0, tb_sram_16x4_IMC_updated);
        file_handle = $fopen("imc_verification_audit_report.txt", "w");

        // 1. Initialize Signals
        clk = 0;
        CE = 0; CSB = 1; WEB = 1; OEB = 1; M_C = 0; A = 0; I = 0;
       
        $display("--------------------------------------------------");
        $display("Starting Synchronous IMC Verification Algorithm...");
        $display("--------------------------------------------------");
        $fwrite(file_handle, "=== IMC-SRAM VERIFICATION AUDIT LOG ===\\n");

        #40;

        // 2. PHASE 1: Populate Memory Array
        $display("-> Phase 1: Populating Memory Array...");
        for (addr = 0; addr < DEPTH; addr = addr + 1) begin
            write_mem(addr, addr[DATA_WIDTH-1:0]);
        end
        deselect_chip();
        #20;

        // 3. PHASE 2: Exhaustive Compute Verification ({max_combinations} Combinations)
        $display("-> Phase 2: Testing {max_combinations} Exhaustive Compute Combinations...");
        for (op1 = 0; op1 < {val_limit}; op1 = op1 + 1) begin
            for (op2 = 0; op2 < {val_limit}; op2 = op2 + 1) begin
               
                total_compute_tests = total_compute_tests + 1;
                trigger_compute(op1[DATA_WIDTH-1:0], op2[DATA_WIDTH-1:0]);

                // Sample synchronous output on the falling edge
                @(negedge clk);
                expected_sum = op1 + op2;
               
                if ({{Carry, O}} !== expected_sum) begin
                    $display("[FAIL-COMPUTE] Op1:%0d, Op2:%0d | Expected: %0d, Got: %0d (Carry: %b, O: %0d)",
                              op1, op2, expected_sum, {{Carry, O}}, Carry, O);
                    $fwrite(file_handle, "[FAIL-COMPUTE] Op1:%0d + Op2:%0d != %0d\\n", op1, op2, {{Carry, O}});
                    errors = errors + 1;
                end
            end
        end
        deselect_chip();
        #20;

        // 4. PHASE 3: Memory Integrity Verification
        write_mem({addr_width}'d0, {data_width}'d0);
        write_mem({addr_width}'d0, {data_width}'d0);
        deselect_chip();
        #10;

        $display("-> Phase 3: Validating Memory Retention (Synchronous Reads)...");
        for (addr = 0; addr < DEPTH; addr = addr + 1) begin
            total_memory_tests = total_memory_tests + 1;
            read_mem(addr);
           
            @(negedge clk);
            if (O !== addr[DATA_WIDTH-1:0]) begin
                $display("[FAIL-MEMORY] Addr: %0d | Expected Data: %0d, Read Data: %0d", addr, addr[DATA_WIDTH-1:0], O);
                errors = errors + 1;
            end
        end
        deselect_chip();

        // 5. Final Report
        $display("--------------------------------------------------");
        $display("Verification Complete!");
        $display("Total Compute Operations : %0d", total_compute_tests);
        $display("Total Memory Reads       : %0d", total_memory_tests);
        if (errors == 0) begin
            $display("STATUS: PASSED - 0 Faults Detected.");
            $display("Synchronous Logic, Addressing, and IMC Periphery are fully operational.");
            $fwrite(file_handle, "SUMMARY: PASSED (%0d Compute Tests, %0d Memory Reads, 0 Errors)\\n", total_compute_tests, total_memory_tests);
        end else begin
            $display("STATUS: FAILED - %0d Faults Detected.", errors);
            $fwrite(file_handle, "SUMMARY: FAILED (%0d Errors)\\n", errors);
        end
        $display("--------------------------------------------------");
        
        $fclose(file_handle);
        $finish;
    end

endmodule
"""
    return tb_code


# ============================================================================
# STREAMLIT PAGE SETUP & HARDWARE STATE INITIALIZATION
# ============================================================================

st.set_page_config(
    page_title="3D Gate-Level IMC-SRAM Silicon Studio",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

if 'mem' not in st.session_state:
    st.session_state.mem = [i for i in range(16)]
if 'R0' not in st.session_state:
    st.session_state.R0 = 9
if 'R1' not in st.session_state:
    st.session_state.R1 = 7
if 'flag' not in st.session_state:
    st.session_state.flag = 0
if 'O' not in st.session_state:
    st.session_state.O = 0
if 'Carry' not in st.session_state:
    st.session_state.Carry = 1
if 'last_op' not in st.session_state:
    st.session_state.last_op = "COMPUTE"  # WRITE_R0, WRITE_R1, READ, COMPUTE
if 'active_addr' not in st.session_state:
    st.session_state.active_addr = 6
if 'last_input_I' not in st.session_state:
    st.session_state.last_input_I = 7
if 'cycle_count' not in st.session_state:
    st.session_state.cycle_count = 3
if 'seq_stage' not in st.session_state:
    st.session_state.seq_stage = 0  # 0 -> Cycle 1 (Write R0), 1 -> Cycle 2 (Write R1), 2 -> Cycle 3 (Compute)
if 'history' not in st.session_state:
    st.session_state.history = [
        {"cycle": 1, "op": "CYCLE 1: WRITE (mem[5]<=9, R[0]<=9)", "CE": 1, "CSB": 0, "WEB": 0, "OEB": 1, "M_C": 0, "A": 5, "I": 9, "R0": 9, "R1": 0, "flag": "0→1", "O": 0, "Carry": 0},
        {"cycle": 2, "op": "CYCLE 2: WRITE (mem[6]<=7, R[1]<=7)", "CE": 1, "CSB": 0, "WEB": 0, "OEB": 1, "M_C": 0, "A": 6, "I": 7, "R0": 9, "R1": 7, "flag": "1→0", "O": 0, "Carry": 0},
        {"cycle": 3, "op": "CYCLE 3: IMC COMPUTE (9 + 7 = 16)", "CE": 1, "CSB": 0, "WEB": 1, "OEB": 1, "M_C": 1, "A": 6, "I": 7, "R0": 9, "R1": 7, "flag": "0", "O": 0, "Carry": 1},
    ]

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Plus+Jakarta+Sans:wght@300;400;600;800&family=JetBrains+Mono:wght@400;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }

    .stApp {
        background: #030712;
        color: #F8FAFC;
    }

    .hero-card {
        background: rgba(15, 23, 42, 0.85);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(0, 240, 255, 0.35);
        border-radius: 18px;
        padding: 18px 26px;
        margin-bottom: 14px;
        box-shadow: 0 0 25px rgba(0, 240, 255, 0.12);
    }

    .hero-title {
        font-family: 'Orbitron', sans-serif;
        font-size: 1.9rem;
        font-weight: 900;
        background: linear-gradient(135deg, #00F0FF 0%, #A855F7 50%, #EC4899 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 4px;
    }

    .hero-subtitle {
        color: #94A3B8;
        font-size: 0.9rem;
    }

    .glass-panel {
        background: rgba(15, 23, 42, 0.72);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 14px;
        padding: 16px;
        margin-bottom: 14px;
    }

    .metric-card {
        background: rgba(15, 23, 42, 0.92);
        border: 1px solid rgba(0, 240, 255, 0.25);
        border-radius: 12px;
        padding: 10px 8px;
        text-align: center;
    }

    .metric-val {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.05rem;
        font-weight: 700;
        color: #00F0FF;
        white-space: nowrap;
    }

    .metric-lbl {
        font-size: 0.68rem;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 4px;
    }

    .stButton > button {
        background: linear-gradient(135deg, #0284C7 0%, #7C3AED 100%) !important;
        color: #FFFFFF !important;
        font-family: 'Orbitron', sans-serif !important;
        font-weight: 700 !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 10px 14px !important;
        font-size: 0.82rem !important;
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# SIDEBAR: STEP-BY-STEP CYCLE SEQUENCER (PERSISTENT 3D CAMERA ZOOM)
# ============================================================================
with st.sidebar:
    st.markdown("<h3 style='font-family: Orbitron; color: #00F0FF; margin-bottom:4px;'>🎛️ Cycle-by-Cycle Sequencer</h3>", unsafe_allow_html=True)
    st.caption("1 Click = 1 Clock Edge (`@posedge clk`). Your 3D camera zoom & angle remain locked across every cycle.")

    op_mode = st.selectbox(
        "⚡ Execution Mode",
        [
            "⏱️ Step-by-Step 3-Cycle IMC Sequencer (1 Click = 1 Cycle)",
            "🚀 Instant 3-Cycle IMC Macro (All 3 Cycles at Once)",
            "🔧 Manual Single Cycle (Write / Read / Compute)"
        ],
        index=0
    )

    if op_mode in [
        "⏱️ Step-by-Step 3-Cycle IMC Sequencer (1 Click = 1 Cycle)",
        "🚀 Instant 3-Cycle IMC Macro (All 3 Cycles at Once)"
    ]:
        st.markdown("##### 🔢 Configure Operands & Addresses")
        c1, c2 = st.columns(2)
        with c1:
            op1_val = st.number_input("Operand 1 (`R[0]`)", min_value=0, max_value=15, value=9, key="in_op1")
            addr1_val = st.number_input("Write Addr 1", min_value=0, max_value=15, value=5, key="in_a1")
        with c2:
            op2_val = st.number_input("Operand 2 (`R[1]`)", min_value=0, max_value=15, value=7, key="in_op2")
            addr2_val = st.number_input("Write Addr 2", min_value=0, max_value=15, value=6, key="in_a2")

        if op_mode == "⏱️ Step-by-Step 3-Cycle IMC Sequencer (1 Click = 1 Cycle)":
            stage_names = [
                f"NEXT CLICK ➔ CYCLE 1: Write Op1 ({op1_val}) to mem[{addr1_val}] & R[0] (flag: 0→1)",
                f"NEXT CLICK ➔ CYCLE 2: Write Op2 ({op2_val}) to mem[{addr2_val}] & R[1] (flag: 1→0)",
                f"NEXT CLICK ➔ CYCLE 3: IMC Compute R[0]({st.session_state.R0}) + R[1]({st.session_state.R1}) (M_C=1)"
            ]
            st.info(stage_names[st.session_state.seq_stage])

            if st.button("⏭️ STEP 1 CYCLE AHEAD (@posedge clk)", type="primary"):
                st.session_state.cycle_count += 1
                if st.session_state.seq_stage == 0:
                    st.session_state.mem[addr1_val] = op1_val
                    st.session_state.R0 = op1_val
                    st.session_state.flag = 1
                    st.session_state.active_addr = addr1_val
                    st.session_state.last_input_I = op1_val
                    st.session_state.last_op = "WRITE_R0"
                    st.session_state.seq_stage = 1
                    st.session_state.history.append({
                        "cycle": st.session_state.cycle_count,
                        "op": f"STEP C1: mem[{addr1_val}]<={op1_val}, R[0]<={op1_val}",
                        "CE": 1, "CSB": 0, "WEB": 0, "OEB": 1, "M_C": 0,
                        "A": addr1_val, "I": op1_val, "R0": st.session_state.R0, "R1": st.session_state.R1,
                        "flag": "0→1", "O": st.session_state.O, "Carry": st.session_state.Carry
                    })
                elif st.session_state.seq_stage == 1:
                    st.session_state.mem[addr2_val] = op2_val
                    st.session_state.R1 = op2_val
                    st.session_state.flag = 0
                    st.session_state.active_addr = addr2_val
                    st.session_state.last_input_I = op2_val
                    st.session_state.last_op = "WRITE_R1"
                    st.session_state.seq_stage = 2
                    st.session_state.history.append({
                        "cycle": st.session_state.cycle_count,
                        "op": f"STEP C2: mem[{addr2_val}]<={op2_val}, R[1]<={op2_val}",
                        "CE": 1, "CSB": 0, "WEB": 0, "OEB": 1, "M_C": 0,
                        "A": addr2_val, "I": op2_val, "R0": st.session_state.R0, "R1": st.session_state.R1,
                        "flag": "1→0", "O": st.session_state.O, "Carry": st.session_state.Carry
                    })
                else:
                    total = st.session_state.R0 + st.session_state.R1
                    st.session_state.O = total & 0xF
                    st.session_state.Carry = (total >> 4) & 0x1
                    st.session_state.last_op = "COMPUTE"
                    st.session_state.seq_stage = 0
                    st.session_state.history.append({
                        "cycle": st.session_state.cycle_count,
                        "op": f"STEP C3 (IMC): {st.session_state.R0} + {st.session_state.R1} = {total}",
                        "CE": 1, "CSB": 0, "WEB": 1, "OEB": 1, "M_C": 1,
                        "A": st.session_state.active_addr, "I": st.session_state.last_input_I,
                        "R0": st.session_state.R0, "R1": st.session_state.R1,
                        "flag": "0", "O": st.session_state.O, "Carry": st.session_state.Carry
                    })
                st.rerun()

        else:
            if st.button("⚡ EXECUTE ALL 3 CYCLES NOW", type="primary"):
                st.session_state.mem[addr1_val] = op1_val
                st.session_state.R0 = op1_val
                st.session_state.cycle_count += 1
                st.session_state.history.append({
                    "cycle": st.session_state.cycle_count,
                    "op": f"MACRO C1: mem[{addr1_val}]<={op1_val}, R[0]<={op1_val}",
                    "CE": 1, "CSB": 0, "WEB": 0, "OEB": 1, "M_C": 0,
                    "A": addr1_val, "I": op1_val, "R0": op1_val, "R1": st.session_state.R1,
                    "flag": "0→1", "O": st.session_state.O, "Carry": st.session_state.Carry
                })
                st.session_state.mem[addr2_val] = op2_val
                st.session_state.R1 = op2_val
                st.session_state.cycle_count += 1
                st.session_state.history.append({
                    "cycle": st.session_state.cycle_count,
                    "op": f"MACRO C2: mem[{addr2_val}]<={op2_val}, R[1]<={op2_val}",
                    "CE": 1, "CSB": 0, "WEB": 0, "OEB": 1, "M_C": 0,
                    "A": addr2_val, "I": op2_val, "R0": op1_val, "R1": op2_val,
                    "flag": "1→0", "O": st.session_state.O, "Carry": st.session_state.Carry
                })
                total = op1_val + op2_val
                st.session_state.O = total & 0xF
                st.session_state.Carry = (total >> 4) & 0x1
                st.session_state.flag = 0
                st.session_state.active_addr = addr2_val
                st.session_state.last_input_I = op2_val
                st.session_state.last_op = "COMPUTE"
                st.session_state.seq_stage = 0
                st.session_state.cycle_count += 1
                st.session_state.history.append({
                    "cycle": st.session_state.cycle_count,
                    "op": f"MACRO C3 (IMC): {op1_val} + {op2_val} = {total}",
                    "CE": 1, "CSB": 0, "WEB": 1, "OEB": 1, "M_C": 1,
                    "A": addr2_val, "I": op2_val, "R0": op1_val, "R1": op2_val,
                    "flag": "0", "O": st.session_state.O, "Carry": st.session_state.Carry
                })
                st.rerun()

    else:
        manual_act = st.radio(
            "Select Single-Cycle Operation",
            ["Write Memory (`WEB=0, OEB=1, M_C=0`)", "Read Memory (`WEB=1, OEB=0, M_C=0`)", "IMC Compute (`M_C=1`)"]
        )
        c_a, c_i = st.columns(2)
        with c_a:
            addr_in = st.number_input("Address `A` (0-15)", min_value=0, max_value=15, value=st.session_state.active_addr)
        with c_i:
            data_in = st.number_input("Data Input `I` (0-15)", min_value=0, max_value=15, value=st.session_state.last_input_I)

        st.info(f"Current `flag = {st.session_state.flag}` ➔ Next Write loads **`R[{st.session_state.flag}]`**")

        if st.button("⏱️ EXECUTE 1 CLOCK CYCLE", type="primary"):
            st.session_state.active_addr = addr_in
            st.session_state.last_input_I = data_in
            st.session_state.cycle_count += 1

            if manual_act.startswith("Write"):
                old_f = st.session_state.flag
                st.session_state.mem[addr_in] = data_in
                if old_f == 0:
                    st.session_state.R0 = data_in
                    st.session_state.last_op = "WRITE_R0"
                else:
                    st.session_state.R1 = data_in
                    st.session_state.last_op = "WRITE_R1"
                st.session_state.flag = 1 - old_f
                st.session_state.history.append({
                    "cycle": st.session_state.cycle_count,
                    "op": f"WRITE mem[{addr_in}]<={data_in}, R[{old_f}]<={data_in}",
                    "CE": 1, "CSB": 0, "WEB": 0, "OEB": 1, "M_C": 0,
                    "A": addr_in, "I": data_in, "R0": st.session_state.R0, "R1": st.session_state.R1,
                    "flag": f"{old_f}→{st.session_state.flag}", "O": st.session_state.O, "Carry": st.session_state.Carry
                })
            elif manual_act.startswith("Read"):
                st.session_state.O = st.session_state.mem[addr_in]
                st.session_state.last_op = "READ"
                st.session_state.history.append({
                    "cycle": st.session_state.cycle_count,
                    "op": f"READ O <= mem[{addr_in}] ({st.session_state.O})",
                    "CE": 1, "CSB": 0, "WEB": 1, "OEB": 0, "M_C": 0,
                    "A": addr_in, "I": data_in, "R0": st.session_state.R0, "R1": st.session_state.R1,
                    "flag": str(st.session_state.flag), "O": st.session_state.O, "Carry": st.session_state.Carry
                })
            else:
                total = st.session_state.R0 + st.session_state.R1
                st.session_state.O = total & 0xF
                st.session_state.Carry = (total >> 4) & 0x1
                st.session_state.last_op = "COMPUTE"
                st.session_state.history.append({
                    "cycle": st.session_state.cycle_count,
                    "op": f"IMC COMPUTE: {st.session_state.R0} + {st.session_state.R1} = {total}",
                    "CE": 1, "CSB": 0, "WEB": 1, "OEB": 1, "M_C": 1,
                    "A": addr_in, "I": data_in, "R0": st.session_state.R0, "R1": st.session_state.R1,
                    "flag": str(st.session_state.flag), "O": st.session_state.O, "Carry": st.session_state.Carry
                })
            st.rerun()

    st.markdown("---")
    if st.button("🔄 Reset Hardware to Phase-1 Init"):
        st.session_state.mem = [i for i in range(16)]
        st.session_state.R0 = 9
        st.session_state.R1 = 7
        st.session_state.flag = 0
        st.session_state.O = 0
        st.session_state.Carry = 1
        st.session_state.last_op = "COMPUTE"
        st.session_state.active_addr = 6
        st.session_state.last_input_I = 7
        st.session_state.cycle_count = 3
        st.session_state.seq_stage = 0
        st.rerun()

    st.markdown("---")
    param_depth = st.selectbox("RTL Parameter `DEPTH`", [16, 32, 64], index=0)
    param_width = st.selectbox("RTL Parameter `DATA_WIDTH`", [4, 8, 16], index=0)


# ============================================================================
# COMPUTE BIT-LEVEL FULL ADDER INTERNAL SIGNALS (FA0, FA1, FA2, FA3)
# ============================================================================
r0_val = st.session_state.R0
r1_val = st.session_state.R1
fa_stages = []
c_in = 0
for bit in range(4):
    a_b = (r0_val >> bit) & 1
    b_b = (r1_val >> bit) & 1
    axorb = a_b ^ b_b
    ab_and = a_b & b_b
    cin_and = c_in & axorb
    s_b = axorb ^ c_in
    c_out = ab_and | cin_and
    fa_stages.append({
        "bit": bit,
        "a": a_b,
        "b": b_b,
        "cin": c_in,
        "axorb": axorb,
        "ab_and": ab_and,
        "cin_and": cin_and,
        "sum": s_b,
        "cout": c_out
    })
    c_in = c_out

# Hero Header
st.markdown("""
<div class="hero-card">
    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 4px;">
        <span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: #00F0FF; box-shadow: 0 0 12px #00F0FF;"></span>
        <span style="font-family: 'Orbitron', monospace; font-size: 0.75rem; font-weight: 700; color: #00F0FF; letter-spacing: 0.14em;">INTERACTIVE MULTI-WORLD SILICON & GATE-LEVEL WORKBENCH</span>
    </div>
    <div class="hero-title">🧠 3D In-Memory Computing (IMC) SRAM Hardware Studio</div>
    <div class="hero-subtitle">
        <b>Persistent Zoom Cycle-by-Cycle Execution</b> + <b>Textbook 6T SRAM & Gate-Level Worlds</b>: Click any memory cell (<code>mem[0]–mem[15]</code>) or functional block to inspect its complete CMOS transistor and logic-gate schematic!
    </div>
</div>
""", unsafe_allow_html=True)

# Top Telemetry Bar
m1, m2, m3, m4, m5, m6 = st.columns(6)
with m1:
    st.markdown(f"""<div class="metric-card"><div class="metric-val" style="color:#00F0FF;">R[0] = {r0_val} (4'b{r0_val:04b})</div><div class="metric-lbl">Operand 1 D-FF Bank</div></div>""", unsafe_allow_html=True)
with m2:
    st.markdown(f"""<div class="metric-card"><div class="metric-val" style="color:#A855F7;">R[1] = {r1_val} (4'b{r1_val:04b})</div><div class="metric-lbl">Operand 2 D-FF Bank</div></div>""", unsafe_allow_html=True)
with m3:
    f_col = "#F59E0B" if st.session_state.flag == 1 else "#10B981"
    st.markdown(f"""<div class="metric-card"><div class="metric-val" style="color:{f_col};">SEL flag = {st.session_state.flag}</div><div class="metric-lbl">1:2 Demux Target: R[{st.session_state.flag}]</div></div>""", unsafe_allow_html=True)
with m4:
    st.markdown(f"""<div class="metric-card"><div class="metric-val" style="color:#10B981;">O = {st.session_state.O} (4'b{st.session_state.O:04b})</div><div class="metric-lbl">Output Bus O[3:0]</div></div>""", unsafe_allow_html=True)
with m5:
    c_col = "#FF0055" if st.session_state.Carry == 1 else "#38BDF8"
    st.markdown(f"""<div class="metric-card"><div class="metric-val" style="color:{c_col};">Carry = {st.session_state.Carry} (C4)</div><div class="metric-lbl">FA3 Carry-Out Bit</div></div>""", unsafe_allow_html=True)
with m6:
    st.markdown(f"""<div class="metric-card"><div class="metric-val" style="color:#EC4899;">{r0_val} + {r1_val} = {r0_val+r1_val} (5'b{r0_val+r1_val:05b})</div><div class="metric-lbl">4-Bit Ripple Adder Out</div></div>""", unsafe_allow_html=True)

st.write("")

# ============================================================================
# 3D INTERACTIVE WEBGL VIEWPORT + PERSISTENT CAMERA + GATE-LEVEL WORLD
# ============================================================================
mem_json = json.dumps(st.session_state.mem)
fa_json = json.dumps(fa_stages)

three_js_multiworld_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@600;800&family=JetBrains+Mono:wght@500;700&display=swap');
        body {{ margin: 0; padding: 0; overflow: hidden; background-color: #030712; font-family: 'JetBrains Mono', monospace; user-select: none; }}
        #canvas-container {{ width: 100vw; height: 650px; position: relative; cursor: grab; }}
        #canvas-container:active {{ cursor: grabbing; }}

        .hud-top-left {{
            position: absolute;
            top: 12px;
            left: 12px;
            background: rgba(15, 23, 42, 0.92);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(0, 240, 255, 0.45);
            border-radius: 12px;
            padding: 12px 16px;
            color: #F8FAFC;
            box-shadow: 0 8px 25px rgba(0,0,0,0.65);
            z-index: 15;
            max-width: 540px;
        }}

        .hud-title {{
            font-family: 'Orbitron', sans-serif;
            font-size: 0.82rem;
            font-weight: 800;
            color: #00F0FF;
            letter-spacing: 0.06em;
            margin-bottom: 5px;
        }}

        .hud-top-right {{
            position: absolute;
            top: 12px;
            right: 12px;
            background: rgba(15, 23, 42, 0.92);
            border: 1px solid rgba(236, 72, 153, 0.55);
            border-radius: 12px;
            padding: 12px 16px;
            color: #F8FAFC;
            z-index: 15;
            text-align: right;
        }}

        .alu-equation {{
            font-family: 'Orbitron', monospace;
            font-size: 0.96rem;
            font-weight: 800;
            color: #EC4899;
            margin-top: 3px;
        }}

        .bottom-bar {{
            position: absolute;
            bottom: 12px;
            left: 12px;
            right: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 10px;
            z-index: 15;
            pointer-events: none;
        }}

        .btn-group {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            background: rgba(15, 23, 42, 0.92);
            border: 1px solid rgba(0, 240, 255, 0.35);
            border-radius: 10px;
            padding: 6px 10px;
            pointer-events: auto;
        }}

        .cyber-btn {{
            background: rgba(30, 41, 59, 0.9);
            border: 1px solid rgba(56, 189, 248, 0.45);
            color: #E2E8F0;
            font-family: 'Orbitron', sans-serif;
            font-size: 0.7rem;
            font-weight: 700;
            padding: 6px 11px;
            border-radius: 7px;
            cursor: pointer;
            transition: all 0.2s ease;
        }}

        .cyber-btn:hover {{
            background: #0284C7;
            color: #FFFFFF;
            border-color: #00F0FF;
            box-shadow: 0 0 12px rgba(0, 240, 255, 0.4);
        }}

        .cyber-btn.active-btn {{
            background: linear-gradient(135deg, #EC4899 0%, #7C3AED 100%);
            border-color: #F472B6;
            color: #FFFFFF;
        }}

        /* GATE-LEVEL SCHEMATIC WORLD OVERLAY ("DIFFERENT WORLD") */
        #gate-world-modal {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: radial-gradient(circle at center, #0B1120 0%, #020617 100%);
            z-index: 30;
            display: none;
            flex-direction: column;
            justify-content: space-between;
            padding: 16px 22px;
            box-sizing: border-box;
        }}

        .gw-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(15, 23, 42, 0.92);
            border: 1px solid rgba(0, 240, 255, 0.45);
            border-radius: 14px;
            padding: 10px 18px;
            gap: 12px;
        }}

        .gw-title {{
            font-family: 'Orbitron', sans-serif;
            font-size: 1.05rem;
            font-weight: 800;
            color: #00F0FF;
        }}

        .gw-sub {{
            font-size: 0.76rem;
            color: #94A3B8;
            margin-top: 2px;
        }}

        .back-btn {{
            background: linear-gradient(135deg, #EF4444 0%, #B91C1C 100%);
            color: white;
            border: 1px solid #FCA5A5;
            font-family: 'Orbitron', sans-serif;
            font-size: 0.75rem;
            font-weight: 800;
            padding: 9px 16px;
            border-radius: 9px;
            cursor: pointer;
            white-space: nowrap;
            box-shadow: 0 0 18px rgba(239, 68, 68, 0.45);
        }}

        .back-btn:hover {{
            transform: scale(1.03);
        }}

        #sram-subcontrols {{
            display: none;
            justify-content: space-between;
            align-items: center;
            background: rgba(15, 23, 42, 0.85);
            border: 1px solid rgba(56, 189, 248, 0.35);
            border-radius: 10px;
            padding: 7px 14px;
            margin-top: 8px;
        }}

        #schematic-svg-box {{
            flex: 1;
            margin: 10px 0;
            background: rgba(9, 14, 28, 0.9);
            border: 1px solid rgba(168, 85, 247, 0.35);
            border-radius: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            overflow: hidden;
        }}

        .gw-footer {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(15, 23, 42, 0.92);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 12px;
            padding: 9px 16px;
            font-size: 0.76rem;
            color: #CBD5E1;
        }}
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
</head>
<body>
    <div id="canvas-container">
        <!-- Top Left HUD -->
        <div class="hud-top-left">
            <div class="hud-title">⚡ CYCLE #{st.session_state.cycle_count} • ACTIVE OPERATION: {st.session_state.last_op}</div>
            <div style="font-size: 0.75rem; color: #CBD5E1; line-height: 1.5;">
                Addr: <b style="color:#10B981;">A = {st.session_state.active_addr} (4'b{st.session_state.active_addr:04b})</b> |
                In: <b style="color:#F59E0B;">I = {st.session_state.last_input_I} (4'b{st.session_state.last_input_I:04b})</b> |
                Demux SEL: <b style="color:#00F0FF;">flag = {st.session_state.flag}</b><br/>
                <span style="color:#38BDF8;">🔒 <b>CAMERA ZOOM LOCKED</b> • <b>CLICK ANY SRAM CELL OR 3D BLOCK</b> for Gate-Level World!</span>
            </div>
        </div>

        <!-- Top Right HUD -->
        <div class="hud-top-right">
            <div style="font-size: 0.72rem; color: #CBD5E1; text-transform: uppercase;">Live Hardware State</div>
            <div class="alu-equation">
                R[0]({r0_val}) + R[1]({r1_val}) = {r0_val + r1_val} (Carry={st.session_state.Carry}, O={st.session_state.O})
            </div>
            <div style="font-size: 0.72rem; color: #10B981; margin-top: 3px;" id="prop-status-text">
                ⚡ Propagating Current Cycle...
            </div>
        </div>

        <!-- Bottom Bar: Replay Single Cycle, Reset Camera View & Quick Gate-World Buttons -->
        <div class="bottom-bar">
            <div class="btn-group">
                <button class="cyber-btn active-btn" onclick="replayCycleAnimation()">🔄 Replay Cycle Step</button>
                <button class="cyber-btn" onclick="stepSubStage(0.25)">25%</button>
                <button class="cyber-btn" onclick="stepSubStage(0.60)">60%</button>
                <button class="cyber-btn" onclick="stepSubStage(1.00)">100%</button>
                <button class="cyber-btn" onclick="resetCameraView()" title="Reset 3D Zoom to Default Overview">📷 Reset View</button>
            </div>
            <div class="btn-group">
                <span style="font-size:0.7rem; color:#94A3B8; align-self:center; margin-right:4px;">🔬 Gate World:</span>
                <button class="cyber-btn" onclick="openGateWorld('SRAM_' + activeAddr)">6T SRAM Cell</button>
                <button class="cyber-btn" onclick="openGateWorld('DEMUX')">1:2 Demux</button>
                <button class="cyber-btn" onclick="openGateWorld('REG_R0')">R[0] D-FFs</button>
                <button class="cyber-btn" onclick="openGateWorld('REG_R1')">R[1] D-FFs</button>
                <button class="cyber-btn" onclick="openGateWorld('FA0')">FA0</button>
                <button class="cyber-btn" onclick="openGateWorld('FA1')">FA1</button>
                <button class="cyber-btn" onclick="openGateWorld('FA2')">FA2</button>
                <button class="cyber-btn" onclick="openGateWorld('FA3')">FA3</button>
                <button class="cyber-btn" onclick="openGateWorld('OUT_MUX')">2:1 Mux</button>
            </div>
        </div>

        <!-- ================================================================ -->
        <!-- GATE-LEVEL SCHEMATIC WORLD MODAL ("DIFFERENT WORLD" VIEW)        -->
        <!-- ================================================================ -->
        <div id="gate-world-modal">
            <div class="gw-header">
                <div>
                    <div class="gw-title" id="gw-title-text">🔬 GATE-LEVEL MICRO-ARCHITECTURE WORLD</div>
                    <div class="gw-sub" id="gw-sub-text">Live Boolean Logic Gates, Transistor Paths, and Real-Time Wire Voltages (1 = Neon High, 0 = Low)</div>
                </div>
                <button class="back-btn" onclick="closeGateWorld()">🔙 RETURN TO 3D SILICON FLOORPLAN</button>
            </div>

            <!-- Interactive Sub-Controls for 6T SRAM Bit-Slice & Topology Switching -->
            <div id="sram-subcontrols">
                <div style="display:flex; gap:6px; align-items:center;">
                    <span style="font-size:0.74rem; color:#00F0FF; font-family:'Orbitron'; font-weight:700;">🔎 Inspect Bitcell in 4-Bit Word:</span>
                    <button class="cyber-btn" id="bit-btn-3" onclick="selectSramBit(3)">Bit 3 (MSB)</button>
                    <button class="cyber-btn" id="bit-btn-2" onclick="selectSramBit(2)">Bit 2</button>
                    <button class="cyber-btn" id="bit-btn-1" onclick="selectSramBit(1)">Bit 1</button>
                    <button class="cyber-btn" id="bit-btn-0" onclick="selectSramBit(0)">Bit 0 (LSB)</button>
                </div>
                <div style="display:flex; gap:6px; align-items:center;">
                    <span style="font-size:0.74rem; color:#A855F7; font-family:'Orbitron'; font-weight:700;">📐 Circuit View:</span>
                    <button class="cyber-btn active-btn" id="topo-btn-latch" onclick="selectSramTopology('LATCH')">1️⃣ Cross-Coupled Inverter Latch + M5/M6</button>
                    <button class="cyber-btn" id="topo-btn-cmos" onclick="selectSramTopology('CMOS')">2️⃣ Full 6-Transistor CMOS (M1–M6)</button>
                </div>
            </div>

            <div id="schematic-svg-box"></div>

            <div class="gw-footer">
                <div id="gw-equation-bar">Boolean Equation: </div>
                <div style="display:flex; gap:6px;">
                    <button class="cyber-btn" onclick="openGateWorld('SRAM_' + sramInspectAddr)">6T SRAM</button>
                    <button class="cyber-btn" onclick="openGateWorld('DEMUX')">1:2 Demux</button>
                    <button class="cyber-btn" onclick="openGateWorld('REG_R0')">R[0] D-FFs</button>
                    <button class="cyber-btn" onclick="openGateWorld('FA0')">FA0</button>
                    <button class="cyber-btn" onclick="openGateWorld('FA1')">FA1</button>
                    <button class="cyber-btn" onclick="openGateWorld('FA2')">FA2</button>
                    <button class="cyber-btn" onclick="openGateWorld('FA3')">FA3</button>
                    <button class="cyber-btn" onclick="openGateWorld('OUT_MUX')">2:1 Mux</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Hardware State Injected from Streamlit
        const memData = {mem_json};
        const faData = {fa_json};
        const activeAddr = {st.session_state.active_addr};
        const inputI = {st.session_state.last_input_I};
        const valR0 = {r0_val};
        const valR1 = {r1_val};
        const valFlag = {st.session_state.flag};
        const valO = {st.session_state.O};
        const valCarry = {st.session_state.Carry};
        const lastOp = "{st.session_state.last_op}";
        const isMC = (lastOp === "COMPUTE") ? 1 : 0;

        // Interactive 6T SRAM World State
        let sramInspectAddr = activeAddr;
        let sramInspectBit = 0;
        let sramTopology = 'LATCH'; // 'LATCH' or 'CMOS'

        // ====================================================================
        // PERSISTENT CAMERA ZOOM & ORBIT STATE ACROSS STREAMLIT CYCLES
        // ====================================================================
        const DEFAULT_CAM = {{ px: 2.5, py: 25, pz: 29, tx: 2.5, ty: 0, tz: 0 }};

        function loadSavedCameraState() {{
            try {{
                if (window.parent && window.parent.__imcCamState) {{
                    return window.parent.__imcCamState;
                }}
            }} catch (e) {{}}
            try {{
                const saved = localStorage.getItem('imc_sram_camera_v1');
                if (saved) return JSON.parse(saved);
            }} catch (e) {{}}
            return DEFAULT_CAM;
        }}

        function saveCurrentCameraState() {{
            const state = {{
                px: camera.position.x,
                py: camera.position.y,
                pz: camera.position.z,
                tx: controls.target.x,
                ty: controls.target.y,
                tz: controls.target.z
            }};
            try {{
                if (window.parent) window.parent.__imcCamState = state;
            }} catch (e) {{}}
            try {{
                localStorage.setItem('imc_sram_camera_v1', JSON.stringify(state));
            }} catch (e) {{}}
        }}

        const container = document.getElementById('canvas-container');
        const scene = new THREE.Scene();
        scene.fog = new THREE.FogExp2(0x030712, 0.010);

        const camera = new THREE.PerspectiveCamera(40, container.clientWidth / container.clientHeight, 0.1, 1000);
        const initCam = loadSavedCameraState();
        camera.position.set(initCam.px, initCam.py, initCam.pz);

        const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: true }});
        renderer.setSize(container.clientWidth, container.clientHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.shadowMap.enabled = true;
        container.appendChild(renderer.domElement);

        const controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.06;
        controls.target.set(initCam.tx, initCam.ty, initCam.tz);
        controls.update();

        controls.addEventListener('change', saveCurrentCameraState);

        window.resetCameraView = function() {{
            camera.position.set(DEFAULT_CAM.px, DEFAULT_CAM.py, DEFAULT_CAM.pz);
            controls.target.set(DEFAULT_CAM.tx, DEFAULT_CAM.ty, DEFAULT_CAM.tz);
            controls.update();
            saveCurrentCameraState();
        }};

        scene.add(new THREE.AmbientLight(0x1E293B, 2.6));
        const dirLight = new THREE.DirectionalLight(0x00F0FF, 1.9);
        dirLight.position.set(18, 30, 22);
        scene.add(dirLight);

        const pointLight = new THREE.PointLight(0xEC4899, 2.5, 35);
        pointLight.position.set(9, 8, 0);
        scene.add(pointLight);

        // Raycaster for Clicking 3D Hardware Units to Open Gate World
        const raycaster = new THREE.Raycaster();
        const mouse = new THREE.Vector2();
        const clickableMeshes = [];

        function registerClickable(mesh, unitId) {{
            mesh.userData.unitId = unitId;
            clickableMeshes.push(mesh);
        }}

        function createLabel(title, subtitle, bgColor, borderColor, w = 4.2, h = 1.35) {{
            const canvas = document.createElement('canvas');
            canvas.width = 512;
            canvas.height = 168;
            const ctx = canvas.getContext('2d');

            ctx.fillStyle = bgColor;
            ctx.strokeStyle = borderColor;
            ctx.lineWidth = 7;
            ctx.beginPath();
            ctx.roundRect(8, 8, 496, 152, 20);
            ctx.fill();
            ctx.stroke();

            ctx.fillStyle = '#FFFFFF';
            ctx.font = 'bold 35px Orbitron, monospace';
            ctx.textAlign = 'center';
            ctx.fillText(title, 256, 68);

            ctx.fillStyle = '#38BDF8';
            ctx.font = 'bold 26px JetBrains Mono, monospace';
            ctx.fillText(subtitle, 256, 124);

            const tex = new THREE.CanvasTexture(canvas);
            const mat = new THREE.SpriteMaterial({{ map: tex, transparent: true, depthTest: false }});
            const sprite = new THREE.Sprite(mat);
            sprite.scale.set(w, h, 1);
            return sprite;
        }}

        function createTrapezoidMesh(leftHalfZ, rightHalfZ, widthX, heightY, colorHex, edgeHex) {{
            const shape = new THREE.Shape();
            shape.moveTo(-widthX / 2, -leftHalfZ);
            shape.lineTo(widthX / 2, -rightHalfZ);
            shape.lineTo(widthX / 2, rightHalfZ);
            shape.lineTo(-widthX / 2, leftHalfZ);
            shape.closePath();

            const extrudeSettings = {{ depth: heightY, bevelEnabled: true, bevelSegments: 2, steps: 1, bevelSize: 0.06, bevelThickness: 0.06 }};
            const geo = new THREE.ExtrudeGeometry(shape, extrudeSettings);
            geo.rotateX(-Math.PI / 2);

            const mat = new THREE.MeshStandardMaterial({{
                color: colorHex, roughness: 0.22, metalness: 0.8, emissive: colorHex, emissiveIntensity: 0.45
            }});
            const mesh = new THREE.Mesh(geo, mat);
            mesh.add(new THREE.LineSegments(new THREE.EdgesGeometry(geo), new THREE.LineBasicMaterial({{ color: edgeHex }})));
            return mesh;
        }}

        // Silicon Substrate Base
        const dieGeo = new THREE.BoxGeometry(34, 0.5, 17);
        const dieMesh = new THREE.Mesh(dieGeo, new THREE.MeshStandardMaterial({{ color: 0x080D1A, roughness: 0.35, metalness: 0.85 }}));
        dieMesh.position.set(2.5, -0.3, 0);
        scene.add(dieMesh);
        const dieEdges = new THREE.LineSegments(new THREE.EdgesGeometry(dieGeo), new THREE.LineBasicMaterial({{ color: 0x00F0FF, transparent: true, opacity: 0.45 }}));
        dieEdges.position.copy(dieMesh.position);
        scene.add(dieEdges);

        const grid = new THREE.GridHelper(44, 44, 0x00F0FF, 0x1E293B);
        grid.position.y = -0.6;
        scene.add(grid);

        // ====================================================================
        // STAGE 1: 16x4 SRAM ARRAY (EACH CELL OPENS ITS EXACT 6T SRAM WORLD!)
        // ====================================================================
        const sramHeader = createLabel("16x4 SRAM ARRAY (Click Any Cell)", `Active Word: mem[${{activeAddr}}] = ${{memData[activeAddr]}}`, "rgba(15,23,42,0.95)", "#00F0FF", 5.5, 1.45);
        sramHeader.position.set(-8.2, 3.8, -5.8);
        scene.add(sramHeader);

        const cellGeo = new THREE.BoxGeometry(1.4, 0.7, 1.4);
        let addrIdx = 0;
        for (let r = 0; r < 4; r++) {{
            for (let c = 0; c < 4; c++) {{
                const isSel = (addrIdx === activeAddr);
                const cell = new THREE.Mesh(cellGeo, new THREE.MeshStandardMaterial({{
                    color: isSel ? 0x10B981 : 0x0284C7, roughness: 0.25, metalness: 0.75,
                    emissive: isSel ? 0x10B981 : 0x002244, emissiveIntensity: isSel ? 0.9 : 0.28
                }}));
                cell.position.set(-11.2 + c * 1.95, 0.4, -3.0 + r * 2.0);
                cell.add(new THREE.LineSegments(new THREE.EdgesGeometry(cellGeo), new THREE.LineBasicMaterial({{ color: isSel ? 0x6EE7B7 : 0x38BDF8 }})));

                const val = memData[addrIdx];
                const tag = createLabel(`mem[${{addrIdx}}]`, `D:${{val}} (${{val.toString(2).padStart(4,'0')}})`, "rgba(2,6,23,0.9)", isSel ? "#10B981" : "#0284C7", 1.65, 0.58);
                tag.position.set(0, 0.82, 0);
                cell.add(tag);

                registerClickable(cell, `SRAM_${{addrIdx}}`);
                scene.add(cell);
                addrIdx++;
            }}
        }}

        // ====================================================================
        // STAGE 2: TRAPEZOIDAL 1:2 WRITE DEMUX (CLICKABLE -> DEMUX GATE WORLD)
        // ====================================================================
        const demuxMesh = createTrapezoidMesh(0.85, 2.35, 1.9, 1.0, 0xF59E0B, 0xFDE68A);
        demuxMesh.position.set(-2.2, 0.1, 0);
        registerClickable(demuxMesh, "DEMUX");
        scene.add(demuxMesh);

        const demuxLabel = createLabel("1:2 WRITE DEMUX (Click)", `SEL(flag)=${{valFlag}} • I=${{inputI}}`, "rgba(35,20,4,0.95)", "#F59E0B", 4.6, 1.35);
        demuxLabel.position.set(-2.2, 2.7, 0);
        scene.add(demuxLabel);

        // ====================================================================
        // STAGE 3: 4-BIT D-FF OPERAND BANKS R[0] & R[1] (CLICKABLE)
        // ====================================================================
        const regBankGeo = new THREE.BoxGeometry(3.2, 0.9, 2.6);
        const dffGeo = new THREE.BoxGeometry(0.62, 0.45, 0.9);

        const r0Bank = new THREE.Mesh(regBankGeo, new THREE.MeshStandardMaterial({{
            color: 0x06B6D4, roughness: 0.25, metalness: 0.8, emissive: 0x06B6D4,
            emissiveIntensity: (lastOp === "WRITE_R0" || lastOp === "COMPUTE") ? 0.75 : 0.25
        }}));
        r0Bank.position.set(2.4, 0.5, -3.6);
        r0Bank.add(new THREE.LineSegments(new THREE.EdgesGeometry(regBankGeo), new THREE.LineBasicMaterial({{ color: 0x67E8F9 }})));
        registerClickable(r0Bank, "REG_R0");
        scene.add(r0Bank);

        for (let b = 0; b < 4; b++) {{
            const bitVal = (valR0 >> b) & 1;
            const dff = new THREE.Mesh(dffGeo, new THREE.MeshStandardMaterial({{
                color: bitVal ? 0x00F0FF : 0x1E293B, emissive: bitVal ? 0x00F0FF : 0x000000, emissiveIntensity: bitVal ? 0.8 : 0.1
            }}));
            dff.position.set(-1.05 + b * 0.7, 0.65, 0);
            r0Bank.add(dff);
        }}

        const r0Tag = createLabel(`REG R[0] = ${{valR0}} (Click)`, `4-Bit D-FF: [${{valR0.toString(2).padStart(4,'0')}}]₂`, "rgba(6,32,48,0.95)", "#00F0FF", 4.2, 1.3);
        r0Tag.position.set(2.4, 2.35, -3.6);
        scene.add(r0Tag);

        const r1Bank = new THREE.Mesh(regBankGeo, new THREE.MeshStandardMaterial({{
            color: 0x8B5CF6, roughness: 0.25, metalness: 0.8, emissive: 0x8B5CF6,
            emissiveIntensity: (lastOp === "WRITE_R1" || lastOp === "COMPUTE") ? 0.75 : 0.25
        }}));
        r1Bank.position.set(2.4, 0.5, 3.6);
        r1Bank.add(new THREE.LineSegments(new THREE.EdgesGeometry(regBankGeo), new THREE.LineBasicMaterial({{ color: 0xC4B5FD }})));
        registerClickable(r1Bank, "REG_R1");
        scene.add(r1Bank);

        for (let b = 0; b < 4; b++) {{
            const bitVal = (valR1 >> b) & 1;
            const dff = new THREE.Mesh(dffGeo, new THREE.MeshStandardMaterial({{
                color: bitVal ? 0xA855F7 : 0x1E293B, emissive: bitVal ? 0xA855F7 : 0x000000, emissiveIntensity: bitVal ? 0.85 : 0.1
            }}));
            dff.position.set(-1.05 + b * 0.7, 0.65, 0);
            r1Bank.add(dff);
        }}

        const r1Tag = createLabel(`REG R[1] = ${{valR1}} (Click)`, `4-Bit D-FF: [${{valR1.toString(2).padStart(4,'0')}}]₂`, "rgba(28,12,50,0.95)", "#A855F7", 4.2, 1.3);
        r1Tag.position.set(2.4, 2.35, 3.6);
        scene.add(r1Tag);

        // ====================================================================
        // STAGE 4: 4-STAGE RIPPLE-CARRY FULL ADDER ARRAY (FA0..FA3, CLICKABLE)
        // ====================================================================
        const faBaseGeo = new THREE.BoxGeometry(3.3, 0.85, 2.1);
        const gateBoxGeo = new THREE.BoxGeometry(1.1, 0.55, 0.75);

        for (let i = 0; i < 4; i++) {{
            const stg = faData[i];
            const posZ = -4.8 + i * 3.2;

            const faMesh = new THREE.Mesh(faBaseGeo, new THREE.MeshStandardMaterial({{
                color: 0xBE185D, roughness: 0.25, metalness: 0.8, emissive: 0xEC4899, emissiveIntensity: stg.sum ? 0.65 : 0.25
            }}));
            faMesh.position.set(8.8, 0.45, posZ);
            faMesh.add(new THREE.LineSegments(new THREE.EdgesGeometry(faBaseGeo), new THREE.LineBasicMaterial({{ color: 0xF472B6 }})));
            registerClickable(faMesh, `FA${{i}}`);

            const xorGate = new THREE.Mesh(gateBoxGeo, new THREE.MeshStandardMaterial({{
                color: stg.sum ? 0x10B981 : 0x0284C7, emissive: stg.sum ? 0x10B981 : 0x000000, emissiveIntensity: stg.sum ? 0.85 : 0.2
            }}));
            xorGate.position.set(-0.75, 0.68, -0.35);
            faMesh.add(xorGate);

            const carryGate = new THREE.Mesh(gateBoxGeo, new THREE.MeshStandardMaterial({{
                color: stg.cout ? 0xF59E0B : 0x475569, emissive: stg.cout ? 0xF59E0B : 0x000000, emissiveIntensity: stg.cout ? 0.9 : 0.15
            }}));
            carryGate.position.set(0.75, 0.68, 0.35);
            faMesh.add(carryGate);

            const faTag = createLabel(
                `FA${{i}} (Click): ${{stg.a}}+${{stg.b}}+Cin(${{stg.cin}})`,
                `Sum[${{i}}]=${{stg.sum}} | Cout=${{stg.cout}}`,
                "rgba(35,8,26,0.94)", stg.sum ? "#10B981" : "#EC4899", 3.7, 1.05
            );
            faTag.position.set(0, 1.65, 0);
            faMesh.add(faTag);

            scene.add(faMesh);
        }}

        // ====================================================================
        // STAGE 5: TRAPEZOIDAL 2:1 OUTPUT MUX & RESULT PORT (CLICKABLE)
        // ====================================================================
        const outMuxMesh = createTrapezoidMesh(2.3, 0.95, 1.8, 1.0, 0x10B981, 0x6EE7B7);
        outMuxMesh.position.set(14.0, 0.1, 0);
        registerClickable(outMuxMesh, "OUT_MUX");
        scene.add(outMuxMesh);

        const muxLabel = createLabel("2:1 OUTPUT MUX (Click)", `SEL(M_C)=${{isMC}} ➔ O=${{valO}}`, "rgba(6,38,28,0.95)", "#10B981", 4.5, 1.35);
        muxLabel.position.set(14.0, 2.6, 0);
        scene.add(muxLabel);

        const outPortGeo = new THREE.BoxGeometry(2.3, 1.1, 3.0);
        const outPort = new THREE.Mesh(outPortGeo, new THREE.MeshStandardMaterial({{
            color: 0x059669, roughness: 0.2, metalness: 0.85, emissive: 0x10B981, emissiveIntensity: 0.75
        }}));
        outPort.position.set(17.2, 0.55, 0);
        outPort.add(new THREE.LineSegments(new THREE.EdgesGeometry(outPortGeo), new THREE.LineBasicMaterial({{ color: 0xA7F3D0 }})));
        registerClickable(outPort, "OUT_MUX");
        scene.add(outPort);

        const outPortLabel = createLabel(`OUT: {{C=${{valCarry}}, O=${{valO}}}}`, `5-Bit Result = ${{(valCarry<<4)|valO}} (${{((valCarry<<4)|valO).toString(2).padStart(5,'0')}}₂)`, "rgba(4,45,32,0.96)", "#34D399", 4.6, 1.4);
        outPortLabel.position.set(17.2, 2.35, 0);
        scene.add(outPortLabel);

        // ====================================================================
        // HARDWARE BUS INTERCONNECT TRACES
        // ====================================================================
        function drawTrace(pts, hexCol) {{
            const vecs = pts.map(p => new THREE.Vector3(...p));
            const geo = new THREE.BufferGeometry().setFromPoints(vecs);
            scene.add(new THREE.Line(geo, new THREE.LineBasicMaterial({{ color: hexCol }})));
            return vecs;
        }}

        const busInToDemux = drawTrace([[-5.0, 0.45, 0], [-3.1, 0.45, 0]], 0xF59E0B);
        const busDemuxToR0 = drawTrace([[-1.2, 0.5, -1.2], [-0.2, 0.5, -3.6], [2.4, 0.5, -3.6]], 0x00F0FF);
        const busDemuxToR1 = drawTrace([[-1.2, 0.5, 1.2], [-0.2, 0.5, 3.6], [2.4, 0.5, 3.6]], 0xA855F7);
        const busR0ToFA = drawTrace([[2.4, 0.55, -3.6], [5.8, 0.55, -3.6], [5.8, 0.55, -1.6], [8.8, 0.55, -1.6]], 0x00F0FF);
        const busR1ToFA = drawTrace([[2.4, 0.55, 3.6], [5.8, 0.55, 3.6], [5.8, 0.55, 1.6], [8.8, 0.55, 1.6]], 0xA855F7);
        for (let i = 0; i < 3; i++) {{
            const z1 = -4.8 + i * 3.2 + 1.05;
            const z2 = -4.8 + (i + 1) * 3.2 - 1.05;
            drawTrace([[9.55, 0.9, z1], [9.55, 0.9, z2]], 0xF59E0B);
        }}
        const busFAToMux = drawTrace([[8.8, 0.55, 0], [14.0, 0.55, 0]], 0xEC4899);
        const busMuxToOut = drawTrace([[14.0, 0.55, 0], [17.2, 0.55, 0]], 0x10B981);
        const busSramRead = drawTrace([[-8.0, 0.3, -6.5], [12.2, 0.3, -6.5], [12.2, 0.3, -1.2], [17.2, 0.3, 0]], 0x38BDF8);

        // ====================================================================
        // SINGLE-SHOT CYCLE PROPAGATION PACKETS (STOPS AT DESTINATION!)
        // ====================================================================
        const pktMain = createLabel(
            lastOp.startsWith("WRITE") ? `WRITE I = ${{inputI}}` : (lastOp === "READ" ? `READ = ${{valO}}` : `R[0] = ${{valR0}}`),
            lastOp.startsWith("WRITE") ? `4'b${{inputI.toString(2).padStart(4,'0')}} ➔ R[${{lastOp === 'WRITE_R0' ? 0 : 1}}]` : `4'b${{(lastOp === 'READ' ? valO : valR0).toString(2).padStart(4,'0')}}`,
            "rgba(4,35,48,0.96)", "#00F0FF", 2.8, 0.92
        );
        scene.add(pktMain);

        const pktSecond = createLabel(
            `R[1] = ${{valR1}}`,
            `4'b${{valR1.toString(2).padStart(4,'0')}}`,
            "rgba(32,10,52,0.96)", "#A855F7", 2.5, 0.88
        );
        scene.add(pktSecond);

        const pktResult = createLabel(
            `SUM = ${{valR0 + valR1}}`,
            `Carry=${{valCarry}}, O=${{valO}}`,
            "rgba(4,45,30,0.96)", "#10B981", 2.8, 0.92
        );
        scene.add(pktResult);

        function pointAlongPath(vecs, tNorm) {{
            const clamped = Math.max(0, Math.min(1, tNorm));
            const totalSegs = vecs.length - 1;
            const scaled = clamped * totalSegs;
            const idx = Math.min(Math.floor(scaled), totalSegs - 1);
            const frac = scaled - idx;
            return new THREE.Vector3().lerpVectors(vecs[idx], vecs[idx + 1], frac);
        }}

        let cycleProgress = 0.0;
        let isPlayingCycle = true;
        const statusEl = document.getElementById('prop-status-text');

        window.replayCycleAnimation = function() {{
            cycleProgress = 0.0;
            isPlayingCycle = true;
        }};

        window.stepSubStage = function(targetP) {{
            cycleProgress = targetP;
            isPlayingCycle = false;
            updatePacketPositions(cycleProgress);
        }};

        function updatePacketPositions(p) {{
            if (lastOp === "WRITE_R0") {{
                pktSecond.visible = false;
                pktResult.visible = false;
                const fullPath = [...busInToDemux, ...busDemuxToR0];
                const pos = pointAlongPath(fullPath, p);
                pktMain.position.set(pos.x, 1.45, pos.z);
                statusEl.innerText = p < 1.0
                    ? `⏱️ CYCLE 1 STEP: Routing I=${{inputI}} through 1:2 Demux (flag=0) ➔ R[0] (${{Math.round(p*100)}}%)`
                    : `✅ CYCLE 1 LOCKED: mem[${{activeAddr}}] = ${{inputI}} & R[0] = ${{valR0}} (flag toggled 0➔1)`;
            }} else if (lastOp === "WRITE_R1") {{
                pktSecond.visible = false;
                pktResult.visible = false;
                const fullPath = [...busInToDemux, ...busDemuxToR1];
                const pos = pointAlongPath(fullPath, p);
                pktMain.position.set(pos.x, 1.45, pos.z);
                statusEl.innerText = p < 1.0
                    ? `⏱️ CYCLE 2 STEP: Routing I=${{inputI}} through 1:2 Demux (flag=1) ➔ R[1] (${{Math.round(p*100)}}%)`
                    : `✅ CYCLE 2 LOCKED: mem[${{activeAddr}}] = ${{inputI}} & R[1] = ${{valR1}} (flag toggled 1➔0)`;
            }} else if (lastOp === "READ") {{
                pktSecond.visible = false;
                pktResult.visible = false;
                const pos = pointAlongPath(busSramRead, p);
                pktMain.position.set(pos.x, 1.45, pos.z);
                statusEl.innerText = p < 1.0
                    ? `⏱️ READ CYCLE STEP: Fetching mem[${{activeAddr}}] = ${{valO}} to Output Bus (${{Math.round(p*100)}}%)`
                    : `✅ READ CYCLE LOCKED: Output O = ${{valO}}`;
            }} else {{
                pktSecond.visible = true;
                const pIn = Math.min(1.0, p / 0.55);
                const pos0 = pointAlongPath(busR0ToFA, pIn);
                const pos1 = pointAlongPath(busR1ToFA, pIn);
                pktMain.position.set(pos0.x, 1.45, pos0.z);
                pktSecond.position.set(pos1.x, 1.45, pos1.z);

                if (p > 0.45) {{
                    pktResult.visible = true;
                    const pOut = Math.min(1.0, (p - 0.45) / 0.55);
                    const outPath = [...busFAToMux, ...busMuxToOut];
                    const posOut = pointAlongPath(outPath, pOut);
                    pktResult.position.set(posOut.x, 1.55, posOut.z);
                }} else {{
                    pktResult.visible = false;
                }}

                statusEl.innerText = p < 1.0
                    ? `⏱️ CYCLE 3 (IMC COMPUTE): R[0](${{valR0}}) + R[1](${{valR1}}) Rippling through FA0–FA3 (${{Math.round(p*100)}}%)`
                    : `✅ CYCLE 3 LOCKED: {{Carry=${{valCarry}}, O=${{valO}}}} = ${{valR0 + valR1}} (Settled at Output)`;
            }}
        }}

        // Click Detection to Open Gate-Level World
        let downPos = {{ x: 0, y: 0 }};
        renderer.domElement.addEventListener('pointerdown', (e) => {{
            downPos = {{ x: e.clientX, y: e.clientY }};
        }});

        renderer.domElement.addEventListener('pointerup', (e) => {{
            const dist = Math.hypot(e.clientX - downPos.x, e.clientY - downPos.y);
            if (dist > 6) return;

            const rect = renderer.domElement.getBoundingClientRect();
            mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
            mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

            raycaster.setFromCamera(mouse, camera);
            const intersects = raycaster.intersectObjects(clickableMeshes, true);
            if (intersects.length > 0) {{
                let obj = intersects[0].object;
                while (obj && !obj.userData.unitId) {{
                    obj = obj.parent;
                }}
                if (obj && obj.userData.unitId) {{
                    openGateWorld(obj.userData.unitId);
                }}
            }}
        }});

        // ====================================================================
        // TEXTBOOK-ACCURATE 6T SRAM SCHEMATIC RENDERER (LATCH & 6-CMOS VIEWS)
        // ====================================================================
        window.selectSramBit = function(bitIdx) {{
            sramInspectBit = bitIdx;
            renderSramSchematic();
        }};

        window.selectSramTopology = function(topo) {{
            sramTopology = topo;
            document.getElementById('topo-btn-latch').className = (topo === 'LATCH') ? 'cyber-btn active-btn' : 'cyber-btn';
            document.getElementById('topo-btn-cmos').className = (topo === 'CMOS') ? 'cyber-btn active-btn' : 'cyber-btn';
            renderSramSchematic();
        }};

        function renderSramSchematic() {{
            const titleEl = document.getElementById('gw-title-text');
            const subEl = document.getElementById('gw-sub-text');
            const eqEl = document.getElementById('gw-equation-bar');
            const box = document.getElementById('schematic-svg-box');

            const wordV = memData[sramInspectAddr];
            const bitQ = (wordV >> sramInspectBit) & 1;
            const bitQB = 1 - bitQ;
            const wlHigh = (sramInspectAddr === activeAddr) ? 1 : 0;

            for (let b = 0; b < 4; b++) {{
                const bVal = (wordV >> b) & 1;
                const btn = document.getElementById('bit-btn-' + b);
                if (btn) {{
                    btn.innerText = `Bit ${{b}} (Q=${{bVal}})`;
                    btn.className = (b === sramInspectBit) ? 'cyber-btn active-btn' : 'cyber-btn';
                }}
            }}

            const qCol = bitQ ? "#10B981" : "#38BDF8";
            const qbCol = bitQB ? "#10B981" : "#A855F7";
            const wlCol = wlHigh ? "#F59E0B" : "#64748B";

            titleEl.innerText = `🔬 6T SRAM BITCELL SCHEMATIC: Word mem[${{sramInspectAddr}}] = ${{wordV}} (4'b${{wordV.toString(2).padStart(4,'0')}}) • Inspecting Bit [${{sramInspectBit}}]`;
            subEl.innerText = `Storage Node Q = ${{bitQ}}, Complementary Node ~Q = ${{bitQB}} | Wordline WL[${{sramInspectAddr}}] = ${{wlHigh}} (${{wlHigh ? 'ACTIVE HIGH - Access NMOS M5/M6 ON' : 'LOW - Bitcell Latched / Isolated'}})`;
            eqEl.innerHTML = `<b>Bistable Latch State:</b> Q = ~(~Q) = <b style="color:${{qCol}}">${{bitQ}}</b> &nbsp;|&nbsp; ~Q (QB) = ~(Q) = <b style="color:${{qbCol}}">${{bitQB}}</b> &nbsp;|&nbsp; Word mem[${{sramInspectAddr}}] = <b style="color:#00F0FF">4'b${{wordV.toString(2).padStart(4,'0')}} (${{wordV}})</b>`;

            if (sramTopology === 'LATCH') {{
                // VIEW 1: TEXTBOOK CROSS-COUPLED INVERTER LATCH + NMOS PASS TRANSISTORS M5 & M6
                box.innerHTML = `
                <svg viewBox="0 0 960 420" width="97%" height="97%">
                    <!-- 1. BITLINE (BL) LEFT RAIL & BITLINE BAR (~BL) RIGHT RAIL -->
                    <line x1="105" y1="25" x2="105" y2="365" stroke="#00F0FF" stroke-width="5"/>
                    <text x="105" y="390" fill="#00F0FF" font-family="Orbitron" font-size="14" font-weight="bold" text-anchor="middle">BITLINE (BL = ${{bitQ}})</text>

                    <line x1="855" y1="25" x2="855" y2="365" stroke="#A855F7" stroke-width="5"/>
                    <text x="855" y="390" fill="#C4B5FD" font-family="Orbitron" font-size="14" font-weight="bold" text-anchor="middle">BITLINE BAR (~BL = ${{bitQB}})</text>

                    <!-- 2. WORDLINE (WL) HORIZONTAL TOP BUS + VERTICAL GATE DROPS TO M5 & M6 -->
                    <line x1="60" y1="52" x2="900" y2="52" stroke="${{wlCol}}" stroke-width="4"/>
                    <text x="480" y="36" fill="#FDE68A" font-family="Orbitron" font-size="15" font-weight="bold" text-anchor="middle">
                        WORDLINE WL[${{sramInspectAddr}}] = ${{wlHigh}} (${{wlHigh ? 'SELECTED: M5 & M6 CONDUCTING' : 'UNSELECTED: M5 & M6 OFF'}})
                    </text>

                    <!-- WL Vertical Gate Drop into Access NMOS M5 -->
                    <circle cx="220" cy="52" r="6" fill="${{wlCol}}"/>
                    <line x1="220" y1="52" x2="220" y2="155" stroke="${{wlCol}}" stroke-width="3.5"/>

                    <!-- WL Vertical Gate Drop into Access NMOS M6 -->
                    <circle cx="740" cy="52" r="6" fill="${{wlCol}}"/>
                    <line x1="740" y1="52" x2="740" y2="155" stroke="${{wlCol}}" stroke-width="3.5"/>

                    <!-- 3. ACCESS TRANSISTOR NMOS M5 (Left Pass Gate Connecting BL <-> Node Q) -->
                    <circle cx="105" cy="200" r="6" fill="#00F0FF"/>
                    <line x1="105" y1="200" x2="185" y2="200" stroke="#00F0FF" stroke-width="4"/>

                    <!-- M5 MOSFET Symbol Box & Insulated Gate -->
                    <rect x="170" y="142" width="100" height="86" rx="10" fill="rgba(15,23,42,0.9)" stroke="#10B981" stroke-width="2.5"/>
                    <line x1="195" y1="155" x2="245" y2="155" stroke="${{wlCol}}" stroke-width="4"/>
                    <line x1="190" y1="166" x2="250" y2="166" stroke="#10B981" stroke-width="3.5"/>
                    <line x1="195" y1="166" x2="195" y2="200" stroke="#10B981" stroke-width="3.5"/>
                    <line x1="245" y1="166" x2="245" y2="200" stroke="#10B981" stroke-width="3.5"/>
                    <line x1="185" y1="200" x2="195" y2="200" stroke="#10B981" stroke-width="3.5"/>
                    <line x1="245" y1="200" x2="255" y2="200" stroke="#10B981" stroke-width="3.5"/>
                    <text x="220" y="218" fill="#6EE7B7" font-family="Orbitron" font-size="12" font-weight="bold" text-anchor="middle">NMOS M5</text>

                    <!-- Wire from M5 Drain to Storage Node Q (x=330, y=200) -->
                    <line x1="255" y1="200" x2="330" y2="200" stroke="${{qCol}}" stroke-width="4.5"/>

                    <!-- 4. STORAGE NODE Q (x=330) & CROSS-COUPLED LATCH LOOP -->
                    <circle cx="330" cy="200" r="7" fill="${{qCol}}"/>
                    <rect x="278" y="170" width="44" height="24" rx="5" fill="#064E3B" stroke="${{qCol}}" stroke-width="2"/>
                    <text x="300" y="187" fill="#FFF" font-family="Orbitron" font-size="13" font-weight="bold" text-anchor="middle">Q=${{bitQ}}</text>

                    <!-- Node Q Vertical Feedback Spine (y=120 to y=280) -->
                    <line x1="330" y1="120" x2="330" y2="280" stroke="${{qCol}}" stroke-width="4"/>
                    <!-- Top Branch: Node Q (330,120) -> Input of INV 1 (430,120) -->
                    <line x1="330" y1="120" x2="430" y2="120" stroke="${{qCol}}" stroke-width="4"/>
                    <!-- Bottom Branch: Output of INV 2 (430,280) -> Node Q (330,280) -->
                    <line x1="330" y1="280" x2="430" y2="280" stroke="${{qCol}}" stroke-width="4"/>

                    <!-- 5. TOP INVERTER INV 1 (PMOS M2 + NMOS M1, Pointing Right ➔) -->
                    <polygon points="430,85 430,155 512,120" fill="#083344" stroke="#00F0FF" stroke-width="3.5"/>
                    <circle cx="520" cy="120" r="7" fill="#083344" stroke="#00F0FF" stroke-width="3.5"/>
                    <text x="462" y="125" fill="#FFF" font-family="Orbitron" font-size="12" font-weight="bold" text-anchor="middle">INV 1</text>
                    <text x="475" y="74" fill="#00F0FF" font-family="Orbitron" font-size="13" font-weight="bold" text-anchor="middle">CMOS INV 1 (M1/M2)</text>

                    <!-- Top Branch Output: INV 1 Output (527,120) -> Node ~Q (630,120) -->
                    <line x1="527" y1="120" x2="630" y2="120" stroke="${{qbCol}}" stroke-width="4"/>

                    <!-- 6. BOTTOM INVERTER INV 2 (PMOS M4 + NMOS M3, Pointing Left ⬅) -->
                    <polygon points="530,245 530,315 448,280" fill="#2E1065" stroke="#A855F7" stroke-width="3.5"/>
                    <circle cx="440" cy="280" r="7" fill="#2E1065" stroke="#A855F7" stroke-width="3.5"/>
                    <text x="498" y="285" fill="#FFF" font-family="Orbitron" font-size="12" font-weight="bold" text-anchor="middle">INV 2</text>
                    <text x="485" y="338" fill="#C4B5FD" font-family="Orbitron" font-size="13" font-weight="bold" text-anchor="middle">CMOS INV 2 (M3/M4)</text>

                    <!-- Bottom Branch Input: Node ~Q (630,280) -> INV 2 Input (530,280) -->
                    <line x1="530" y1="280" x2="630" y2="280" stroke="${{qbCol}}" stroke-width="4"/>

                    <!-- 7. STORAGE NODE ~Q (QB, x=630) -->
                    <line x1="630" y1="120" x2="630" y2="280" stroke="${{qbCol}}" stroke-width="4"/>
                    <circle cx="630" cy="200" r="7" fill="${{qbCol}}"/>
                    <rect x="638" y="170" width="54" height="24" rx="5" fill="#2E1065" stroke="${{qbCol}}" stroke-width="2"/>
                    <text x="665" y="187" fill="#FFF" font-family="Orbitron" font-size="13" font-weight="bold" text-anchor="middle">~Q=${{bitQB}}</text>

                    <!-- Wire from Storage Node ~Q (630,200) to M6 Source (705,200) -->
                    <line x1="630" y1="200" x2="705" y2="200" stroke="${{qbCol}}" stroke-width="4.5"/>

                    <!-- 8. ACCESS TRANSISTOR NMOS M6 (Right Pass Gate Connecting Node ~Q <-> ~BL) -->
                    <rect x="690" y="142" width="100" height="86" rx="10" fill="rgba(15,23,42,0.9)" stroke="#10B981" stroke-width="2.5"/>
                    <line x1="715" y1="155" x2="765" y2="155" stroke="${{wlCol}}" stroke-width="4"/>
                    <line x1="710" y1="166" x2="770" y2="166" stroke="#10B981" stroke-width="3.5"/>
                    <line x1="715" y1="166" x2="715" y2="200" stroke="#10B981" stroke-width="3.5"/>
                    <line x1="765" y1="166" x2="765" y2="200" stroke="#10B981" stroke-width="3.5"/>
                    <line x1="705" y1="200" x2="715" y2="200" stroke="#10B981" stroke-width="3.5"/>
                    <line x1="765" y1="200" x2="775" y2="200" stroke="#10B981" stroke-width="3.5"/>
                    <text x="740" y="218" fill="#6EE7B7" font-family="Orbitron" font-size="12" font-weight="bold" text-anchor="middle">NMOS M6</text>

                    <!-- Wire from M6 Drain (775,200) to ~BL (855,200) -->
                    <line x1="775" y1="200" x2="855" y2="200" stroke="#A855F7" stroke-width="4"/>
                    <circle cx="855" cy="200" r="6" fill="#A855F7"/>

                    <!-- 9. BOTTOM SUMMARY BADGE -->
                    <rect x="315" y="362" width="330" height="44" rx="9" fill="#064E3B" stroke="#10B981" stroke-width="3"/>
                    <text x="480" y="389" fill="#FFF" font-family="Orbitron" font-size="15" font-weight="bold" text-anchor="middle">
                        mem[${{sramInspectAddr}}] = 4'b${{wordV.toString(2).padStart(4,'0')}} (${{wordV}}) • Bit[${{sramInspectBit}}] = ${{bitQ}}
                    </text>
                </svg>`;
            }} else {{
                // VIEW 2: FULL 6-TRANSISTOR CMOS CIRCUIT DIAGRAM (M1, M2, M3, M4, M5, M6 + VDD & GND)
                box.innerHTML = `
                <svg viewBox="0 0 960 420" width="97%" height="97%">
                    <!-- Bitlines BL and ~BL -->
                    <line x1="95" y1="20" x2="95" y2="395" stroke="#00F0FF" stroke-width="5"/>
                    <text x="95" y="412" fill="#00F0FF" font-family="Orbitron" font-size="13" font-weight="bold" text-anchor="middle">BL (${{bitQ}})</text>

                    <line x1="865" y1="20" x2="865" y2="395" stroke="#A855F7" stroke-width="5"/>
                    <text x="865" y="412" fill="#C4B5FD" font-family="Orbitron" font-size="13" font-weight="bold" text-anchor="middle">~BL (${{bitQB}})</text>

                    <!-- Wordline WL Top Bus -->
                    <line x1="55" y1="42" x2="905" y2="42" stroke="${{wlCol}}" stroke-width="3.5"/>
                    <text x="480" y="28" fill="#FDE68A" font-family="Orbitron" font-size="14" font-weight="bold" text-anchor="middle">WORDLINE WL[${{sramInspectAddr}}] = ${{wlHigh}}</text>

                    <!-- VDD Supply Rail (Center Top) & GND Rail (Center Bottom) -->
                    <line x1="330" y1="75" x2="630" y2="75" stroke="#EF4444" stroke-width="4"/>
                    <text x="480" y="66" fill="#FCA5A5" font-family="Orbitron" font-size="12" font-weight="bold" text-anchor="middle">VDD (+1.8V SUPPLY RAIL)</text>

                    <line x1="330" y1="365" x2="630" y2="365" stroke="#64748B" stroke-width="4"/>
                    <text x="480" y="385" fill="#94A3B8" font-family="Orbitron" font-size="12" font-weight="bold" text-anchor="middle">GND / VSS (0V GROUND RAIL)</text>

                    <!-- Left CMOS Inverter: PMOS M2 (Pull-Up) + NMOS M1 (Pull-Down) at x=390 -->
                    <line x1="390" y1="75" x2="390" y2="105" stroke="#EF4444" stroke-width="3.5"/>
                    <rect x="355" y="105" width="70" height="52" rx="8" fill="#1E293B" stroke="#F43F5E" stroke-width="2.5"/>
                    <text x="390" y="128" fill="#FDA4AF" font-family="Orbitron" font-size="11" font-weight="bold" text-anchor="middle">PMOS M2</text>
                    <text x="390" y="146" fill="#CBD5E1" font-family="JetBrains Mono" font-size="11" text-anchor="middle">Pull-Up</text>

                    <line x1="390" y1="157" x2="390" y2="275" stroke="${{qCol}}" stroke-width="4.5"/>

                    <rect x="355" y="275" width="70" height="52" rx="8" fill="#1E293B" stroke="#38BDF8" stroke-width="2.5"/>
                    <text x="390" y="298" fill="#7DD3FC" font-family="Orbitron" font-size="11" font-weight="bold" text-anchor="middle">NMOS M1</text>
                    <text x="390" y="316" fill="#CBD5E1" font-family="JetBrains Mono" font-size="11" text-anchor="middle">Pull-Down</text>
                    <line x1="390" y1="327" x2="390" y2="365" stroke="#64748B" stroke-width="3.5"/>

                    <!-- Right CMOS Inverter: PMOS M4 (Pull-Up) + NMOS M3 (Pull-Down) at x=570 -->
                    <line x1="570" y1="75" x2="570" y2="105" stroke="#EF4444" stroke-width="3.5"/>
                    <rect x="535" y="105" width="70" height="52" rx="8" fill="#1E293B" stroke="#F43F5E" stroke-width="2.5"/>
                    <text x="570" y="128" fill="#FDA4AF" font-family="Orbitron" font-size="11" font-weight="bold" text-anchor="middle">PMOS M4</text>
                    <text x="570" y="146" fill="#CBD5E1" font-family="JetBrains Mono" font-size="11" text-anchor="middle">Pull-Up</text>

                    <line x1="570" y1="157" x2="570" y2="275" stroke="${{qbCol}}" stroke-width="4.5"/>

                    <rect x="535" y="275" width="70" height="52" rx="8" fill="#1E293B" stroke="#A855F7" stroke-width="2.5"/>
                    <text x="570" y="298" fill="#C4B5FD" font-family="Orbitron" font-size="11" font-weight="bold" text-anchor="middle">NMOS M3</text>
                    <text x="570" y="316" fill="#CBD5E1" font-family="JetBrains Mono" font-size="11" text-anchor="middle">Pull-Down</text>
                    <line x1="570" y1="327" x2="570" y2="365" stroke="#64748B" stroke-width="3.5"/>

                    <!-- Cross-Coupled Gate Interconnects Between Node Q (x=390) and Node ~Q (x=570) -->
                    <!-- Left Gate Spine (x=442) connecting M2 & M1 gates, driven by Node ~Q (570, 230) -->
                    <line x1="425" y1="131" x2="442" y2="131" stroke="${{qbCol}}" stroke-width="3"/>
                    <line x1="425" y1="301" x2="442" y2="301" stroke="${{qbCol}}" stroke-width="3"/>
                    <line x1="442" y1="131" x2="442" y2="301" stroke="${{qbCol}}" stroke-width="3"/>
                    <line x1="442" y1="185" x2="570" y2="230" stroke="${{qbCol}}" stroke-width="3.5"/>
                    <circle cx="570" cy="230" r="6" fill="${{qbCol}}"/>

                    <!-- Right Gate Spine (x=518) connecting M4 & M3 gates, driven by Node Q (390, 230) -->
                    <line x1="518" y1="131" x2="535" y2="131" stroke="${{qCol}}" stroke-width="3"/>
                    <line x1="518" y1="301" x2="535" y2="301" stroke="${{qCol}}" stroke-width="3"/>
                    <line x1="518" y1="131" x2="518" y2="301" stroke="${{qCol}}" stroke-width="3"/>
                    <line x1="390" y1="230" x2="518" y2="185" stroke="${{qCol}}" stroke-width="3.5"/>
                    <circle cx="390" cy="230" r="6" fill="${{qCol}}"/>

                    <!-- Access NMOS M5 (Left: BL <-> Node Q at y=205) -->
                    <circle cx="95" cy="205" r="6" fill="#00F0FF"/>
                    <line x1="95" y1="205" x2="185" y2="205" stroke="#00F0FF" stroke-width="4"/>
                    <rect x="185" y="175" width="90" height="56" rx="8" fill="#064E3B" stroke="#10B981" stroke-width="3"/>
                    <text x="230" y="200" fill="#FFF" font-family="Orbitron" font-size="12" font-weight="bold" text-anchor="middle">NMOS M5</text>
                    <text x="230" y="218" fill="#6EE7B7" font-family="JetBrains Mono" font-size="11" text-anchor="middle">Access FET</text>
                    <line x1="275" y1="205" x2="390" y2="205" stroke="${{qCol}}" stroke-width="4.5"/>
                    <circle cx="390" cy="205" r="7" fill="${{qCol}}"/>
                    <text x="332" y="192" fill="${{qCol}}" font-family="Orbitron" font-size="14" font-weight="bold" text-anchor="middle">Q = ${{bitQ}}</text>

                    <!-- WL Gate Drop to M5 -->
                    <circle cx="230" cy="42" r="6" fill="${{wlCol}}"/>
                    <line x1="230" y1="42" x2="230" y2="175" stroke="${{wlCol}}" stroke-width="3.5"/>

                    <!-- Access NMOS M6 (Right: Node ~Q <-> ~BL at y=205) -->
                    <circle cx="570" cy="205" r="7" fill="${{qbCol}}"/>
                    <text x="628" y="192" fill="${{qbCol}}" font-family="Orbitron" font-size="14" font-weight="bold" text-anchor="middle">~Q = ${{bitQB}}</text>
                    <line x1="570" y1="205" x2="685" y2="205" stroke="${{qbCol}}" stroke-width="4.5"/>
                    <rect x="685" y="175" width="90" height="56" rx="8" fill="#064E3B" stroke="#10B981" stroke-width="3"/>
                    <text x="730" y="200" fill="#FFF" font-family="Orbitron" font-size="12" font-weight="bold" text-anchor="middle">NMOS M6</text>
                    <text x="730" y="218" fill="#6EE7B7" font-family="JetBrains Mono" font-size="11" text-anchor="middle">Access FET</text>
                    <line x1="775" y1="205" x2="865" y2="205" stroke="#A855F7" stroke-width="4"/>
                    <circle cx="865" cy="205" r="6" fill="#A855F7"/>

                    <!-- WL Gate Drop to M6 -->
                    <circle cx="730" cy="42" r="6" fill="${{wlCol}}"/>
                    <line x1="730" y1="42" x2="730" y2="175" stroke="${{wlCol}}" stroke-width="3.5"/>
                </svg>`;
            }}
        }}

        // ====================================================================
        // GATE-LEVEL SCHEMATIC WORLD GENERATOR (ALL HARDWARE UNITS)
        // ====================================================================
        window.closeGateWorld = function() {{
            document.getElementById('gate-world-modal').style.display = 'none';
        }};

        window.openGateWorld = function(unitId) {{
            const modal = document.getElementById('gate-world-modal');
            const titleEl = document.getElementById('gw-title-text');
            const subEl = document.getElementById('gw-sub-text');
            const eqEl = document.getElementById('gw-equation-bar');
            const box = document.getElementById('schematic-svg-box');
            const sramControls = document.getElementById('sram-subcontrols');
            modal.style.display = 'flex';

            const wCol = (bit) => bit ? "#10B981" : "#38BDF8";

            if (unitId.startsWith("SRAM")) {{
                sramControls.style.display = 'flex';
                if (unitId.includes("_")) {{
                    sramInspectAddr = parseInt(unitId.split("_")[1]);
                }} else {{
                    sramInspectAddr = activeAddr;
                }}
                renderSramSchematic();
                return;
            }}

            sramControls.style.display = 'none';

            if (unitId.startsWith("FA")) {{
                const idx = parseInt(unitId.replace("FA", ""));
                const s = faData[idx];
                titleEl.innerText = `🔬 GATE-LEVEL WORLD: FULL ADDER SLICE FA${{idx}} (BIT ${{idx}})`;
                subEl.innerText = `5-Gate IEEE Full Adder Schematic: 2x XOR Gates, 2x AND Gates, 1x OR Gate • Live Inputs: R0[${{idx}}]=${{s.a}}, R1[${{idx}}]=${{s.b}}, Cin=${{s.cin}}`;
                eqEl.innerHTML = `<b>Live Gate Equations:</b> P = R0[${{idx}}](${{s.a}}) ⊕ R1[${{idx}}](${{s.b}}) = <b style="color:#00F0FF">${{s.axorb}}</b> &nbsp;|&nbsp; <b>Sum[${{idx}}]</b> = P(${{s.axorb}}) ⊕ Cin(${{s.cin}}) = <b style="color:#10B981">${{s.sum}}</b> &nbsp;|&nbsp; <b>Cout</b> = (${{s.a}}&${{s.b}}) | (${{s.cin}}&${{s.axorb}}) = <b style="color:#F59E0B">${{s.cout}}</b>`;

                box.innerHTML = `
                <svg viewBox="0 0 950 420" width="96%" height="96%">
                    <rect x="25" y="55" width="120" height="42" rx="8" fill="#0F172A" stroke="${{wCol(s.a)}}" stroke-width="3"/>
                    <text x="85" y="81" fill="#FFF" font-family="Orbitron" font-size="15" font-weight="bold" text-anchor="middle">R0[${{idx}}] = ${{s.a}}</text>

                    <rect x="25" y="135" width="120" height="42" rx="8" fill="#0F172A" stroke="${{wCol(s.b)}}" stroke-width="3"/>
                    <text x="85" y="161" fill="#FFF" font-family="Orbitron" font-size="15" font-weight="bold" text-anchor="middle">R1[${{idx}}] = ${{s.b}}</text>

                    <rect x="25" y="235" width="120" height="42" rx="8" fill="#0F172A" stroke="${{wCol(s.cin)}}" stroke-width="3"/>
                    <text x="85" y="261" fill="#FFF" font-family="Orbitron" font-size="15" font-weight="bold" text-anchor="middle">Cin[${{idx}}] = ${{s.cin}}</text>

                    <path d="M 145 76 L 280 76" stroke="${{wCol(s.a)}}" stroke-width="4" fill="none"/>
                    <path d="M 145 156 L 240 156 L 240 104 L 280 104" stroke="${{wCol(s.b)}}" stroke-width="4" fill="none"/>
                    <path d="M 200 76 L 200 305 L 280 305" stroke="${{wCol(s.a)}}" stroke-width="3" stroke-dasharray="6,4" fill="none"/>
                    <path d="M 240 156 L 240 335 L 280 335" stroke="${{wCol(s.b)}}" stroke-width="3" stroke-dasharray="6,4" fill="none"/>

                    <path d="M 270 60 Q 288 90 270 120" stroke="#00F0FF" stroke-width="4" fill="none"/>
                    <path d="M 282 60 L 325 60 Q 365 60 385 90 Q 365 120 325 120 L 282 120 Q 300 90 282 60 Z" fill="#1E293B" stroke="#00F0FF" stroke-width="3"/>
                    <text x="330" y="95" fill="#00F0FF" font-family="Orbitron" font-size="14" font-weight="bold" text-anchor="middle">XOR 1</text>
                    <text x="435" y="78" fill="#F8FAFC" font-family="JetBrains Mono" font-size="14" font-weight="bold">P = ${{s.axorb}}</text>

                    <path d="M 385 90 L 530 90" stroke="${{wCol(s.axorb)}}" stroke-width="4" fill="none"/>
                    <path d="M 465 90 L 465 215 L 530 215" stroke="${{wCol(s.axorb)}}" stroke-width="4" fill="none"/>

                    <path d="M 145 256 L 495 256 L 495 122 L 530 122" stroke="${{wCol(s.cin)}}" stroke-width="4" fill="none"/>
                    <path d="M 495 256 L 530 245" stroke="${{wCol(s.cin)}}" stroke-width="4" fill="none"/>

                    <path d="M 520 75 Q 538 105 520 135" stroke="#10B981" stroke-width="4" fill="none"/>
                    <path d="M 532 75 L 575 75 Q 615 75 635 105 Q 615 135 575 135 L 532 135 Q 550 105 532 75 Z" fill="#064E3B" stroke="#10B981" stroke-width="3"/>
                    <text x="580" y="110" fill="#6EE7B7" font-family="Orbitron" font-size="14" font-weight="bold" text-anchor="middle">XOR 2</text>

                    <path d="M 532 200 L 580 200 A 30 30 0 0 1 580 260 L 532 260 Z" fill="#1E293B" stroke="#A855F7" stroke-width="3"/>
                    <text x="568" y="235" fill="#C4B5FD" font-family="Orbitron" font-size="14" font-weight="bold" text-anchor="middle">AND 2</text>
                    <text x="655" y="222" fill="#C4B5FD" font-family="JetBrains Mono" font-size="13">Cin&P = ${{s.cin_and}}</text>

                    <path d="M 282 290 L 330 290 A 30 30 0 0 1 330 350 L 282 350 Z" fill="#1E293B" stroke="#F59E0B" stroke-width="3"/>
                    <text x="318" y="325" fill="#FDE68A" font-family="Orbitron" font-size="14" font-weight="bold" text-anchor="middle">AND 1</text>
                    <text x="415" y="312" fill="#FDE68A" font-family="JetBrains Mono" font-size="13">G = A&B = ${{s.ab_and}}</text>

                    <path d="M 610 230 L 680 230 L 680 272 L 715 272" stroke="${{wCol(s.cin_and)}}" stroke-width="4" fill="none"/>
                    <path d="M 360 320 L 680 320 L 680 302 L 715 302" stroke="${{wCol(s.ab_and)}}" stroke-width="4" fill="none"/>

                    <path d="M 710 255 L 750 255 Q 790 255 810 287 Q 790 320 750 320 L 710 320 Q 728 287 710 255 Z" fill="#451A03" stroke="#F59E0B" stroke-width="3"/>
                    <text x="758" y="292" fill="#FDE68A" font-family="Orbitron" font-size="14" font-weight="bold" text-anchor="middle">OR 1</text>

                    <path d="M 635 105 L 785 105" stroke="${{wCol(s.sum)}}" stroke-width="5" fill="none"/>
                    <rect x="785" y="82" width="145" height="46" rx="9" fill="#064E3B" stroke="#10B981" stroke-width="3"/>
                    <text x="857" y="110" fill="#FFF" font-family="Orbitron" font-size="16" font-weight="bold" text-anchor="middle">O[${{idx}}] = ${{s.sum}}</text>

                    <path d="M 810 287 L 835 287" stroke="${{wCol(s.cout)}}" stroke-width="5" fill="none"/>
                    <rect x="785" y="264" width="145" height="46" rx="9" fill="#451A03" stroke="#F59E0B" stroke-width="3"/>
                    <text x="857" y="292" fill="#FFF" font-family="Orbitron" font-size="16" font-weight="bold" text-anchor="middle">Cout = ${{s.cout}}</text>
                </svg>`;
            }} else if (unitId === "DEMUX") {{
                const sel = valFlag;
                const notSel = 1 - sel;
                const enR0 = (lastOp === "WRITE_R0") ? 1 : 0;
                const enR1 = (lastOp === "WRITE_R1") ? 1 : 0;
                titleEl.innerText = "🔬 GATE-LEVEL WORLD: 1:2 WRITE DEMULTIPLEXER & TOGGLE FLAG (flag <= ~flag)";
                subEl.innerText = "Shows how a single 1-bit T-Flip-Flop (flag) + Inverter + AND Gate Bank steers incoming 4-bit Data Bus I[3:0] into R[0] or R[1]";
                eqEl.innerHTML = `<b>Demux Equations:</b> Load_R0 = (~WEB) & (~flag[${{notSel}}]) = <b style="color:#00F0FF">${{enR0}}</b> &nbsp;|&nbsp; Load_R1 = (~WEB) & (flag[${{sel}}]) = <b style="color:#A855F7">${{enR1}}</b> &nbsp;|&nbsp; Next_flag = ~flag = <b>${{notSel}}</b>`;

                box.innerHTML = `
                <svg viewBox="0 0 920 400" width="95%" height="95%">
                    <rect x="30" y="60" width="160" height="50" rx="8" fill="#0F172A" stroke="#F59E0B" stroke-width="3"/>
                    <text x="110" y="90" fill="#FFF" font-family="Orbitron" font-size="15" font-weight="bold" text-anchor="middle">Bus I[3:0] = ${{inputI}}</text>

                    <rect x="30" y="220" width="160" height="90" rx="10" fill="#1E293B" stroke="#00F0FF" stroke-width="3"/>
                    <text x="110" y="255" fill="#00F0FF" font-family="Orbitron" font-size="15" font-weight="bold" text-anchor="middle">FLAG D-FF</text>
                    <text x="110" y="285" fill="#FFF" font-family="JetBrains Mono" font-size="15" text-anchor="middle">Q(flag) = ${{sel}}</text>

                    <polygon points="310,165 310,205 355,185" fill="#1E293B" stroke="#10B981" stroke-width="3"/>
                    <circle cx="362" cy="185" r="6" fill="#1E293B" stroke="#10B981" stroke-width="3"/>
                    <text x="330" y="155" fill="#10B981" font-family="JetBrains Mono" font-size="13" text-anchor="middle">NOT (~flag=${{notSel}})</text>

                    <path d="M 190 85 L 480 85" stroke="#F59E0B" stroke-width="4" fill="none"/>
                    <path d="M 420 85 L 420 265 L 480 265" stroke="#F59E0B" stroke-width="4" fill="none"/>
                    <path d="M 190 265 L 260 265 L 260 185 L 310 185" stroke="${{wCol(sel)}}" stroke-width="4" fill="none"/>
                    <path d="M 368 185 L 445 185 L 445 125 L 480 125" stroke="${{wCol(notSel)}}" stroke-width="4" fill="none"/>
                    <path d="M 260 265 L 260 305 L 480 305" stroke="${{wCol(sel)}}" stroke-width="4" fill="none"/>

                    <path d="M 480 65 L 550 65 A 40 40 0 0 1 550 145 L 480 145 Z" fill="#083344" stroke="#00F0FF" stroke-width="3"/>
                    <text x="530" y="110" fill="#00F0FF" font-family="Orbitron" font-size="14" font-weight="bold" text-anchor="middle">AND (R0)</text>

                    <path d="M 480 245 L 550 245 A 40 40 0 0 1 550 325 L 480 325 Z" fill="#2E1065" stroke="#A855F7" stroke-width="3"/>
                    <text x="530" y="290" fill="#C4B5FD" font-family="Orbitron" font-size="14" font-weight="bold" text-anchor="middle">AND (R1)</text>

                    <path d="M 590 105 L 700 105" stroke="#00F0FF" stroke-width="5" fill="none"/>
                    <rect x="700" y="75" width="185" height="60" rx="10" fill="#083344" stroke="#00F0FF" stroke-width="3"/>
                    <text x="792" y="110" fill="#FFF" font-family="Orbitron" font-size="15" font-weight="bold" text-anchor="middle">R[0] <= ${{valR0}} (${{valR0.toString(2).padStart(4,'0')}})</text>

                    <path d="M 590 285 L 700 285" stroke="#A855F7" stroke-width="5" fill="none"/>
                    <rect x="700" y="255" width="185" height="60" rx="10" fill="#2E1065" stroke="#A855F7" stroke-width="3"/>
                    <text x="792" y="290" fill="#FFF" font-family="Orbitron" font-size="15" font-weight="bold" text-anchor="middle">R[1] <= ${{valR1}} (${{valR1.toString(2).padStart(4,'0')}})</text>
                </svg>`;
            }} else if (unitId === "REG_R0" || unitId === "REG_R1") {{
                const isR0 = (unitId === "REG_R0");
                const regVal = isR0 ? valR0 : valR1;
                const regName = isR0 ? "R[0]" : "R[1]";
                const regColor = isR0 ? "#00F0FF" : "#A855F7";
                titleEl.innerText = `🔬 GATE-LEVEL WORLD: 4-BIT SYNCHRONOUS D-FLIP-FLOP REGISTER BANK ${{regName}}`;
                subEl.innerText = `4 Parallel Positive-Edge Triggered Master-Slave D-Flip-Flops Storing ${{regName}} = ${{regVal}} (4'b${{regVal.toString(2).padStart(4,'0')}})`;
                eqEl.innerHTML = `<b>RTL Behavior:</b> always @(posedge clk) if (CE && !CSB && !M_C && !WEB && OEB && flag==${{isR0?0:1}}) ${{regName}}[3:0] &lt;= I[3:0];`;

                let dffCards = "";
                for (let b = 3; b >= 0; b--) {{
                    const bitV = (regVal >> b) & 1;
                    const xPos = 60 + (3 - b) * 215;
                    dffCards += `
                        <rect x="${{xPos}}" y="85" width="175" height="220" rx="12" fill="#0F172A" stroke="${{bitV ? regColor : '#475569'}}" stroke-width="3"/>
                        <text x="${{xPos+87}}" y="120" fill="${{regColor}}" font-family="Orbitron" font-size="16" font-weight="bold" text-anchor="middle">D-FF [Bit ${{b}}]</text>
                        <text x="${{xPos+30}}" y="165" fill="#94A3B8" font-family="JetBrains Mono" font-size="14">D[${{b}}]</text>
                        <text x="${{xPos+135}}" y="165" fill="#FFF" font-family="JetBrains Mono" font-size="16" font-weight="bold">Q=${{bitV}}</text>
                        <polygon points="${{xPos}},255 ${{xPos+22}},265 ${{xPos}},275" fill="none" stroke="#F59E0B" stroke-width="2"/>
                        <text x="${{xPos+32}}" y="270" fill="#F59E0B" font-family="JetBrains Mono" font-size="12">posedge clk</text>
                        <rect x="${{xPos+42}}" y="195" width="90" height="38" rx="6" fill="${{bitV ? '#064E3B' : '#1E293B'}}" stroke="${{bitV ? '#10B981' : '#64748B'}}" stroke-width="2"/>
                        <text x="${{xPos+87}}" y="220" fill="#FFF" font-family="Orbitron" font-size="16" font-weight="bold" text-anchor="middle">Bit = ${{bitV}}</text>
                    `;
                }}
                box.innerHTML = `<svg viewBox="0 0 940 380" width="96%" height="96%">${{dffCards}}</svg>`;
            }} else if (unitId === "OUT_MUX") {{
                const memReadVal = memData[activeAddr];
                const aluSumVal = (valR0 + valR1) & 0xF;
                titleEl.innerText = "🔬 GATE-LEVEL WORLD: 2:1 OUTPUT MULTIPLEXER (SEL = M_C) & CARRY PORT";
                subEl.innerText = "Selects between SRAM Read Data (mem[A] when M_C=0) and 4-Bit Adder Sum (R[0]+R[1] when M_C=1)";
                eqEl.innerHTML = `<b>Mux Logic:</b> O[3:0] = (~M_C &amp; mem[${{activeAddr}}][${{memReadVal}}]) | (M_C &amp; Adder_Sum[${{aluSumVal}}]) = <b style="color:#10B981">${{valO}}</b> &nbsp;|&nbsp; Carry = <b style="color:#F59E0B">${{valCarry}}</b>`;

                box.innerHTML = `
                <svg viewBox="0 0 920 390" width="95%" height="95%">
                    <rect x="40" y="70" width="210" height="55" rx="8" fill="#0F172A" stroke="#38BDF8" stroke-width="3"/>
                    <text x="145" y="103" fill="#FFF" font-family="Orbitron" font-size="15" font-weight="bold" text-anchor="middle">SRAM mem[${{activeAddr}}] = ${{memReadVal}}</text>

                    <rect x="40" y="240" width="210" height="55" rx="8" fill="#0F172A" stroke="#EC4899" stroke-width="3"/>
                    <text x="145" y="273" fill="#FFF" font-family="Orbitron" font-size="15" font-weight="bold" text-anchor="middle">Adder Sum = ${{aluSumVal}}</text>

                    <polygon points="410,45 550,115 550,255 410,325" fill="#064E3B" stroke="#10B981" stroke-width="4"/>
                    <text x="480" y="180" fill="#FFF" font-family="Orbitron" font-size="18" font-weight="bold" text-anchor="middle">2:1 MUX</text>
                    <text x="480" y="210" fill="#6EE7B7" font-family="JetBrains Mono" font-size="14" text-anchor="middle">SEL(M_C) = ${{isMC}}</text>

                    <path d="M 250 97 L 410 115" stroke="#38BDF8" stroke-width="4" fill="none"/>
                    <path d="M 250 267 L 410 255" stroke="#EC4899" stroke-width="4" fill="none"/>

                    <path d="M 550 185 L 680 185" stroke="#10B981" stroke-width="6" fill="none"/>
                    <rect x="680" y="145" width="200" height="80" rx="12" fill="#064E3B" stroke="#34D399" stroke-width="4"/>
                    <text x="780" y="182" fill="#FFF" font-family="Orbitron" font-size="17" font-weight="bold" text-anchor="middle">O[3:0] = ${{valO}}</text>
                    <text x="780" y="208" fill="#A7F3D0" font-family="JetBrains Mono" font-size="14" text-anchor="middle">Carry = ${{valCarry}}</text>
                </svg>`;
            }}
        }};

        // Initialize Packet Position & Animation Loop
        const clock = new THREE.Clock();
        function animate() {{
            requestAnimationFrame(animate);
            const dt = clock.getDelta();

            if (isPlayingCycle) {{
                cycleProgress += dt * 0.42;
                if (cycleProgress >= 1.0) {{
                    cycleProgress = 1.0;
                    isPlayingCycle = false;
                }}
                updatePacketPositions(cycleProgress);
            }}

            controls.update();
            renderer.render(scene, camera);
        }}
        updatePacketPositions(0.0);
        animate();

        window.addEventListener('resize', () => {{
            camera.aspect = container.clientWidth / container.clientHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(container.clientWidth, container.clientHeight);
        }});
    </script>
</body>
</html>
"""

components.html(three_js_multiworld_html, height=665)

# ============================================================================
# BIT-BY-BIT FULL ADDER GATE LOGIC TABLE & TABS
# ============================================================================
tab_gates, tab_mem, tab_rtl, tab_tb = st.tabs([
    "🔬 Gate-Level 4-Bit Ripple Adder & Mux Breakdown",
    "📊 Live SRAM Array & Cycle Execution History",
    "📂 Synthesizable IMC Verilog (`sram_16x4_IMC.v`)",
    "🧪 Self-Checking Testbench (`tb_sram_16x4_IMC_updated.v`)"
])

with tab_gates:
    st.markdown("##### 🔬 Real-Time Bit-Slice Full Adder Gate Evaluation (`FA0` to `FA3`)")
    st.caption("Each Full Adder stage computes `Sum[i] = R0[i] ^ R1[i] ^ Cin[i]` (XOR Gate) and `Cout[i] = (R0[i] & R1[i]) | (Cin[i] & (R0[i] ^ R1[i]))` (AND/OR Carry Gate).")

    fa_cols = st.columns(4)
    for i in range(4):
        s = fa_stages[i]
        border_c = "#10B981" if s["sum"] == 1 else "#38BDF8"
        fa_cols[i].markdown(f"""
        <div class="glass-panel" style="border-top: 3px solid {border_c};">
            <div style="font-family:'Orbitron'; font-size:0.95rem; font-weight:700; color:#EC4899; margin-bottom:6px;">
                Bit Slice FA{i} (Bit {i})
            </div>
            <div style="font-family:'JetBrains Mono'; font-size:0.82rem; color:#E2E8F0; line-height:1.65;">
                • <b>Inputs:</b> R0[{i}]=<code>{s['a']}</code>, R1[{i}]=<code>{s['b']}</code>, Cin=<code>{s['cin']}</code><br/>
                • <b>XOR1 Gate:</b> R0[{i}] ⊕ R1[{i}] = <code>{s['axorb']}</code><br/>
                • <b style="color:#10B981;">XOR2 Sum (O[{i}]):</b> {s['axorb']} ⊕ {s['cin']} = <b>{s['sum']}</b><br/>
                • <b style="color:#F59E0B;">OR1 Carry (C{i+1}):</b> <b>{s['cout']}</b>
            </div>
        </div>
        """, unsafe_allow_html=True)

with tab_mem:
    col_map, col_trace = st.columns([1.15, 1.85])
    with col_map:
        st.markdown("##### 💾 16x4 SRAM Bitcell Array Contents")
        for idx in range(0, 16, 4):
            cols = st.columns(4)
            for j in range(4):
                a = idx + j
                val = st.session_state.mem[a]
                border_col = "#10B981" if a == st.session_state.active_addr else "rgba(255,255,255,0.12)"
                cols[j].markdown(
                    f"""<div style="background:rgba(15,23,42,0.9); border:2px solid {border_col}; border-radius:10px; padding:8px; text-align:center; margin-bottom:8px;">
                        <div style="font-size:0.7rem; color:#94A3B8;">mem[{a}] (0x{a:X})</div>
                        <div style="font-family:'JetBrains Mono'; font-size:1.05rem; font-weight:700; color:#00F0FF;">{val} ({val:04b})</div>
                    </div>""",
                    unsafe_allow_html=True
                )

    with col_trace:
        st.markdown("##### ⏱️ Synchronous `@posedge clk` Execution History")
        st.dataframe(st.session_state.history[::-1], use_container_width=True, height=340)

with tab_rtl:
    rtl_code = generate_imc_verilog(param_depth, param_width)
    st.code(rtl_code, language="verilog")
    st.download_button("💾 Download sram_16x4_IMC.v", rtl_code, "sram_16x4_IMC.v", "text/plain")

with tab_tb:
    tb_code = generate_imc_testbench(param_depth, param_width)
    st.code(tb_code, language="verilog")
    st.download_button("💾 Download tb_sram_16x4_IMC_updated.v", tb_code, "tb_sram_16x4_IMC_updated.v", "text/plain")