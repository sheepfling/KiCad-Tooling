# Synthetic unconnected generic power-input connector contacts

This tooling-owned fixture has two identical connector symbols with pin 1
defined as KiCad electrical type `power_in` and a generic numeric pin function.
The fault leaves both pin 1 contacts unassigned while the return pins remain
connected. The control assigns both power-input contacts to `+5V`.

The fault demonstrates a common-mode omission: neither named-pin checks nor a
peer outlier can determine that an open generic contact is suspicious when all
peers are open. The new `connector.unconnected_power_input` rule uses only the
native electrical type and missing net assignment to request review. It does
not decide whether the pin is positive supply, a reference, or intentionally
unused, and it does not require the peer contacts to share a net.

The exact source hashes and native exports are verified in the digest-pinned
KiCad 10.0.0 and 10.0.5 package acceptance lane. All content is synthetic.

| Source              | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | `2e16c602d6ba0068360b3f8b493351f6d7e4d7adbe94946d17db883587f0528f` |
| `control.kicad_sch` | `b05c1a3994a4f26f07e18bdfe28c8caaf4a298cbb66b6d1814b20c9a7dce2c13` |
