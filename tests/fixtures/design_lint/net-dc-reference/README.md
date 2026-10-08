# Connector/capacitor-only net fixture

These are tooling-owned synthetic KiCad schematics. They contain no proprietary
project data and are not for manufacture.

- `fault.kicad_sch` assigns `J1.1` and `C1.1` to `ANALOG_IN`; no fitted local
  component pin on that net can source or bias it.
- `control.kicad_sch` adds a native output-capable `U1.1` to the same net. That
  extra pin suppresses the deliberately narrow connector/capacitor-only hint.
- `dnp-control.kicad_sch` keeps `J1.1` and `C1.1` assigned to `ANALOG_IN` but
  marks `C1` DNP. KiCad retains the pin assignment in its exported netlist;
  the local predicate ignores the unpopulated capacitor.
- All three schematics connect their other connector and capacitor pins to
  `GND`.

The pure unit and CLI/MCP tests cover the rule predicate and policy behavior.
The optional native regression exports all three schematics twice with the
exact KiCad 10.0.0 and 10.0.5 images pinned by the public template's project
toolchains. It compares normalized netlists and ERC reports, checks the exact
fault membership and DNP state, and records command receipts and source hashes
under the ignored `build/ci-hosted/` tree. ERC is expected to have zero errors
for all three schematics; the heuristic should report `ANALOG_IN` only for the
fitted connector/capacitor fault.

The native regression establishes export repeatability and whether ERC reports
the same synthetic condition. It does not establish that an off-board source,
internal bias path, or board-level copper path is absent from a real design.

## Recorded trial

On 2026-10-01, the native regression passed with the public template's exact
digest-pinned KiCad 10.0.0 and 10.0.5 images. Each source file exported the
same normalized netlist in both versions; repeated netlist and ERC exports also
matched within each version. ERC reported zero errors for all cases. The
lint reported `ANALOG_IN` only for the fitted connector/capacitor fault and
stayed quiet for the output-driver and DNP controls. This is evidence of
incremental detection over ERC for this exact synthetic pattern and evidence
that the native DNP state is honored; it is not a field false-positive rate or
general proof of missing bias.

| KiCad version | Case           | Normalized netlist SHA-256                                         | Normalized ERC SHA-256                                             |
| ------------- | -------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ |
| 10.0.0        | Fault          | `0d648172e85d63def654d6ccdb9d2e397c973ee66510c608b61271659a375dbc` | `fc82a4a2916c31bf54f22e695695a53f8b78476ca57572960ed16058f269901c` |
| 10.0.0        | Driver control | `da0877232f90efe93f2488e6b80e478194122cb68c2125127d48b324cedffe38` | `ab30a48880b3e2c4498b5623c17ab02dd376532c04cf6da1eba12980cae4c369` |
| 10.0.0        | DNP control    | `620e5e3ed5c59caf384e8ad4217219cc5420cccb3ab5c122a2fc836abf806595` | `fc82a4a2916c31bf54f22e695695a53f8b78476ca57572960ed16058f269901c` |
| 10.0.5        | Fault          | `0d648172e85d63def654d6ccdb9d2e397c973ee66510c608b61271659a375dbc` | `a342b6d6f150550b7e1b252a70a08a3c62ac2a3f9b7424766ba0b84cdcbe67ef` |
| 10.0.5        | Driver control | `da0877232f90efe93f2488e6b80e478194122cb68c2125127d48b324cedffe38` | `090b4abe3fdff8346bb0002170a1b48abdd896bbe0949db965f683ab6c32b57a` |
| 10.0.5        | DNP control    | `620e5e3ed5c59caf384e8ad4217219cc5420cccb3ab5c122a2fc836abf806595` | `a342b6d6f150550b7e1b252a70a08a3c62ac2a3f9b7424766ba0b84cdcbe67ef` |

The source SHA-256 values are `34678343d148878ab7ab470a3dd99e049ccfc08969cbd419548397602e5c483a` for
the fault, `312d7a1f6cd61c4c2e05f31ec57e5688c22610f7bb76dd18271d53eba86eb2ec` for the driver
control, and `fecaddc449493001871d6ca049b1d764030d7f72860e3aa11aa492fdcf570924` for the DNP control.
The tested image references were
`ghcr.io/kicad/kicad:10.0.0@sha256:9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3`
and
`ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`.

The command receipts remain reproducible under the ignored `build/ci/` tree
created by the test.
