# Explicit thermal-pad scope fixture

This tooling-owned schematic contains synthetic U1 and DNP U2 instances. The
embedded symbol exports pin 9 as `EP` and pin 8 as `THERMAL_ALERT`; U1 has an
assigned synthetic footprint and U2 is marked DNP. There are no board files,
thermal requirements, or proprietary source files in this fixture.

The fixture checks native pin-function export and supports the advisory prompt
that asks a reviewer whether an exact exposed-pad via requirement applies. It
does not assert that either pin needs thermal vias or that any via geometry is
adequate.
