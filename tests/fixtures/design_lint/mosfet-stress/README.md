# Synthetic MOSFET state-stress fixture

This tooling-owned schematic contains one synthetic three-pin N-MOSFET symbol
with separate D, G, and S pins, an exact `PART_ID`, and three labeled nets. It
contains no proprietary project information or real part ratings. Its SHA-256 is
`92e70feba1b173c5cbcf8bf2bc9d820be1f7bf1116448e76b072da0b7d1119b6`.

## Native KiCad 10.0.6 check

The configured local KiCad 10.0.6 CLI exported the schematic netlist twice
and ran ERC twice. The tooling parser read the exported symbol, `PART_ID`,
three-pin inventory, native D/G/S functions, and pin-to-net assignments. The
MOSFET checker passed identity, terminal mapping, required-state coverage, and
the synthetic equality-at-limit case at 48 V VDS and 16 V VGS with a project
utilization limit of 0.8. The repeated normalized netlist digest was
`7061672756bfcb228a64155279b0e637377fc75b6871b3db976729f17292c224`; the
repeated normalized ERC type digest was
`9696e79f6888002c605f848ebbe415dbb5226fb1aefadd1975005af70560635f`. Both ERC
reports had warnings only and zero errors. Raw exports and reports are under
the ignored `build/mosfet-stress-native-kicad-10.0.6/` directory.

The same parsed export also passes an authored 48 V VDS / 16 V VGS control at
the 0.8 limit and fails when only the authored state changes to 49 V / 17 V;
the native netlist, source schematic, and ERC result remain fixed.

## Digest-pinned KiCad 10.0.0 and 10.0.5 acceptance (2026-10-02)

The package acceptance test exported the same schematic and ran ERC twice
under each digest-pinned image. It verified the exact symbol, `PART_ID`,
three-pin D/G/S inventory, and net assignments, then applied the same parsed
native netlist to an exact-limit control and a VDS/VGS over-limit fault.

KiCad 10.0.0 used image
`sha256:9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3`.
Its repeated normalized netlist digest is
`7061672756bfcb228a64155279b0e637377fc75b6871b3db976729f17292c224` and
normalized ERC-type digest is
`4a632f6d163b0861bc357960365da48435ab6959db8977948eaf3f270b321765`.
The 48/16 V equality control passes at the 0.8 limit; the 49/17 V fault fails
both VDS and VGS. Both ERC runs have zero errors.

KiCad 10.0.5 used image
`sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`.
Its repeated normalized netlist digest is the same, and normalized ERC-type
digest is
`a6a910f0c5d37eea8c05212779068c6aa6dcb4472f0dbadeeea166a462f34b77`.
The 48/16 V equality control passes at the 0.8 limit; the 49/17 V fault fails
both VDS and VGS. Both ERC runs have zero errors.

ERC warning-type signatures are stable within each version and differ across
versions. Raw XML digests are retained in ignored `build/ci-hosted/` receipts.
The reproducible test command is:

```sh
export KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test
export KICAD_RUN_NATIVE_COMPONENT_RATING_FIXTURES=1
.venv/bin/python -B -m unittest -q tests.test_ci_hosted.NativeComponentRatingFixtureTests
```

The intervals, rating limits, and utilization threshold in these checks are
synthetic owner-authored values. The fixture demonstrates native identity and
the deterministic comparison only; it does not establish part suitability,
switching stress, safe operating area, thermal performance, or hardware
acceptance.
