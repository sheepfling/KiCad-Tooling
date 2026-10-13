# Cross-symbol named power-input peer fixtures

These tooling-owned schematic sources test
`connector.peer_power_input_open_assignment` and
`connector.peer_power_input_named_all_open`, and
`connector.peer_power_input_named_assignment_divergence`. Two distinct
synthetic connector symbols share a native `PART_ID`, value, footprint, full
two-pin inventory, and matching `BIAS_IN` / `power_in` metadata.
`fault.kicad_sch` assigns J1.1 and leaves J2.1 open;
`all-open-fault.kicad_sch` leaves both target contacts open;
`control.kicad_sch` assigns both target contacts to one synthetic net;
`divergent-fault.kicad_sch` assigns J1.1 to `+3V3` and J2.1 to `+5V`.

The prompt is a review question. Matching schematic identity and pin metadata
do not prove that the contacts should share a net. The sources are synthetic
and are not based on a product board or project requirement.

The digest-pinned native lane exports each source repeatedly with KiCad 10.0.0
and 10.0.5, then checks the normalized netlist and focused lint result.
Tagged acceptance `v0.5.0rc209` passed in GitHub run `38326684651` with the
native connector fixture lane enabled. The divergent fault reports the new
review rule, while the common-net, mixed, and all-open cases preserve their
expected outcomes on both exact KiCad versions. The focused lint gate,
installed-wheel check against a separate project checkout, playtest, and
Ubuntu, Windows, and macOS preview jobs passed.

SHA-256 source digests:

- `control.kicad_sch`: `401fda583c25519540d427b1e24e320e5843c3aab5e99407378497e7dc475717`
- `divergent-fault.kicad_sch`: `fcbe8aba85c991d73f2daa19443749a440b7eef8cb5532ec3e2d09352b6d998c`
- `fault.kicad_sch`: `48eae0285f76c61668dbe58e33ee00bf9480a3064f5a45c2e122b12d2f91ec7c`
- `all-open-fault.kicad_sch`: `b17443d0e3db891ca9946f032561dabe57d29e17bd9396668b0398a70ac2fdeb`
