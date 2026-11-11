# Mapped component supply-voltage range fixture

These tooling-owned synthetic schematics exercise the opt-in
`power.component_supply_voltage_outside_range` and
`power.component_supply_range_pin_coverage` review rules. Both contain the
same synthetic `U1` with two native `power_in` pins (`VIN` and `VDD`) and exact
symbol, footprint, `PART_ID`, and pin inventory. Both pins share the source
rail. The fault labels that rail `24V`; the valid control labels it `5V`. Their
only source difference is the voltage label.

The native verifier applies an explicitly authored synthetic range map for
`U1.1` with an inclusive range of 5 V to 12 V. The 24 V net label creates a
review finding and the 5 V label is quiet. For pin-coverage review, a map that
lists only `U1.1` reports the uncovered native `power_in` pin `U1.2`; adding an
exact `U1.2` range entry clears that coverage finding on the same native source.
The synthetic ranges are test boundaries, not real component ratings or
datasheet claims.

| Case                | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | `6bf5cae9f306553442dfbac9a427f584068ae1e8df4ee6f797907c3bce289ccc` |
| `control.kicad_sch` | `09d4978aba50c6378dcd46cd870897ff30640cb9428bd4f02ff2cc115e826064` |

The acceptance test exports both schematics twice using the selected external
template's exact KiCad project profiles: KiCad 10.0.0 and 10.0.5. The images
are pinned by digest in
`tests/test_component_rating_native_fixture_lane.py`. The lane requires
repeatable normalized netlists and ERC signatures and rejects ERC errors.
These checks establish deterministic parsing and rule behavior for the
synthetic source. They do not establish a real component's operating range,
measured voltage, board copper continuity, or electrical approval.
