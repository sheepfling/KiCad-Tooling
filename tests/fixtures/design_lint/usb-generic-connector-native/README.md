# Generic USB connector coverage fixtures

These tooling-owned KiCad schematics test
`bus.usb_generic_connector_phy_pair_review`. They use a synthetic three-pin
connector and a synthetic single-port PHY. The connector's data contacts are
generic `Pin_N` functions in the fault and explicit D+/D− functions in the
control. Both schematic sources assign the same positive and negative nets to
the corresponding PHY pins and give the connector and PHY one common reference.

| Fixture | Connector data functions | Expected result |
| --- | --- | --- |
| `fault.kicad_sch` | `Pin_1`, `Pin_2` | One generic connector review candidate |
| `control.kicad_sch` | `D+`, `D-` | No generic connector review candidate |

The fixture does not claim to represent a production connector or verify USB
behavior, reference policy, PCB copper, or physical continuity. The source
hashes are pinned in `kicad_tooling/ci_hosted_usb_generic_connector_cases.py`:

| Fixture | SHA-256 |
| --- | --- |
| `fault.kicad_sch` | `cc6a6fd8b860bfef7e3a784ae0c46eea82e96c591796b13a36013383f5c2317b` |
| `control.kicad_sch` | `a4805756125893183c61278af060ba0cdcadf42180096335340431d0eef89a82` |
