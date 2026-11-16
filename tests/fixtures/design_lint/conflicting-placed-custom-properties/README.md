# Conflicting placed custom-property fixtures

These source fixtures are synthetic tooling regressions. They contain no
product-board data. Each schematic is a self-contained KiCad 10 source with a
USB connector and a simple controller symbol; only the connector's placed
property fields vary between cases.

The fault places two direct `MFR_PN` fields on J1 with values
`SYNTHETIC-PN-A` and `SYNTHETIC-PN-B`. Digest-pinned KiCad 10.0.0 and 10.0.5
netlist exports preserve `SYNTHETIC-PN-B`, while KiCad 10.0.8 preserves
`SYNTHETIC-PN-A`. All three versions export just one `MFR_PN` field. This is a
source-integrity review cue; it does not determine the intended manufacturer
part number.

The source lint reports only conflicting duplicate user-defined fields. It
ignores identical duplicate values, separate field names (including
case-distinct names), the five default fields, DNP, `ki_`-prefixed reserved
names, and conflicts only present in embedded library definitions. KiCad's
[symbol-fields documentation](https://docs.kicad.org/10.0/en/eeschema/eeschema.html)
describes the five default fields, arbitrary additional field names, and the
reserved `ki_` prefix.

| Fixture                                   | Purpose                                                                    | SHA-256                                                            |
| ----------------------------------------- | -------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`                         | Conflicting placed `MFR_PN` values                                         | `65bf170dd28749c5f373edc88bba168eb5d2b8dac76ee441eef429f442669e27` |
| `control-unique.kicad_sch`                | One placed `MFR_PN` value                                                  | `4c728ad08407fcf98468cb2fc3fdeec77e951e59955275060f58a77faf48ee26` |
| `control-identical-duplicates.kicad_sch`  | Repeated equal `MFR_PN` values                                             | `429ae05ed1f5802dc6586757f151682e90892b429ff099fb54b873c7a22e7e85` |
| `control-distinct-names.kicad_sch`        | Distinct `MFR_PN` and `MFR_PN_ALT` fields                                  | `1e454b117bce079ddc84a7371226c08ed6768915a7446e7cbf7c7bd8af3f0cb5` |
| `control-case-distinct-names.kicad_sch`   | `MFR_PN` and `mfr_pn` remain distinct in all three tested exports          | `5ce38ea480b1c025ba9ff708876af59bd1535a9149132e486642043c176a5892` |
| `control-standard-description.kicad_sch`  | Conflicting standard `Description` fields are outside this user-field rule | `df60942e9d239d9894080e19c830280e6db443acf5b56aa8d58c618b02341595` |
| `control-reserved-ki-prefix.kicad_sch`    | Conflicting reserved `ki_custom` fields are excluded                       | `55a86c06fce6d80a7b403b16267bda8d25adbcd55379e918d2452c17833c6ea8` |
| `control-library-only-conflict.kicad_sch` | Conflicting fields only in an embedded library definition                  | `6b9e01134701a7ab2707972e41712e8f7420aaa064206e638921adf1a8a7458b` |

The native regression exports the fault and unique, identical-duplicate, and
distinct-name controls twice on the digest-pinned KiCad 10.0.0, 10.0.5, and
10.0.8 images. Fixture files are mounted read-only and the Docker lane has no
network access.
