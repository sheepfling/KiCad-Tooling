# JTAG TDO output-sharing fixtures

These tooling-authored schematic fixtures exercise a configurable review heuristic.
They contain only synthetic IC symbols and are marked not for manufacture.

| Case                | Expected result                                                                | Source SHA-256                                                     |
| ------------------- | ------------------------------------------------------------------------------ | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | Fitted U1.4 and U2.4 JTAG TDO pins share `JTAG_TDO_SHARED`; one REVIEW prompt. | `27780a89a033d3b5c4ca4a1179a14245edc400e96e9776251867926f1b464fc1` |
| `control.kicad_sch` | Each fitted IC's JTAG TDO pin has its own net; no prompt.                      | `5f83444498c05f61cd7e6466203a7df14814eaa2846e05474361f9625fb5e4e5` |

The native lane checks the complete pin-function inventory and all net assignments,
then repeats KiCad 10.0.0 and 10.0.5 schematic netlist and ERC exports from digest-pinned
Docker images. Both fixtures must have no ERC errors and repeat-identical normalized
netlists. The heuristic asks for review; it does not establish whether a mux or TAP
selection makes shared TDO intentional, and it does not inspect PCB copper.
