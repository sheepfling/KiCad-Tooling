# Native connector-inventory candidate regression

This synthetic pair checks that connector coverage can discover a standard
connector library identity under a nonstandard `U` reference after native
netlist export. The fault contains `U7` with
`Connector_Generic:Conn_01x02` and `U8` with `Connector:TestPoint_Alt`; the
report returns exactly `U7` as `UNDECLARED`. The control contains only the
test-point symbol; with an explicit inventory-review basis, coverage is
`COMPLETE` with no candidates.

The embedded symbol definitions are minimal tooling-authored shapes carrying
the standard library IDs. They test the identity KiCad writes to native
`libsource` and the shared parser consumes; they do not validate the official
symbol geometry, pinout, installed library contents, or whether the project
should use a connector under a `U` reference. No external or proprietary project
source is included.

SHA-256 of the version-controlled schematic inputs:

- Fault: `db0fe26dee3a199bc07999f0665f6da5addd5ab49d6d5d773254ce6cde6ddab1`
- Control: `43fe30b4501b9efeb98a2eccdb1a9aec46b56086c871564fb3f7a5ebc542ab18`

The package acceptance lane exports both schematics twice using the exact
KiCad 10.0.0 and 10.0.5 images selected by the public template checkout. It
checks the reported version, exact exported library identities, normalized
netlist repeatability, candidate references, and coverage report digests. The
lane does not run ERC because this check concerns inventory coverage.

## KiCad 10.0.0

- Image: `ghcr.io/kicad/kicad:10.0.0`
- Image digest SHA-256:
  `9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3`
- Fault normalized netlist SHA-256:
  `296accdb51487e304f982723db189196afd35e533ef46cff6a1cf9be38365a3b`
- Control normalized netlist SHA-256:
  `60fe767e2aea9871be56b20ffcbfa3cbed095e8fdf102198072f44bd79917ffe`
- Fault/control coverage report SHA-256:
  `fc6d10e41d24b8c18b3fe2b5245764513bc7da248a7d993cd4839c9b02f8415f` /
  `9e324160dadbee850d5f786f9c4668718ea1e9254c0f9b232c28fdc108101d19`
- Fault raw netlist SHA-256, first/repeat:
  `5fc93e9490ea69a13eef5aaa0176bd27ab82bd9da702e45188d3d73f84db337e` /
  `5fc93e9490ea69a13eef5aaa0176bd27ab82bd9da702e45188d3d73f84db337e`
- Control raw netlist SHA-256, first/repeat:
  `65a010787774cc9268227da0d433823fd2000425b43bbd3989f5cd20bb317617` /
  `65a010787774cc9268227da0d433823fd2000425b43bbd3989f5cd20bb317617`

## KiCad 10.0.5

- Image: `ghcr.io/kicad/kicad:10.0.5`
- Image digest SHA-256:
  `fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`
- Fault normalized netlist SHA-256:
  `296accdb51487e304f982723db189196afd35e533ef46cff6a1cf9be38365a3b`
- Control normalized netlist SHA-256:
  `60fe767e2aea9871be56b20ffcbfa3cbed095e8fdf102198072f44bd79917ffe`
- Fault/control coverage report SHA-256:
  `fc6d10e41d24b8c18b3fe2b5245764513bc7da248a7d993cd4839c9b02f8415f` /
  `9e324160dadbee850d5f786f9c4668718ea1e9254c0f9b232c28fdc108101d19`
- Fault raw netlist SHA-256, first/repeat:
  `e3c314c965f46388029dbc69deeff9efc7dcfcbb4e548099add2d0ebcef735c1` /
  `b397cc3ceea4133cbfafcf0a94fcb18b9eeeaf6bc4b6c83693a1be7504908ba2`
- Control raw netlist SHA-256, first/repeat:
  `1b33070803a1f9fbf4e350457ae61b2bcc31360f26f7318e89266df936960130` /
  `f693d97e486fb684b023400655057c44ddeea3afce4012c9913a0f398a7508e9`
- KiCad 10.0.5 raw exports include timestamps and differ across repetitions;
  their parsed netlists normalize to the hashes above.

Reproduce through the package acceptance test with
`KICAD_RUN_NATIVE_CONNECTOR_FIXTURES=1`. The selected template projects bind
the image pins and exact KiCad versions; receipts stay under ignored `build/`.
