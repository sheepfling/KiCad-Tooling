# USB-C SBU asymmetric-assignment fixtures

These tooling-owned synthetic schematics exercise a paired-pin review hint.
They contain no product board or project data.

- `fault.kicad_sch` assigns the connector's SBU1 contact to `SBU1_BUS` but
  explicitly leaves controller U1's SBU1 pin open; U1's SBU2 pin is assigned
  to `SBU2_BUS`.
- `control.kicad_sch` connects both controller SBU pins to their corresponding
  connector contacts on separate named nets.

Reviewed schematic SHA-256 digests:

| Fixture             | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`   | `7244d4285c4624aadc302905ab051462e16280a56e8dfe01b1791aea701f6bed` |
| `control.kicad_sch` | `9b16bfcbc1efff9a72db1ac636a3decdb069f0136b827d03b6aed72ea66128d7` |

The exact-version native lane exports each source twice with digest-pinned
KiCad 10.0.0 and 10.0.5 images, checks normalized-netlist repeatability,
assignment and open-pin inventories, expected lint subjects, and zero ERC
errors. The result does not establish alternate-mode use, whether one SBU line
is required, PCB copper, or physical continuity.
