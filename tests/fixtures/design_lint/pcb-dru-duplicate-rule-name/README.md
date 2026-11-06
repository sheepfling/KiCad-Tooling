# Duplicate custom DRC rule-name fixtures

These tooling-owned `.kicad_dru` inputs exercise exact duplicate-name review.
The fault has three top-level rules named `SYNTHETIC_DUPLICATE_NAME`, producing
one finding with ordinals 1, 2, and 3. The control has distinct names, one
case-only variant, and comments that mention the fault name; it stays quiet.

| Source                            | SHA-256                                                            | Expected result                                       |
| --------------------------------- | ------------------------------------------------------------------ | ----------------------------------------------------- |
| `fault-duplicate-names.kicad_dru` | `ab8c380983998f61697cc105a8b3d0945994546158a96d8e085088fbb8074161` | One REVIEW for the three exact duplicate declarations |
| `control-unique-names.kicad_dru`  | `9a3bd4a9d0672fd22f107873121f0e6a134a31f35e088f4c5d4e36e6f03b7ebf` | No duplicate-name finding                             |

The native test appends Tooling's terminal sentinel to each source and runs
`kicad-cli pcb drc` twice per source in digest-pinned KiCad 10.0.0 and 10.0.5
images. Both files must reach the sentinel with identical typed identity and
match counts. This confirms the duplicate-name review adds a source-lint signal
even when the native DRC parser continues evaluating the file; it does not
establish the semantics of either authored rule.

The candidate idea is recorded by the pinned
[`kicad-druid` README](https://github.com/Cimos/kicad-druid/blob/8af046d6a1839320a360a4b6790ac11eb27a78ae/README.md),
which lists duplicate names among its source-lint checks. KiCad documents rule
names as identifiers in DRC reports in its
[PCB Editor documentation](https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html#custom-design-rules).
No cohort code, board, or project fixture is included here.
