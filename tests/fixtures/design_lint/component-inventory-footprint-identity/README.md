# PCB footprint identity fixtures

These tooling-owned schematic and PCB fixtures test whether the assigned
schematic footprint ID matches the exact ID in native PCB placement evidence.
They do not model a real package or assert pad-geometry equivalence.

- `control.kicad_sch` assigns `Synthetic:Probe_Module` to U1, matching the
  footprint ID in `control.kicad_pcb`. Its native value field also matches the
  schematic's `Synthetic identity probe` value.
- `fault.kicad_sch` assigns `Synthetic:Wrong_Footprint` to U1 while leaving the
  board unchanged. The expected result is one review candidate for U1.
- The board also contains U2 and U3, which are intentionally board-only controls
  outside this comparison.
- `population-schematic-dnp.kicad_sch` marks U1 DNP; `population-board-dnp.kicad_pcb`
  marks the placed U1 footprint DNP. The native acceptance lane compares both
  mismatch directions and the matching fitted and DNP controls. It checks only
  the default/base DNP flags.
- The named-variant native lane uses fixed tooling-owned synthetic PCB variant
  sources, pairs `--variant` schematic netlists with same-name PCB position
  exports, confirms the board contains the declared variant, and compares both
  DNP mismatch directions plus a fitted control. A board without that variant
  must block before default-variant comparison. Temporary projects and exports
  live only in ignored test scratch/build output. The synthetic inputs and
  native fixture-generation recipe are described in the [variant fixture
  record](../named-variant-population/README.md).

The native acceptance lane checks these source files and their expected SHA-256
digests on digest-pinned KiCad 10.0.0 and 10.0.5. It repeats the base schematic
exports and board snapshots to verify stable evidence. All content is synthetic
and included solely for Tooling regression tests.

- `value-fault.kicad_pcb` changes only U1's board value to `Stale synthetic
  board value`. Compared with the control schematic, it must produce one
  fitted value-field review; the control PCB must stay quiet.

Pinned source hashes:

- `fault.kicad_sch`: `3a66be0b39af5f2a065de3b10e9476a53838042bc4e87f8618e711b31ad59e2b`
- `control.kicad_sch`: `3acf612f93c0f2f48c6b469928ab9366fc2374644966b9bf07087c8a4cd808f8`
- `control.kicad_pcb`: `23a19d40848ad3b6136f163ccf3ab64c53fef9185d696cde96323b66415d8913`
- `value-fault.kicad_pcb`: `08a35eee9763c93501167098fcdf8b7484c9c539f5d0c649b58b64fb99feb1c0`
- `population-schematic-dnp.kicad_sch`
  SHA-256: `7f185318b3941f10901f8e27bc29b13030ca771e4ff7d3418c09e18a6428c269`
- `population-board-dnp.kicad_pcb`
  SHA-256: `cabf0b68f4ceadffa21ec590c7a2a67c5a54c9930a1e57bae688a813417b8ca4`
