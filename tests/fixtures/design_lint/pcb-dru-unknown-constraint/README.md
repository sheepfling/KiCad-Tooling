# Unknown custom DRC constraint fixtures

These tooling-owned version-1 rule files use the shared synthetic board and
project in `pcb-drc-duplicate-net-settings/`. The fault misspells
`track_width` as `track_wdith`; the control uses the documented constraint.
No project or cohort source is used.

KiCad 10.0 documents the valid custom-rule constraint vocabulary in the
[PCB Editor reference](https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html#custom-rule-syntax).
The tooling registry is intentionally limited to KiCad 10.0.x. The native
probe is pinned to KiCad 10.0.8. It also checks the accepted
`mechanical_clearance` legacy alias against the canonical `physical_clearance`
constraint on the synthetic tracks.

## Source hashes

| Fixture                                    | SHA-256                                                            |
| :----------------------------------------- | :----------------------------------------------------------------- |
| `control-track-width.kicad_dru`            | `cd05e0d1f96eda8b29f919918217309365da9d851b237cda6326a7806798591c` |
| `control-legacy-clearance-alias.kicad_dru` | `53b2549702f89a5d1de4a9ce44e94c2f9fe96cd2001504d1d59b20c238ccfe9e` |
| `control-physical-clearance.kicad_dru`     | `f2412883248029051723f6b2e30bf2e4317879a87ff736d4014c0b1a1b674cea` |
| `fault-misspelled-track-width.kicad_dru`   | `dd58b9f8c35bf3766cecf052bd18aaf845f4685c01fb35fd4f14a451ca4b9ccd` |

The KiCad 10.0.8 probe ran each source twice against the same two-track board.
The misspelled constraint produced only the board's two `track_dangling`
warnings. The valid control reported those warnings plus two `track_width`
errors for its authored 0.5 mm minimum. This shows that this typo was silently
ignored by that exact native version and fixture; it does not establish
behavior for another version or every possible constraint typo.

The legacy `mechanical_clearance` alias and canonical `physical_clearance`
control produce matching physical-clearance violation types on these tracks.
This verifies that one legacy alias remains accepted by the pinned native
version; the registry's remaining aliases are grounded in the release parser
vocabulary and have not each received a separate native fixture.
