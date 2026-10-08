# kicad_skills clock-output trial

This fixture set tests the documented `analog.clock_no_series_resistor` rule
from `sabas0ba/kicad_skills` against tooling-owned synthetic schematics. The
source topologies and the `direct-drive` control's acceptance are authored for
this trial; they are not derived from a product, datasheet, or real board.

## Candidate provenance

- Repository: `https://github.com/sabas0ba/kicad_skills`
- Commit: `53d1af8bc550f60415b4b8e51a6d2d5924ada03f`
- Package: `eda-toolkit` 0.1.0
- License: Apache-2.0
- Rule source SHA-256:
  `fd7427eb29ee099e3cb8868869be8e8b75ed7d72aeba07ad1b4fa5a8e8597d54`
- License SHA-256:
  `c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4`

The rule selects references beginning with `X` or symbols whose library ID
begins `Oscillator:`. It checks output pin types (or `OUT` in the pin name),
then examines the output net's component references. A resistor with no other
load is accepted; a resistor and load on the same output net is described as a
pull rather than a series component. The predicate does not compare an
authored topology map, inspect DNP state, or parse the resistor value.

## Installation and invocation

This trial reused the isolated Python 3.11.16 environment from the earlier
`analog.no_dc_path` trial at `/private/tmp/eda-cohort-trial-venv`; no candidate
source or environment was copied into this repository. The package had been
built with its pinned setuptools 83.0.0 backend and installed with
`--no-build-isolation --no-deps`.

The exact invocation was:

```sh
/private/tmp/eda-cohort-trial-venv/bin/python -I -m eda_toolkit.cli sch review \
  --no-cli --json --output <ignored-build-report.json> <fixture.kicad_sch>
```

The `--no-cli` run used the candidate's geometry fallback. `kicad-cli` was not
available in this environment, so the trial did not run ERC or a native
netlist export, and it does not establish compatibility with any KiCad version.
The candidate's documented container workflow and its advertised KiCad image
versions were not exercised because Docker's API socket returned permission
denied. Two invocations per fixture produced byte-identical JSON reports.
Generated reports are under the ignored
`build/cohort-trials/kicad-skills-clock/` directory.

## Results

The table records the targeted rule result and the raw report SHA-256 from the
first invocation. Every second report matched the first byte for byte.

| Fixture                             | Source SHA-256                                                     | `analog.clock_no_series_resistor` | Report SHA-256                                                     | Result                                                                                                                                                     |
| ----------------------------------- | ------------------------------------------------------------------ | --------------------------------: | ------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `direct-x-fault.kicad_sch`          | `756364ec8e7c998d8b1c1eb01a11af0132e87141ca8a2f5dbee95a1f5d520720` |          1 at `X1.1 / CLK_DIRECT` | `ef482ffdb69f5dff5ab2cef501980e54263a758235e7d8def7deeaf07fe2968d` | Reports a direct-loaded oscillator output; no part-specific resistor requirement is asserted.                                                              |
| `direct-with-pull.kicad_sch`        | `0b3f0b46766ce603cefcd6bbbb79592dc5cb4ec91c119992372f7ca4c8d9da8b` |          1 at `X1.1 / CLK_DIRECT` | `6b53c07aa94d6da07aa34c825e611d23b7631dcf8a7939febc6a7e5484d92512` | Correctly does not count a shunt pull resistor as a series element.                                                                                        |
| `series-x-control.kicad_sch`        | `e2f6ce6dd59c46aca6206407e11a9e425566d76df8cdf3b3501f212ee0353d7a` |                                 0 | `7a896ddef802142428a88375182652202d6a5f47fd7deeebbbb1189585e6afad` | Quiet on a fitted series path with a downstream input.                                                                                                     |
| `direct-library-control.kicad_sch`  | `0efad29774e5342391273bf7790e621eb934e4e4e95cebb04fd933bee7d5c4f2` |          1 at `U2.1 / CLK_DIRECT` | `d64c25cada1ecb7729a3c376584b617f3a3d85916b938baba6ee97cf668919d6` | Warns on the direct-drive alternative designated as allowed by the trial setup. This is a fixture-relative over-prompt, not field false-positive evidence. |
| `series-dnp-miss.kicad_sch`         | `3e81272c75cd5d4cbfaaeac06ab1231a4ba24219d01b6d5a2a21e3e9dd081ab9` |                                 0 | `cb93b01edfe720c5f7a23f0d69e79ec22bf072235c49a05a5ed6725f38074643` | Misses a series component marked DNP because it only sees a resistor reference on the source net.                                                          |
| `series-wrong-value-miss.kicad_sch` | `6738f4aaca061a34472fe1a2feffcd749f40237845e9e67fb6cf2938ac8fc8cd` |                                 0 | `345c2fdba4fd1edcc5ab7d3da129816e7a6a7f895adfb2c7d93fa96a93befe46` | Misses a synthetic 1 MΩ series component because resistor values are not checked.                                                                          |
| `crystal-control.kicad_sch`         | `d4dbf294996675ee4cd44c18ec757ac5061b0b9028980b135c27d7e3704f9b0d` |                                 0 | `61f959516158a3a7a341bf1c445231efbd67674868ae88923898fcf90c3724ce` | Quiet on a passive crystal symbol with no oscillator output pin.                                                                                           |

All reports had zero errors. Other warning/info counts include candidate checks
outside this trial and are not treated as clock-rule results.

## Disposition

The candidate demonstrates a bounded topology hint for a directly loaded
oscillator-module output and distinguishes a series resistor from a shunt
resistor. It does not prove that the output requires damping, and it cannot
honor a project-specific direct-drive decision. It also treats a DNP or
arbitrarily valued resistor as a valid series component. No cohort runtime
dependency or generic first-party rule is justified by this trial.

A source-bound map may still provide deterministic coverage when a project
owner supplies the exact output pin, load pins, expected direct/series choice,
part identity, resistor endpoints, and reviewed value range. Native KiCad
evidence, reviewer effort, applicable part sources, and behavior on approved
non-proprietary designs remain unmeasured. No proprietary design source or fixture was
used.
