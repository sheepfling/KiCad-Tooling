# Synthetic USB-C VBUS capacitance review fixture

Source SHA-256 for `connector-pair.kicad_sch`:
`5368f8bcff7fd3500e80708bab0b5b7283c5d4e9b95a9356082c1addc7756ea6`.

`connector-pair.kicad_sch` is a tooling-owned two-port fixture. J1 has native
CC1, CC2, VBUS, and GND roles but no capacitor across its VBUS and return
nets. J2 has the same native role pattern and a fitted two-pin `Device:C`
between its own VBUS and GND nets. This isolates a missing-capacitor review
candidate from a valid presence control in one deterministic native export.

The fixture does not define a USB-C capacitance requirement or claim that J1
is defective. It tests only that a likely port with no recognized capacitor
gets a configurable review prompt, while a fitted symbol with the exact two
native pin assignments clears that prompt. It contains no product, customer,
or private project data.
