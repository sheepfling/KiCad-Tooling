# Unanchored same-voltage connector power-input fixtures

These synthetic schematics exercise
`connector.footprint_same_voltage_power_input_unanchored`. Distinct connector
symbols share the same value, footprint, complete two-pin inventory, and native
pin metadata. Pin 1 is a `power_in` contact with `BIAS_IN` function. Pin 2 is
split across `PORT_A` and `PORT_B`, so the connectors have no common-net anchor.

The fault labels pin 1 as `+3V3` and `3.3V`; both parse to the same supported
nominal voltage while remaining separate net assignments. Pin 2 is split
between `PORT_A` and `PORT_B`, so there is no shared-net anchor. The control
joins the pin 1 contacts to `+3V3` and uses one shared `PORT_A` pin-2 anchor.
Separate sources and intentional isolation remain valid, and this review
heuristic does not require joining the fault nets.

SHA-256 source digests:

- `fault.kicad_sch`: `b1f0fbf69b4bf417ac004147b5eef2649446d8c563bac5716e3aab5a8ea3e78e`
- `control.kicad_sch`: `93b2988e463477a23a5041d1d38f4cf07178245dfc757c086f653ae93bab4f56`
