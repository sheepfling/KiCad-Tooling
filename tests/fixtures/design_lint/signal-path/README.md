# Synthetic PCB signal-path DRC fixtures

`create.py` builds small boards from a standard KiCad pin-header footprint. The
control board has a direct clock route and a detoured data route within its
length and bundle-skew limits and keeps the clock route inside the authored
board-edge margin. The fault board moves the synthetic board edge close to the
clock pads and uses tighter length and skew limits, so native DRC must report
`length_out_of_range`, `skew_out_of_range`, and `copper_edge_clearance`. A
third board uses the fault geometry and limits with `(severity ignore)` on
each matching custom rule; it must not report any target violation.

The boards are generated inside the digest-pinned KiCad 10.0.0 and 10.0.5
images. The native lane runs each case twice, checks the exact tool version,
and requires identical violation types across runs. Its retained acceptance
event records hashes for all three generated boards, their rule files, all six
raw DRC reports, and the command receipt, along with the reported violation
types and exit codes. This fixture validates both that native DRC applies
active `fromTo` length, skew, and edge-clearance constraints and that ignored
custom rules do not produce findings; it does not select appropriate
electrical limits for a real interface.

When `KICAD_RUN_NATIVE_PCB_FIXTURES=1`, pytest retains the synthetic boards,
rule files, six raw reports, exit files, normalized command receipt, and
hash-bearing event journal under the ignored
`build/ci/native-fixtures/pcb-signal-path/<project>/` tree. The package
workflow uploads `build/ci/`. Host-specific mount paths in the retained
command are replaced with `<fixture-root>` and `<output-root>` so the receipt
does not embed a developer or runner checkout path.

All board geometry and rule values are synthetic. No project design files,
netlists, pinouts, or project-authored requirements are included.
