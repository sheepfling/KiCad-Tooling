# Mapped component supply-voltage range fixture

These tooling-owned synthetic schematics exercise the opt-in
`power.component_supply_voltage_outside_range`,
`power.component_supply_range_pin_coverage`, and
`power.component_supply_range_map_coverage` review rules. Both contain the
same synthetic `U1` with two native `power_in` pins (`VIN` and `VDD`) and exact
symbol, footprint, `PART_ID`, and pin inventory. They also contain a fitted,
unmapped `U3` with the same two pin functions and a distinct `PART_ID`. Both ICs
share the source rail: the fault labels it `24V`, and the valid control labels
it `5V`. Their only source difference is the voltage label.

The native verifier applies a synthetic range map for `U1.1` with an inclusive
range of 5 V to 12 V. The 24 V net label creates a review finding and the 5 V
label is quiet. For pin-coverage review, a map that lists only `U1.1` reports
the uncovered native `power_in` pin `U1.2`; adding an exact `U1.2` range entry
clears that pin-coverage finding. For component-map coverage, the `U1`-only map
prompts on the unmapped `U3.1`/`U3.2`; exact entries for U3 clear the prompt.
The synthetic ranges are test boundaries, not real component ratings or
datasheet claims.

| Case                | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | `3966a0ffd04d4e75dc30c751497ba34c00dcdafbf12982903d42b96470a3c152` |
| `control.kicad_sch` | `4a9709636901c51b362e688f22d4ae3bd69faa2b2b0a747e6e2d09ae31a73545` |

The acceptance test exports both schematics twice using the selected external
template's exact KiCad project profiles: KiCad 10.0.0 and 10.0.5. The images
are pinned by digest in
`tests/test_component_rating_native_fixture_lane.py`. The lane requires
repeatable normalized netlists and ERC signatures and rejects ERC errors.
These checks establish deterministic parsing and rule behavior for the
synthetic source. They do not establish a real component's operating range,
measured voltage, board copper continuity, or electrical approval.
