# Synthetic USB series-resistor cohort trial

These tooling-owned schematic-parser fixtures contain no product design or
proprietary source. They model only two named USB data pins; connector power,
shielding, PHY behavior, and PCB routing are deliberately outside the trial.

| Fixture                                    | Topology                                                     | kicad-happy `PR-004` result        |
| ------------------------------------------ | ------------------------------------------------------------ | ---------------------------------- |
| `candidate-no-external-resistor.kicad_sch` | `J1` exposes named D+ and D− nets without external resistors | Two prompts, one for each data pin |
| `control-two-series-resistors.kicad_sch`   | A visible 22R resistor is in series on each data net         | No `PR-004` finding                |

Fixture SHA-256 values:

| Fixture                                    | SHA-256                                                            |
| ------------------------------------------ | ------------------------------------------------------------------ |
| `candidate-no-external-resistor.kicad_sch` | `16880c0e70332f792f25dc7db6250bffbc08378f698db73f77048892f6e635fc` |
| `control-two-series-resistors.kicad_sch`   | `8558ac5863cde2a6775b9bea31cc9c55a5d639ef84671f7a3be3347e81c5bd96` |

The read-only trial used the MIT-licensed `aklofas/kicad-happy` checkout at
commit `a6bba1add1e18b89e3aa0824b9769ed1d9d79174`. It invoked only the
deterministic schematic analyzer directly from that checkout and wrote
generated reports under ignored `build/`. No package install was performed;
the candidate's broader installation workflow remains unmeasured:

```sh
HAPPY=/path/to/kicad-happy
OUT=build/cohort-usb-series
mkdir -p "$OUT"
.venv/bin/python -B -I "$HAPPY/skills/kicad/scripts/analyze_schematic.py" \
  tests/fixtures/design_lint/cohort-usb-series/candidate-no-external-resistor.kicad_sch \
  --no-hierarchy --only-deterministic --output "$OUT/candidate.json"
.venv/bin/python -B -I "$HAPPY/skills/kicad/scripts/analyze_schematic.py" \
  tests/fixtures/design_lint/cohort-usb-series/control-two-series-resistors.kicad_sch \
  --no-hierarchy --only-deterministic --output "$OUT/control.json"
```

The candidate distinguished this simple no-external-resistor topology from
the visible-resistor control. Repeating both invocations produced identical
filtered `PR-004` findings. Its predicate recognizes connector names containing
`USB`, a bounded set of D+/D− pin names, and resistor values from 15–33 Ω; it
also attempts a datasheet-feature exemption for some MCU parts. The trial does
not establish that either resistor is required, that 22R is suitable, or that
the fixture represents a complete or native-validated USB design. No
integrated-PHY, USB-C, USB 3.x, branched-line, or alternate resistor-value
control was run. Exact-version KiCad import, ERC, and netlist export were
unavailable in this environment.

The local baseline has no generic rule about external USB series resistors. A
synthetic Tooling `NetlistContract` run emitted the broader
`signal.named_pair_without_reviewed_requirement` prompt on `USB_D+`/`USB_D−`
for both the no-resistor candidate and the resistor control. That check asks
whether the names indicate a physical pair; it does not review series parts.
PR-004 therefore adds a more specific review question, not new electrical
detection, and may duplicate review effort. Its connector naming and resistor
value range assumptions are too broad to adopt as a universal requirement. Keep it
deferred until a project-authored interface requirement can state the
applicable PHY, connector pins, expected external path, or reasoned
no-external-resistor disposition.

## Source-backed PHY applicability follow-up

The follow-up uses only synthetic tooling fixtures. ST AN4879 Rev 12 (June
2026) identifies STM32F103 as a full-speed device with an integrated PHY and
states that internal USB PHY output matching impedance is built into the pads,
so no external resistors are needed. TI's TUSB2036 Rev I datasheet (revised
March 2017), Section 9.2, says its USB DP/DM signal pairs require approximately
27 Ω series resistors. The source guidance differs by PHY:

- [ST AN4879](https://www.st.com/resource/en/application_note/an4879-usb-hardware-and-pcb-guidelines-using-stm32-mcus-stmicroelectronics.pdf)
- [TI TUSB2036 datasheet](https://www.ti.com/lit/ds/symlink/tusb2036.pdf)

| Fixture                                      | Modeled path                                            | `kicad-happy` PR-004 result                                           |
| -------------------------------------------- | ------------------------------------------------------- | --------------------------------------------------------------------- |
| `integrated-stm32-fs-direct.kicad_sch`       | STM32F103 direct D+/D− connection, no external resistor | Two prompts; false prompt for this documented integrated-PHY topology |
| `external-hub-no-series-resistors.kicad_sch` | TUSB2036 pair with required external parts omitted      | Two prompts                                                           |
| `external-hub-control-27r-series.kicad_sch`  | TUSB2036 pair with 27R on both lines                    | No PR-004 finding                                                     |

The two new no-resistor fixtures each produced one finding per data line on two
consecutive deterministic runs; the fitted 27R control produced no finding on
either run. The candidate's MCU feature lookup did not exempt the STM32 fixture
because no trusted F103 feature cache was present. This shows the value and
boundary of the candidate prompt; it does not make that prompt a universal
resistor requirement.

SHA-256 values for the follow-up fixtures:

| Fixture                                      | SHA-256                                                            |
| -------------------------------------------- | ------------------------------------------------------------------ |
| `integrated-stm32-fs-direct.kicad_sch`       | `d6f5186e63b00c5291989596ad5fc446c5e06d75cc940900e0e76cb87d751284` |
| `external-hub-no-series-resistors.kicad_sch` | `b314005226c339e84134f5ead8e6b463fc7d6b75ba549c22ab867b7104b095cb` |
| `external-hub-control-27r-series.kicad_sch`  | `91c9cde2d8e3f9e5eaf721cb58285717c4c8793c17177baebb5cf536846f2d9b` |

Reproduce the three cases twice with the pinned cohort checkout:

```sh
HAPPY=/path/to/kicad-happy
OUT=build/cohort-usb-series
mkdir -p "$OUT"
for CASE in integrated-stm32-fs-direct external-hub-no-series-resistors external-hub-control-27r-series; do
  for RUN in 1 2; do
    .venv/bin/python -B -I "$HAPPY/skills/kicad/scripts/analyze_schematic.py" \
      "tests/fixtures/design_lint/cohort-usb-series/$CASE.kicad_sch" \
      --no-hierarchy --only-deterministic --output "$OUT/$CASE-run$RUN.json"
  done
done
```

Tooling's independent `design_lint.usb_data_path_map` is exercised by
`tests.test_usb_data_paths`: the documented direct integrated-PHY map and
external TUSB2036 27R map pass, while removing required R1 produces a single
D+ mismatch. Its series range remains a project-authored choice. The current
test input is a synthetic `NetlistContract`, not a native KiCad export; exact
KiCad import, ERC, and exported-netlist comparison remain open.
