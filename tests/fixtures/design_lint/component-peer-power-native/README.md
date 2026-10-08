# Synthetic component peer power-pin fixtures

These schematics use two fitted instances of the same embedded synthetic
symbol. Both have a passive shared signal, pin 2 `VDD`, and pin 3 `GND`; every
pin has an explicit net assignment.

| Fixture             | U1 pin 2 / pin 3 | U2 pin 2 / pin 3 | Expected lint result          |
| ------------------- | ---------------- | ---------------- | ----------------------------- |
| `control.kicad_sch` | `+3V3` / `GND`   | `+3V3` / `GND`   | No peer power-pin finding     |
| `fault.kicad_sch`   | `+3V3` / `AGND`  | `+5V` / `DGND`   | Two default `REVIEW` findings |

SHA-256 source digests:

- `control.kicad_sch`: `0198205216be6cd5be0c03ac14b7c2b9de52258aacd564159e16532fadb10446`
- `fault.kicad_sch`: `92a2cfda8088c7eebe8305e5ecf786870ed44bc846acb031fe4bb1d567418ae3`

The digest-pinned native SPI participant lane exports both schematics twice on
KiCad 10.0.0 and 10.0.5. It checks that native netlist parsing retains the
shared symbol identity, full pin inventory, pin functions, pin types, and exact
assignments before running the same design-lint service used by CLI and MCP. It
also retains repeated native ERC JSON reports for both cases, including exact
warning/error types and normalized report hashes, so reviewers can measure
whether native ERC distinguishes the synthetic split.

This compares native ERC reports but does not assume that any warning proves a
missing connection. Pinned exports on both versions reported two
`power_pin_not_driven` errors for the common-domain control and four for the
split-domain fault. Both cases therefore have a generic power-source finding;
the rule adds pin-specific review evidence for the split assignment. The fault
also reported four `isolated_pin_label` warnings because `AGND` and `DGND` each
appear once. These reports do not establish a common-ground requirement, prove
part interchangeability, or show PCB copper or off-board continuity. The labels
are fixture inputs, not electrical requirements. No board or project source is
included.

## Pinned run evidence

The native lane passed on 2026-10-01 and was rerun on 2026-10-02 after
revalidating the source hashes above. Both runs used these exact images:

- KiCad 10.0.0:
  `ghcr.io/kicad/kicad:10.0.0@sha256:9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3`
- KiCad 10.0.5:
  `ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`

The normalized native netlist hashes matched across both versions:

- Control: `27b214dc9bd5b33dc7732f1155267462fb7a4efdcd2ed8efb7614ad3e489c0b6`
- Fault: `afb64b0e55b04276c8c2d45e94a6aeec056a424aeff2bb349be5aba78b36a1f9`

Normalized ERC report hashes, which include the KiCad version, were:

| Version | Control                                                            | Fault                                                              |
| ------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ |
| 10.0.0  | `e78bedb44456f210618bf2160a1623f67aac4daf276c59a58820c8bc776fcd32` | `9d064db5c5e393c7e77db4a61698ffd67230d835abb36fb6a3aa1f56cd515152` |
| 10.0.5  | `360b380c826d3788216181f80d670ee2e6af9c31a02a2b8eb38704cd982c7ec7` | `8b490c1bdac0d2d3b795cabcc127cef25d4d6fc38c16161d76fea8ff480d65cf` |

The raw reports and command receipts remain in ignored `build/` outputs.
