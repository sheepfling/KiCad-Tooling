# Empty native netlist evidence fixture

This is a tooling-owned synthetic schematic with no placed symbols. It checks
the LINT-078 evidence boundary: KiCad can successfully export an empty native
netlist, but the source-bound contract coach and design lint must return
`BLOCKED` because there is no component inventory to analyze.

The valid control is the tooling-owned
[`serial-connector-control.kicad_sch`](../serial-peer-connector-reference-native/serial-connector-control.kicad_sch),
which exports component records. No project schematic or authored project
expectation is included.

The native acceptance lane exports both sources twice through the exact
project-selected KiCad 10.0.0 and 10.0.5 images. It compares parsed typed
netlists across repeats and versions, because KiCad XML includes changing
export metadata. The empty fixture must have zero component records and zero
nets; the control must retain a nonempty component inventory.

The unit and CLI/MCP parity tests separately verify that a hash-correct,
successful empty export is rejected by the shared source-bound evidence
reader. Together, these tests prove the native trigger and the typed-service
response. This does not prove that a nonempty export contains every source
symbol or net; project-authored source/net contracts remain necessary for that.

## Native evidence (2026-10-03)

The project-pinned images were:

```text
KiCad 10.0.0: ghcr.io/kicad/kicad:10.0.0@sha256:9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3
KiCad 10.0.5: ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c
```

Both returned exit code 0 for the blank schematic and exported zero components
and zero nets.
Repeated normalized typed netlists matched within each version and across both
versions. Their shared SHA-256 is
`d893aaecc8176cc3016d7d1505d75f98bd7cb06a7cf95aae77884264f83531d1`. The
blank schematic SHA-256 is
`ed107ec68043c2eb02fa6566b289b35f119b37c3296bbd1a0f12705ba36b2c9b`.

The nonempty control exported two components and four nets on both versions.
Its normalized typed-netlist SHA-256 is
`08650946c2dfeb42dda98b16e7ba9b37b934fdd310e6fb70e9801cfec08fef7d`, and its
source SHA-256 is
`7d086f4f838504fa3cefc906f7f9e415240b10d89e95c9063c19780922915f16`. Native
KiCad XML hashes are recorded in acceptance receipts under ignored `build/`
paths; raw XML is not the repeatability oracle because export metadata varies.
