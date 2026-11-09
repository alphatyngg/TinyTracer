import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge


# helper function to inject bytes into the parser input (rx_bytes)
async def send_byte(dut, value):
    """inject 1 byte to the parser input (rx_bytes)"""

    # rx_fire = rx_bytes.valid && rx_bytes.ready
    # we wait for ready, raise valid with data for 1 clk edge, then lower valid
    
    while True:
        await RisingEdge(dut.clk)                   # wait until parser is ready to accept a byte

        if int(dut.dut_io.rx_bytes.ready.value) == 1:
            break


    # present the byte with valid high
    # fires on next clk edge if both valid and ready are high
    dut.dut_io.rx_bytes.data.value = value
    dut.dut_io.rx_bytes.valid.value = 1
    await RisingEdge(dut.clk)                       # hold valid for 1 clk edge

    # drop valid, clear data, let the parser settle before next byte
    dut.dut_io.rx_bytes.data.value = 0
    dut.dut_io.rx_bytes.valid.value = 0
    await ClockCycles(dut.clk, 1)                   # wait a few cycles for things to settle


async def send_bytes(dut, values):
    """inject a list of bytes to the parser input (rx_bytes)"""

    for value in values:
        await send_byte(dut, value)


@cocotb.test()

async def test_render(dut):
    """render test, sends render command to parser, waits for render pulse, and checks w / h values"""
    dut._log.info("start render test")

    # setup (clock + reset)
    clock = Clock(dut.clk, 40, units="ns")          # starts clock (25MHz)
    cocotb.start_soon(clock.start())

    dut.rst_n.value = 0
    dut.uart_rx.value = 1                           # we're not even using this, so keep idle at 1
    dut.clkdiv_ctl.value = 0                        # clkdiv not even used, so keep floating at 0
    dut.clkdiv_data.value = 0
    dut.dut_io.rx_bytes.valid.value = 0
    dut.dut_io.rx_bytes.data.value = 0
    await ClockCycles(dut.clk, 5)                   # hold reset low for 5 cycles
    dut.rst_n.value = 1                             # release reset
    await ClockCycles(dut.clk, 2)                   # wait 2 cycles for things to settle, then parser live

    dim = 0x123                                     # artbitrary test value
    dim_low = dim & 0xFF                            # grabs lower 8 bits -> 0x23
    dim_high = (dim >> 8) & 0xFF                    # shifts down, masks lower 8 bits -> 0x01


    # catches the one cycle render pulse (bgd monitoring)
    seen = {"pulsed": False, "w": None, "h": None}

    async def monitor_render():
        while True:                                 # infinite loop that checks if render_strobe is high on every clk edge 
            await RisingEdge(dut.clk)

            if int(dut.render_strobe.value) == 1:
                seen["pulsed"] = True
                seen["w"] = int(dut.render_img_w.value)                     # captures img_w value at moment of pulse
                seen["h"] = int(dut.render_img_h.value)                     # captures img_h value at moment of pulse

    cocotb.start_soon(monitor_render())

    await send_bytes(dut, [0x00, dim_low, dim_high, dim_low, dim_high])     # inject render msg, 4 payload bytes (RENDER_START, width low / high, height low / high)
    await ClockCycles(dut.clk, 5)                                           # wait a few cycles for things to settle

    # the check
    assert seen["pulsed"] == True, "render pulse not seen after render message"
    assert seen["w"] == dim, f"render width mismatch: expected {dim:#05x}, got {seen['w']:#05x}"    # #05x for formatting in output msg only, purely cosmetic
    assert seen["h"] == dim, f"render height mismatch: expected {dim:#05x}, got {seen['h']:#05x}"

    dut._log.info(f"render test passed: width=height={dim:#05x}")


# async def test(dut):
#     """confirm cocotb can reach the signals we gonna use"""

#     clock = Clock(dut.clk, 40, units="ns")          # starts clock (25MHz)
#     cocotb.start_soon(clock.start())

#     # the reset sequence, active low (0 -> reset active)
#     dut.rst_n.value = 0

#     dut.uart_rx.value = 1                           # we're not even using this, so keep idle at 1
#     dut.clkdiv_ctl.value = 0                        # clkdiv not even used, so keep floating at 0
#     dut.clkdiv_data.value = 0

#     await ClockCycles(dut.clk, 5)                   # hold reset for 5 cycles
#     dut.rst_n.value = 1                             # release reset
#     await ClockCycles(dut.clk, 5)                   # wait a few cycles for things to settle


#     # the actual loop that checks if the signals we want are reachable
#     for path in [
#         "dut_io.rx_bytes.valid",
#         "dut_io.rx_bytes.ready",
#         "dut_io.rx_bytes.data",
#         "dut_io.rx_state",
#         "render_strobe",
#         "sram_req_valid",
#     ]:
#         obj = dut

#         try:                                        
#             for part in path.split("."):            # the hierarchy walk, splitting up the path with "."
#                 obj = getattr(obj, part)            # getattr() to get each part of the path

#             dut._log.info(f"REACHABLE: {path} = {obj.value}")

#         except Exception as e:
#             dut._log.error(f"UNREACHABLE: {path} ({type(e).__name__})")
