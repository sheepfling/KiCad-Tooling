# Distinct mapped signals sharing one net

`shared-net.kicad_sch` is a tooling-owned generic two-pin connector whose
native pins 1 and 2 share the `SHARED_SIGNAL_NET` net. Both pins use generic passive
native functions so the regression exercises only the source-matched interface
map and the exported native net assignment.

The fault maps the contacts to two distinct signal names. The control maps
both contacts to the same signal name. Both evaluations use the same exact
native netlist; this checks whether a map change alone creates the review
candidate. The intentional same-signal tie is a valid control, not a claim
that different signal labels must always be electrically isolated.

Source SHA-256:

- `shared-net.kicad_sch`: `3716e8019bc5d5572d8a4f2e9112e01aecd69a8c035354c37e92aa481a0595ba`

The exact-version lane exports the source twice with digest-pinned KiCad
10.0.0 and 10.0.5 images and checks that normalized netlist evidence repeats.
The fixture contains no project or customer source.
