# Synthetic SPI chip-select bias cohort trial

These tooling-owned schematic-parser fixtures contain no product design or
proprietary source. They model a W25Q80BV-style flash component with one active-low
`CSN` input and an optional direct resistor to `+3V3`; other flash pins,
controller reset behavior, and PCB routing are outside the trial.

| Fixture                           | Topology                         | kicad-happy `PR-002` result                      |
| --------------------------------- | -------------------------------- | ------------------------------------------------ |
| `candidate-no-pullup.kicad_sch`   | `CSN` has no external resistor   | One missing-pull-up prompt                       |
| `control-fitted-10k.kicad_sch`    | Fitted 10k resistor to `+3V3`    | No prompt                                        |
| `anti-control-dnp-10k.kicad_sch`  | 10k resistor is marked DNP       | No prompt; candidate counts the unpopulated part |
| `anti-control-zero-ohm.kicad_sch` | 0R link connects `CSN` to `+3V3` | No prompt; candidate accepts a hard tie          |

Fixture SHA-256 values:

| Fixture                              | SHA-256                                                            |
| ------------------------------------ | ------------------------------------------------------------------ |
| `candidate-no-pullup.kicad_sch`      | `7be766155da1064934853c9cf60a44b9a9e9021aec1c27b81e0ed1232a690b6c` |
| `control-fitted-10k.kicad_sch`       | `21b78ca14d7276d75e1458e65de5c0dc8c54ad718706b1f8b48697ad005994cf` |
| `anti-control-dnp-10k.kicad_sch`     | `7a55a8bcc9047fbf6765016cebb0677cd3def605c6292593532ddccb97ba232b` |
| `anti-control-zero-ohm.kicad_sch`    | `ee0f0be04dd326a3a378b772b3ec37a44454ba93810b448feb65144df77cb7e1` |

The read-only trial used the MIT-licensed `aklofas/kicad-happy` checkout at
commit `a6bba1add1e18b89e3aa0824b9769ed1d9d79174`. It invoked the deterministic
schematic analyzer directly from that checkout. No package install was
performed; the candidate's broader installation workflow remains unmeasured.
Reports were written to ignored `build/`:

```sh
HAPPY=/path/to/kicad-happy
OUT=build/cohort-spi-bias
mkdir -p "$OUT"
for CASE in candidate-no-pullup control-fitted-10k anti-control-dnp-10k anti-control-zero-ohm; do
  .venv/bin/python -B -I "$HAPPY/skills/kicad/scripts/analyze_schematic.py" \
    "tests/fixtures/design_lint/cohort-spi-bias/$CASE.kicad_sch" \
    --no-hierarchy --only-deterministic --output "$OUT/$CASE.json"
done
```

Repeated runs had identical filtered `PR-002` summaries: one prompt without a
pull-up and none for the fitted 10k, DNP 10k, or 0R cases. The detector
recognizes a bounded device keyword list and `CS` aliases, then treats any
resistor from the selected net to a recognized positive rail as a pull-up. It
does not check fitted state, resistance range, or pin electrical type in this
path. This demonstrates two candidate false negatives, not proof that every
`CSN` pin needs an external resistor.

Tooling's existing `bus.spi_active_low_chip_select_without_pullup` rule produces the missing-bias
prompt for the first fixture, remains quiet for the fitted 10k control, and still prompts for the
DNP and 0R cases. The synthetic baseline is covered by
`tests.test_design_lint_spi.test_spi_active_low_select_bias_hint_is_review_only_and_configurable`,
`tests.test_design_lint_spi.test_spi_select_bias_reports_unusable_pullup_paths`,
`tests.test_design_lint_spi.test_spi_select_bias_recognizes_pullup_paths`, and
`tests.test_design_lint_spi.test_spi_select_bias_ignores_valid_controls`.
The candidate adds no detection on these cases and misses two invalid paths that the local rule
excludes.

Applicability remains device- and startup-dependent. Winbond's
[W25Q80BV datasheet, section 4.1](https://www.winbond.com/upload/technical-support/f0f72951-b845-42ea-9010-faaeab26872f.pdf#page=7)
says `/CS` must track VCC at power-up and presents a pull-up as something to use if needed. This
does not establish the host's reset-time drive state, so the schematic alone cannot determine
whether the external resistor is required. The fixtures were accepted by the cohort parser but were
not imported or checked by native KiCad; ERC, exported netlist, false-positive rate, and reviewer
effort remain unmeasured.
