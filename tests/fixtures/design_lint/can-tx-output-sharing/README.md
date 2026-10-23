# Synthetic CAN TX output-sharing fixtures

These tooling-owned schematics contain two synthetic CAN controller symbols.
The fault assigns both `CAN1_TX` pins to `CAN_TX_SHARED`; the control connects
one controller TX pin to the other controller RX pin and keeps the second TX
on a separate net. Passive native pin types isolate the review predicate from
ERC driver checks and do not model real device pin directions.

The default-off rule asks whether multiple fitted CAN transmit-function pins
are intentionally sharing one schematic net. It requires complete native pin
inventories and supported electrical types, skips ambiguous or unsupported
assignments, and leaves two explicit native outputs to ERC. Different channel
indices are still grouped when their exported net is exactly the same.

The native fixture lane repeats netlist and ERC exports on digest-pinned KiCad
10.0.0 and 10.0.5 images. This is a schematic assignment check; it does not
establish controller mode, driver behavior, board copper, or off-board wiring.
No product or cohort source is included.

Source SHA-256 digests:

- `multiple-transmitters.kicad_sch`
  SHA-256: `c3a6207f2c03eb1e5ce7bd6cbc9bd544833463e92f639a09b7ad126079a3d4e6`
- `one-transmitter-control.kicad_sch`
  SHA-256: `45907af0a675dd98b7fd6bc48046be280b7ce4b9da72b84a67be9d7f384fb6d3`
