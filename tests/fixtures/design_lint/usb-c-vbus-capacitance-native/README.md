# Synthetic USB-C VBUS capacitance fixtures

These tooling-owned schematics verify that the USB-C port capacitance check
reads capacitor identity, nominal value, footprint, pin inventory, and native
pin-to-net assignments from a KiCad-exported netlist. They are synthetic and
contain no product or customer board data.

- `control.kicad_sch`: 4.7 uF; PASS for the fixture-authored 4500–5000 nF window.
- `fault.kicad_sch`: 2.2 uF; FAIL below the same fixture-authored window.

Both sources map C1.1 to `VBUS_PORT` and C1.2 to `GND`, with the synthetic
`Device:C` symbol and `Synthetic:C_0603` footprint. The lane repeats native
netlist export and compares normalized typed-netlist digests. It runs in the
digest-pinned KiCad 10.0.0 and 10.0.5 acceptance jobs. Passing demonstrates
only that the declared schematic facts and project-authored nominal limits
match; it does not establish USB compliance, component tolerance/derating,
dynamic behavior, PCB placement, copper continuity, or product approval.

Source SHA-256 values are recorded by the native fixture test and acceptance
receipt. Do not replace these sources with project schematics.
