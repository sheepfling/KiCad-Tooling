# Repeated mapped signal contacts on separate nets

`split-signal.kicad_sch` is a tooling-owned, two-contact generic connector.
Its two passive native contacts are assigned to `CONTACT_NET_A` and
`CONTACT_NET_B`. A source-matched map that names both contacts `CONTROL`
produces a review candidate. The valid control uses the same native export but
maps the contacts to distinct signal names.

The case tests map-to-netlist consistency only. Repeated interface names do not
prove that direct commoning is required; series elements, intentional splits,
or a map correction can explain separate nets. The test contains no project,
customer, or cohort source.

Source SHA-256:

- `split-signal.kicad_sch`: `fa11e55fe8cc046fd093eb3cb6fdd1c9a6cfc2c75a838320ea8ff720fa3c512e`

The exact-version lane exports this source twice with digest-pinned KiCad
10.0.0 and 10.0.5 images and compares the normalized native netlist evidence.
