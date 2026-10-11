# PCB footprint identity fixtures

These tooling-owned schematic and PCB fixtures test whether the assigned
schematic footprint ID matches the exact ID in native PCB placement evidence.
They do not model a real package or assert pad-geometry equivalence.

- `control.kicad_sch` assigns `Synthetic:Probe_Module` to U1, matching the
  footprint ID in `control.kicad_pcb`.
- `fault.kicad_sch` assigns `Synthetic:Wrong_Footprint` to U1 while leaving the
  board unchanged. The expected result is one review candidate for U1.
- The board also contains U2 and U3, which are intentionally board-only controls
  outside this comparison.

The native acceptance lane checks these source files and their expected SHA-256
digests on digest-pinned KiCad 10.0.0 and 10.0.5. It repeats both schematic
exports and board snapshots to verify stable evidence. All content is synthetic
and included solely for Tooling regression tests.

Pinned source hashes:

- `fault.kicad_sch`: `3a66be0b39af5f2a065de3b10e9476a53838042bc4e87f8618e711b31ad59e2b`
- `control.kicad_sch`: `3acf612f93c0f2f48c6b469928ab9366fc2374644966b9bf07087c8a4cd808f8`
- `control.kicad_pcb`: `500ba5a3fbaa36cec9d57cdd6a74f9b65cd03517ed37f11cd960de425c1d5522`
