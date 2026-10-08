# Cohort label-alias native comparison

These Tooling-owned synthetic fixtures compare the documented kicad-happy
`LB-001` predicate with native KiCad ERC. They contain no board or project
source.

The fault attaches distinct global labels `ALIAS_A` and `ALIAS_B` to one wire
connected to `R1.1`. The control attaches the same global label twice. Both
schematics retain the same disconnected `R1.2` and intentionally unconfigured
synthetic symbol library, so the background `pin_not_connected`,
`lib_symbol_issues`, and two `isolated_pin_label` diagnostics appear in both.

## Native result

The two fixtures were exported twice with each exact official linux/amd64
image:

- KiCad 10.0.0:

  ```text
  ghcr.io/kicad/kicad:10.0.0@sha256:9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3
  ```

- KiCad 10.0.5:

  ```text
  ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c
  ```

For each version and repeat, KiCad assigned `R1.1` to `ALIAS_A` in the fault
and `CONTROL_NET` in the control. ERC added exactly one diagnostic category
for the fault: warning `multiple_net_names`, identifying both labels and
stating that `ALIAS_A` will be used in the netlist. The duplicate-name control
had no `multiple_net_names` diagnostic. The normalized pin/net assignments
and ERC signatures matched across repeated exports and both versions; raw XML
bytes differ because their export timestamps differ.

This confirms that native ERC already detects this tested electrical label
conflict and localizes both source labels. It does not measure whether the
cohort's additional maintainability explanation saves review time. The
candidate analyzer was not installed or run here. A distinct intentional alias,
power-label exclusions, and same-name labels on separate sheets remain outside
this partial comparison.

## Source hashes

- Fault: `a233fe244a23c928955e7f8615260241e05e7b83e376070e679bfab0985cf6d2`
- Control: `cbf28be6a2e80e72da387a8f1e527f4f9e95edfe4c764e7c68ad3a94fc62d953`
- Base: `tests/fixtures/design_lint/connected-pin-control.kicad_sch`

Generated native receipts and exports stay under ignored
`build/ci/lb001-native-trial/`. The tracked fixture directory contains only the
synthetic inputs and this comparison record.
