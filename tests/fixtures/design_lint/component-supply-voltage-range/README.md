# Mapped component supply-voltage range fixture

These tooling-owned synthetic schematics exercise the opt-in
`power.component_supply_voltage_outside_range` review rule. Both contain the
same synthetic `U1` supply input and exact symbol, footprint, `PART_ID`, pin
inventory, and pin function. The fault connects `U1.1` to `24V`; the valid
control connects it to `5V`. Their only source difference is that voltage
label.

The native verifier applies an explicitly authored synthetic map for pin
`U1.1` with an inclusive range of 5 V to 12 V. The 24 V net label creates a
review finding and the 5 V label is quiet. The synthetic map is a test
boundary, not a real component rating or datasheet claim.

| Case                | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | `2114ccc1f771667a0ee7c9ed2ae8a8d865fc05f597fb792b9c591d647441b94e` |
| `control.kicad_sch` | `c8da09bc16116df7f3083d3b99b4cbdc1c389e08f5638b701ed3b8b5e424e0dd` |

The acceptance test exports both schematics twice using the selected external
template's exact KiCad project profiles: KiCad 10.0.0 and 10.0.5. The images
are pinned by digest in
`tests/test_component_rating_native_fixture_lane.py`. The lane requires
repeatable normalized netlists and ERC signatures and rejects ERC errors.
These checks establish deterministic parsing and rule behavior for the
synthetic source. They do not establish a real component's operating range,
measured voltage, board copper continuity, or electrical approval.
