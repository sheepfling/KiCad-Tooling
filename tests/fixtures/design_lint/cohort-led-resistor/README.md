# Synthetic LED limiter cohort trial

These three standalone schematics are tooling-owned synthetic examples. They
contain no product design or proprietary source.

| Fixture                               | Topology                                                                                             | kicad-happy `LR-001` result                                                          |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `fault-direct-across-rails.kicad_sch` | `Device:LED` directly joins `+3V3` and `GND`                                                         | One “no current-limiting resistor found” finding                                     |
| `control-series-resistor.kicad_sch`   | A fitted `1k` resistor is in series from `+3V3` through the LED to `GND`                             | No `LR-001` finding                                                                  |
| `fault-parallel-resistor.kicad_sch`   | LED remains directly across `+3V3` and `GND`; a `1k` resistor is also placed across those same rails | No `LR-001` finding; the candidate treats the parallel resistor as a current limiter |

Fixture SHA-256 values:

| Fixture                               | SHA-256                                                            |
| ------------------------------------- | ------------------------------------------------------------------ |
| `fault-direct-across-rails.kicad_sch` | `998164b255a1ec4c71a1faf1681366ea0bf3e253cc1a9833d3a6c85b838816b8` |
| `control-series-resistor.kicad_sch`   | `00d7ab8dc51351f400f5599526304ab4576ced2d9cd9f583f093cb37705456c3` |
| `fault-parallel-resistor.kicad_sch`   | `b5fef4b342eccddf9b582ad725ee69aa910b595c92f44042e999c6810459cffd` |

The read-only trial used the MIT-licensed `aklofas/kicad-happy` checkout at
commit `a6bba1add1e18b89e3aa0824b9769ed1d9d79174`. It invoked only the
deterministic schematic analyzer and wrote reports under ignored `build/`:

```sh
HAPPY=/path/to/kicad-happy
OUT=build/cohort-led-resistor
mkdir -p "$OUT"
.venv/bin/python -B -I "$HAPPY/skills/kicad/scripts/analyze_schematic.py" \
  tests/fixtures/design_lint/cohort-led-resistor/fault-direct-across-rails.kicad_sch \
  --no-hierarchy --only-deterministic --output "$OUT/fault.json"
.venv/bin/python -B -I "$HAPPY/skills/kicad/scripts/analyze_schematic.py" \
  tests/fixtures/design_lint/cohort-led-resistor/control-series-resistor.kicad_sch \
  --no-hierarchy --only-deterministic --output "$OUT/control.json"
.venv/bin/python -B -I "$HAPPY/skills/kicad/scripts/analyze_schematic.py" \
  tests/fixtures/design_lint/cohort-led-resistor/fault-parallel-resistor.kicad_sch \
  --no-hierarchy --only-deterministic --output "$OUT/parallel.json"
```

The trial demonstrates review coverage on the simple direct-rail case and a
correct no-finding result on the visible series-resistor control. It also
exposes a topology false negative: the detector accepts a parallel resistor
across the same rails as the LED as if it were in series. This does not measure
electrical behavior or establish whether a current-limiting resistor is
required in every assembly. Repeating all three invocations produced the same
filtered LR-001 summaries.

## Native KiCad source-to-netlist regression

The same three synthetic inputs are exported twice and checked by the local
`component.led_directly_across_supply_and_return` rule. The direct-rail fault
and parallel-resistor fault each produce one LED finding; the series-resistor
control produces none. Parsed netlists are normalized and compared across
repeated exports.

| KiCad  | Pinned image                                                                                         |
| ------ | ---------------------------------------------------------------------------------------------------- |
| 10.0.0 | `ghcr.io/kicad/kicad:10.0.0@sha256:9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3` |
| 10.0.5 | `ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c` |

Reproduce the native fixture lane against the public tooling acceptance
checkout:

```sh
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test KICAD_RUN_NATIVE_LED_RAIL_FIXTURES=1 .venv/bin/python -B -m pytest -q tests/test_ci_hosted.py::NativeLedRailFixtureTests
```

CI enables this test in the digest-pinned package acceptance step. The
container mounts the synthetic fixture directory read-only, disables network
access, and writes its command receipt and netlists under ignored `build/`.
This verifies schematic export and the LED review predicate, not ERC, current,
current limiting elsewhere in the assembly, PCB copper, or hardware behavior.

## Independent output-pin extension

`component.led_directly_driven_from_output` is a separate local review
heuristic. The earlier kicad-happy LR-001 trial did not evaluate output-pin
topology. A separate read-only trial below exercises the cohort's broader
LED-audit classification on the same synthetic output-pin fixtures; it does
not make the cohort report equivalent to the local rule. Three tooling-owned
schematics cover the local predicate, with two more covering a project role
for a custom LED symbol:

| Fixture                                                  | Native topology and expected local rule result                                             | SHA-256                                                            |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------ |
| `fault-direct-output.kicad_sch`                          | Native output pin directly shares an LED terminal; other terminal is `GND`; finding        | `a71215195b1273c29ebbe318d52d32ba7db568a8cb49476ed34bea0252fbdfb2` |
| `control-output-series-return-resistor.kicad_sch`        | Output directly shares an LED terminal; fitted resistor lies in the return leg; no finding | `d64eac25b88d7d355e81f8f05001976f15ea989d9b518086499e30e7ef48ba2c` |
| `fault-output-parallel-resistor.kicad_sch`               | Resistor is parallel to the LED across output and `GND`; finding remains                   | `1c37d1e6c7a70f460f4525f25c1d0ebe89dd8db0cbe8e17b415a15827a9422a0` |
| `fault-custom-direct-output.kicad_sch`                   | Custom `Training:LED_5mm`; unmapped it stays outside the rule, exact role map reports      | `2e2d6909d49c5815c5254aea14125ac6243fba0d45307d875c2563d657bc4f7b` |
| `control-custom-output-series-return-resistor.kicad_sch` | Same custom identity with a fitted return-side series resistor; mapped rule is quiet       | `c5a254ead0887da399cd2ace46db4fde8231711abdb602304eac7e1be68ff047` |

The normalized native netlist contracts for both custom fixtures matched
between the two KiCad versions and on repeated exports:

| Fixture                      | Normalized native contract SHA-256                                 |
| ---------------------------- | ------------------------------------------------------------------ |
| Custom direct-output fault   | `6ed038222748a919bd25f72373c631481d4ba027b200d5eb3bfc000c9787ef5b` |
| Custom series-return control | `c4750bf3b29e57ccb44a9edc951512a45298bf213f96aab2348641b6c324a82a` |

The full native lane exports these five output-pin schematics and the original
three rail-based cases twice on digest-pinned KiCad 10.0.0 and 10.0.5. It
verifies that native output pin types and the custom component's exact `PART_ID`,
symbol, footprint, pin names, and electrical types survive XML netlist parsing;
normalized contracts are repeatable; and the explicit project role map reports
the direct custom-symbol fault while the mapped series-return control stays
quiet. Without that map, the custom symbol stays outside the predicate. For the
parallel-output fixture, the lane also asserts from the native netlist that
`U1.1`, `D1.1`, and `R1.1` share a net and that `D1.2` and `R1.2` share the
other. The synthetic unit tests also cover a series-resistor control on the
output side, non-output or missing pin types, DNP endpoints, stale custom
identity mappings, the same-value unrelated-symbol control, unknown rail
names, stable binding digests, and finding configuration. CLI and MCP parity
use one native-style synthetic netlist and the shared typed service.

Reproduce the pinned native checks:

```sh
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test \
KICAD_RUN_NATIVE_LED_RAIL_FIXTURES=1 \
.venv/bin/python -B -m pytest -q tests/test_ci_hosted.py::NativeLedRailFixtureTests
```

These checks establish the bounded schematic-netlist heuristic only. They do
not establish that current limiting is electrically required, that a resistor
value is suitable, or that the physical board, assembly, or runtime behavior is
correct.

## Read-only kicad-happy LED-audit comparison

On 2026-09-30, the pinned MIT-declared kicad-happy commit
`a6bba1add1e18b89e3aa0824b9769ed1d9d79174` was run twice against the three
output-pin fixtures using its deterministic schematic analyzer. The tested
`analyze_schematic.py` SHA-256 was
`beea21348a0794bd3ce02ea85cb537ff8efe7e63bad70bc7773d7bbe4e484315`, and the
`domain_detectors.py` SHA-256 was
`753b6212198964f02501fc3239305f133efdd89e23250fc6a2525b81451d168b`. Reports
were written under ignored `build/cohort-led-output-review-20260930/`; each
repeated report was byte-identical.

| Fixture                                           | kicad-happy LED-audit result                | First report SHA-256                                               |
| ------------------------------------------------- | ------------------------------------------- | ------------------------------------------------------------------ |
| `fault-direct-output.kicad_sch`                   | `LA-AUD`, `ic_direct`, driver `U1`          | `40704b4fbf8b5f50b47b2582eff8b0133e6985cbec78bf713a7f202887e3f9e1` |
| `control-output-series-return-resistor.kicad_sch` | `LA-AUD`, `resistor_limited`, resistor `R1` | `b0ca7b618bee239748afc7181349943a492719c77bc188af79996600c8dec637` |
| `fault-output-parallel-resistor.kicad_sch`        | `LA-AUD`, `resistor_limited`, resistor `R1` | `602797b1bbdc38fa1172c8d92c8825dee12e070d9e5ad14ed6b7569db4e1f72f` |

The `LA-AUD` classifier distinguishes the direct-drive fault from the
series-return control, but it also labels the parallel-resistor fault
`resistor_limited`. Its one-hop resistor scan does not distinguish a resistor
in series with the LED from one connected in parallel across the LED's same two
nets. The local `component.led_directly_driven_from_output` rule still reports
the parallel case. The cohort report is also coarser: it classifies an IC as
the LED driver but does not identify the native output pin type or bind the
finding to its pin/net evidence. No electrical current, resistor adequacy, or
design intent was established.
The table filters to the LED-audit classifier; each full report also contains
unrelated sourcing, datasheet, and lifecycle findings for the intentionally
sparse synthetic schematic.

Reproduce the read-only comparison from the repository root:

```sh
HAPPY=/private/tmp/kicad-happy-lint-trial
OUT=build/cohort-led-output-review-20260930
mkdir -p "$OUT"
for CASE in fault-direct-output control-output-series-return-resistor fault-output-parallel-resistor; do
  for RUN in first repeat; do
    .venv/bin/python -B -I "$HAPPY/skills/kicad/scripts/analyze_schematic.py" \
      "tests/fixtures/design_lint/cohort-led-resistor/$CASE.kicad_sch" \
      --no-hierarchy --only-deterministic --output "$OUT/$CASE-$RUN.json"
  done
done
```
