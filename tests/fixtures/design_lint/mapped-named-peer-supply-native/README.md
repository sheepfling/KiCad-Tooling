# Mapped named peer-supply split fixture

This tooling-owned schematic pair contains two unrelated one-pin synthetic
connector symbols. Their native pin functions are `CONTACT_A` and `CONTACT_B`,
so the generic repeated-pin and recognized power-category checks do not infer
that they share a supply role. The synthetic connector map explicitly classifies
both pins as supplies in one `board-input` voltage domain and one reviewed
`external-power` comparison group.

The fault source assigns the contacts to `NODE_ALPHA` and `NODE_BETA`. The
control assigns both contacts to `COMMON_NODE`. These fixtures test schematic
netlist evidence only; they do not prove that separate supplies are wrong, that
a common supply is required, or that PCB copper connects the contacts.

The native test exports each source twice with digest-pinned KiCad 10.0.0 and
10.0.5 Docker images. The fixture directory is mounted read-only and native
outputs are written to a separate temporary directory. These sources contain
no product-board, customer, or cohort project data.

SHA-256:

- `control.kicad_sch`: `0feff0855ebb0338633c8c7ff71c19cd26724c1338005a1c48e95753cdf37d7f`
- `fault.kicad_sch`: `b066f0a88ea6b32205c96b99b23a1ce841a1772c8ea7294cfa9b4415e94d219a`
