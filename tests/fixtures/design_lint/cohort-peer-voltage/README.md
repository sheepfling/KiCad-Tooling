# Synthetic cross-supply SPI peer fixtures

These schematics are tooling-owned cohort inputs. They contain no product or
proprietary source. Each has two synthetic ICs sharing four SPI nets; each IC has one
explicitly named positive supply pin.

| File                 | U1 rail | U2 rail | SHA-256                                                            |
| -------------------- | ------- | ------- | ------------------------------------------------------------------ |
| `mismatch.kicad_sch` | `+5V`   | `+3V3`  | `e1d908707a9da91bd2159a7602d67247cbe04636a15f7f8bdc39889a16782ec1` |
| `matching.kicad_sch` | `+3V3`  | `+3V3`  | `6760ea3e514d76d3b663f8acabea95318b836d179011404e47dcf04012ddee0b` |

The pair derives from the tooling-owned
[`spi-participant-native/multi-device.kicad_sch`](../spi-participant-native/multi-device.kicad_sch),
SHA-256 `0c5d901b4dc70ccb3c3818bd8fdf002955a6322b814ac2e7f8bab086d47d5e06`.
The derived schematic body before adding the two supply labels has SHA-256
`99e237e06b9b1b7ae933a6bbfb76ebe536d8b39b139306e92013f90ef3009d10`.

## Candidate trial

On 2026-10-01, the deterministic `VM-001` detector from
[`aklofas/kicad-happy`](https://github.com/aklofas/kicad-happy/tree/a6bba1add1e18b89e3aa0824b9769ed1d9d79174)
was run directly from its extracted v2.2.1 source archive. The candidate
declares MIT; the tested `validation_detectors.py` SHA-256 is
`b4f0b0deb0ce4bd5c598840f3cdc1eaceced883fc2929d7e7a1a9c0a27acbfc9`, and the
archive's `LICENSE` SHA-256 is
`f542344efc2d21d18c81507e8168ab256c32ece6e7acb1bc8bde71950c9b6bb5`. The
archive had no Git metadata. No package was installed and no candidate source
was copied into this repository.

The command was the candidate's `analyze_schematic.py <fixture>
--no-hierarchy --only-deterministic --compact`, invoked with Python 3.11
isolated mode. Each case ran twice with `PYTHONHASHSEED=1` and `73`. The
detector's datasheet lookup helper was unavailable in the isolated interpreter,
so no cached device facts influenced this result. Reports remain under ignored
`build/ci/cohort-peer-voltage/`.

| Input                | VM-001 result                                                      | All candidate findings | Repeated report SHA-256                                            |
| -------------------- | ------------------------------------------------------------------ | ---------------------: | ------------------------------------------------------------------ |
| `mismatch.kicad_sch` | Four `error` findings: `SPI_CS`, `SPI_MISO`, `SPI_MOSI`, `SPI_SCK` |                     13 | `6e6e7e82de5659538d9ef3aa6850e85a5ae71df6aee5cf48e834732384c13de7` |
| `matching.kicad_sch` | No VM-001 findings                                                 |                      6 | `4f9bbbbe9571cd9a171065b132e0fc26d2b4d014312271270d4bee1cb22f6c61` |

Both full JSON reports were byte-identical across the two hash seeds. This is
a parser-level candidate comparison; the local machine did not have
`kicad-cli`, so no native export or ERC comparison was made. The same-rail
fixture is a negative control for the candidate predicate, not an electrical
approval.

## Interpretation

The candidate offers a useful *coverage prompt hypothesis*: unlike LINT-061's
authored compatibility map, VM-001 can surface an unmapped shared digital net
when the attached ICs have differently named, voltage-explicit rails. The
current detector estimates each IC's rail from its first recognized power net,
uses generic voltage thresholds, and reports `error` with a level-shifter
recommendation. It does not establish pin direction, device-specific `VIH`,
`VIL`, absolute limits, or whether a receiver is 5 V tolerant. Those claims
are too strong for an inferred rail-name relationship.

No cohort code or threshold is adopted. LINT-066 tracks a possible local
`REVIEW` prompt for missing peer-voltage review coverage. It must preserve the
rail names as clues, avoid making a compatibility claim, and allow project
overrides. The local LINT-061 contract remains the check for exact,
source-backed output and input limits. False-positive rate, reviewer effort,
and performance on approved non-proprietary projects remain unmeasured.
