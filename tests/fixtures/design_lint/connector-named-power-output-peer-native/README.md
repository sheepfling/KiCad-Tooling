# Cross-symbol named power-output peer fixtures

These tooling-owned schematic sources test
`connector.peer_power_output_open_assignment`. Two distinct synthetic
connector symbols share a native `PART_ID`, value, footprint, full two-pin
inventory, and matching `BIAS_OUT` / `power_out` metadata. `fault.kicad_sch`
assigns J1.1 and leaves J2.1 open; `control.kicad_sch` assigns both target
contacts to one synthetic net. `all-open-fault.kicad_sch` leaves both target
contacts unassigned to exercise `connector.peer_power_output_named_all_open`.

The prompt is a review question. Matching schematic identity and pin metadata
do not prove that the contacts should share a net. All-open groups are outside
this mixed-assignment rule. These sources are synthetic and are not based on a
product board or project requirement.

The digest-pinned native lane exports each source repeatedly with KiCad 10.0.0
and 10.0.5, then checks the normalized netlist and focused lint result.

SHA-256 source digests:

- `control.kicad_sch`: `e5621a2b8f8660db341ffe5a4088c1b802c28d1b624e522434516f0235de7d71`
- `fault.kicad_sch`: `ef721f666d540f3ce99598fcf9e52a494729e6cdbd56b57798fd260c10bc40be`
- `all-open-fault.kicad_sch`: `e16ae20d4f198fdf648049f7571bdf4db0842518bd54f8c7536d89655e93b12b`

## Hosted acceptance

The rule-scoped hosted run 38322241068 used
`KICAD_RUN_NATIVE_CONNECTOR_FIXTURES=1`. The native lane ran both fault
and control on the pinned KiCad 10.0.0 and 10.0.5 images, verified repeatable
normalized netlists, reported this rule for the fault, and kept the control
free of this finding. The full scoped acceptance gate also passed its separate
project wheel playtest and platform preview jobs.

| KiCad version | Digest-pinned image                                                                                  |
| ------------- | ---------------------------------------------------------------------------------------------------- |
| 10.0.0        | `ghcr.io/kicad/kicad:10.0.0@sha256:9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3` |
| 10.0.5        | `ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c` |
