# Mapped named peer-signal split fixtures

These tooling-owned synthetic schematics contain two unlike, one-pin connector
symbols with native functions `CONTACT_A` and `CONTACT_B`. The fault assigns
them to `NODE_ALPHA` and `NODE_BETA`; the control puts both on `COMMON_NODE`.
The test applies a separate reviewed signal map to each source. Signal name,
voltage domain, and peer group define review scope only; they do not state that
the nets must be common or establish PCB continuity.

The exact KiCad 10.0.0 and 10.0.5 Docker images export each source twice. The
fixture directory is mounted read-only and outputs go to a temporary directory.
These files are small synthetic examples, not product-board or customer data.

SHA-256:

- `control.kicad_sch`: `62c73dd6569fbdbfd716632da1b98ffb2809b30e1a6fe25ba882463480c38d04`
- `fault.kicad_sch`: `4176ca5edf852912528c85f27d3eab741d19046dbf641b0121fddc9f7716168c`
