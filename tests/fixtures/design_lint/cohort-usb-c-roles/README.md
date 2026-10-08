# Synthetic USB-C CC role cohort trial

These three standalone schematics are tooling-owned synthetic inputs. They
contain no proprietary or product design data and are marked not for manufacture.

| Fixture                       | Synthetic topology                                                       | kicad-happy USB-C result                                                                          |
| ----------------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------- |
| `unmapped-port.kicad_sch`     | `J1` has separate `CC1_NET` and `CC2_NET`; no CC resistors or controller | Reports two `UC-003` missing 5.1 kΩ pull-down findings even though its inferred role is `unknown` |
| `source-rp-control.kicad_sch` | `R1` and `R2` are 56 kΩ from CC1/CC2 to `+5V`                            | Classifies `source`; no `UC-003` findings                                                         |
| `sink-rd-control.kicad_sch`   | `R1` and `R2` are 5.1 kΩ from CC1/CC2 to `GND`                           | Classifies `sink`; both pull-down checks pass                                                     |

## Cohort analyzer trial

The read-only trial used
[`aklofas/kicad-happy` v2.1.0 at commit `f765dc0916e9752fe2639ca5bad4bda2d5161b8f`](https://github.com/aklofas/kicad-happy/tree/f765dc0916e9752fe2639ca5bad4bda2d5161b8f),
which declares the MIT license. The inspected
[USB-C role and topology logic](https://github.com/aklofas/kicad-happy/blob/f765dc0916e9752fe2639ca5bad4bda2d5161b8f/skills/kicad/scripts/analyze_schematic.py#L7976-L8156)
and
[`UC-003` finding text](https://github.com/aklofas/kicad-happy/blob/f765dc0916e9752fe2639ca5bad4bda2d5161b8f/skills/kicad/scripts/analyze_schematic.py#L8317-L8332)
were run from the pinned checkout. The
[license file](https://github.com/aklofas/kicad-happy/blob/f765dc0916e9752fe2639ca5bad4bda2d5161b8f/LICENSE)
was inspected at the same commit.

The trial invoked only the deterministic schematic analyzer directly with
Python 3.11, `--no-hierarchy`, and `--only-deterministic`. No Python package or
hosted review service was installed. The focused `usb_compliance` result and
`UC-*` findings were identical across repeated runs for all three fixtures.
Candidate checkouts and reports stayed under `/private/tmp`; no candidate
implementation or output was copied into this repository.

This comparison did not demonstrate unique actionable coverage over the local
rules. LINT-053 asks for a reviewed project role map whenever the supported
CC1/CC2 pin-function pair is absent from that map. LINT-012 checks the
project-declared CC topology after a role is recorded. Running LINT-053 on the
same parsed native contracts produced one `J1` role-map finding in all three
cases, including the valid source and sink topologies. The candidate recognizes
the simple source and sink controls, but its unconfigured case exposes a
limitation: it reports a `sink`-specific missing-pull-down finding while its
own role field says `unknown`. A source, dual-role, or controller-managed port
can make that finding inapplicable. The candidate has no project-authored role
map that would resolve this applicability question. The trial therefore does
not justify a dependency or replace the local contract model.

## Native source-to-netlist evidence

Each source was exported twice with digest-pinned KiCad 10.0.0 and 10.0.5,
using `kicad-cli sch export netlist --format kicadxml`. The exports were parsed
with the same `kicad_tooling.validate.read_netlist` parser used by the local
verification tooling. The normalized contract was serialized with sorted JSON
keys before hashing. Both repeats and both KiCad versions produced the same
normalized digest per fixture. The native exports preserve these exact nets:

| Fixture                       | Native net assignments                                                             | Normalized netlist contract SHA-256                                |
| ----------------------------- | ---------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `unmapped-port.kicad_sch`     | `J1.4` on `CC1_NET`; `J1.5` on `CC2_NET`                                           | `aed83b3fb5f41e28df70bbf9930ba5864a5bf32fd1a1e8785bcdc863182c83bc` |
| `source-rp-control.kicad_sch` | `R1=56k` from `J1.4`/`CC1_NET` to `+5V`; `R2=56k` from `J1.5`/`CC2_NET` to `+5V`   | `f88a8f36c85ce3c84cb44c145ac57639890a99369821c17d40a733907740e613` |
| `sink-rd-control.kicad_sch`   | `R1=5.1k` from `J1.4`/`CC1_NET` to `GND`; `R2=5.1k` from `J1.5`/`CC2_NET` to `GND` | `6ab178bc1c36b936f2ff75995d76fcb2e91fc30a3d5e53c81ad9d22efe7531e0` |

| KiCad  | Digest-pinned image                                                                                  |
| ------ | ---------------------------------------------------------------------------------------------------- |
| 10.0.0 | `ghcr.io/kicad/kicad:10.0.0@sha256:9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3` |
| 10.0.5 | `ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c` |

SHA-256 hashes of the version-controlled schematic inputs:

| Fixture                       | SHA-256                                                            |
| ----------------------------- | ------------------------------------------------------------------ |
| `unmapped-port.kicad_sch`     | `3e3bb8ea41a574c2bdc3f8e591f8af8b429985b07f287603e33ea5a46d04758c` |
| `source-rp-control.kicad_sch` | `b9913fa1e44adaaa3837257dc0756bcb39411b9bb79dcd1568c1a264248a1f8f` |
| `sink-rd-control.kicad_sch`   | `5ac40420e4adcc7f2005e1808f1ebdeb765fd4907113bfa5be657407d2d6d789` |

The native check establishes only reproducible schematic export and the stated
synthetic net assignments. It does not run ERC, review USB compliance, infer
the required role, inspect PCB copper, or establish hardware behavior.
The source and sink controls are also exercised by the first-party LINT-053
native regression lane; see the
[role-map fixture notes](../usb-c-port-native/README.md).
