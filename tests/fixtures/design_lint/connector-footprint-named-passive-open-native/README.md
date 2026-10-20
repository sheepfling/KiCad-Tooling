# Named passive connector contact open on a peer

This tooling-owned KiCad 10 fixture pair tests
`connector.footprint_named_passive_open_outlier`. The fault assigns the named
`AUX_DETECT` passive contact on one matching connector and leaves it open on the
other; pin 2 provides a separate common-net anchor. The control assigns the
contact on both peers.

The warning is a review clue only. Similar metadata and a common anchor do not
prove that the passive contact has the same electrical role or must connect.
No project or customer source is represented here.

SHA-256:

- `fault.kicad_sch`: `9d05ca2c2f871e763b311ec299cee1b325a0daaf5370f15eff80228edebd62b7`
- `control.kicad_sch`: `8e3be4a0aec8a24ac85021d1f647c51052e35966d4bfe434adf7b53b7491b821`
