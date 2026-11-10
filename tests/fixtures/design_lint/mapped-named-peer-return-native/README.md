# Mapped named peer-return split fixture

This tooling-owned schematic pair contains two unrelated one-pin synthetic
connector symbols. Their native pin functions are `CONTACT_A` and `CONTACT_B`,
so the generic repeated-return comparison cannot infer that they share a role.
The synthetic connector map explicitly classifies both pins as returns in one
`signal-return` voltage domain and one reviewed `external-returns` comparison
group.

The fault source assigns the contacts to separate named nets. The control uses
one shared label. The fixtures test schematic netlist evidence only; they do
not prove that separate returns are electrically wrong, that a common return is
required, or that PCB copper connects the contacts.

The native test exports each source twice with digest-pinned KiCad 10.0.0 and
10.0.5 Docker images. The fixture directory is mounted read-only and native
outputs are written to a separate temporary directory. These sources contain
no product-board, customer, or cohort project data.
