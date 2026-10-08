# Synthetic IC power-pin and decoupling cohort trials

These tooling-owned schematics support read-only cohort comparisons and native
ERC / local lint regressions for IC power-pin sources and decoupling presence.
They do not represent a product board and contain no proprietary source.

| Fixture                                 | Pin/net pattern                                                                                                                 | Role / cohort result                                                           |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `fault.kicad_sch`                       | `U1.1` is an embedded `power_in` symbol pin on `LOCAL_A`; `C1` connects that net to `GND`; no positive rail or source is shown. | `PP-001` finding                                                               |
| `control.kicad_sch`                     | Same pin and capacitor arrangement, with the supply net named `+3V3`. No source component is shown.                             | No `PP-001`; isolates the rail-name branch and is not a valid source control.  |
| `no-cap.kicad_sch`                      | Fitted `U1.1` is assigned to recognized positive rail `+3V3`; no capacitor component is placed on that schematic net.           | `DO-DET` review observation                                                    |
| `source-backed-control.kicad_sch`       | `U1.1`, synthetic `power_out` pin `U2.1`, and `C1.1` share `+3V3`.                                                              | Native ERC control; cohort reports capacitor coverage.                         |
| `source-backed-no-cap.kicad_sch`        | `U1.1` and synthetic `power_out` pin `U2.1` share `+3V3`; no capacitor is present.                                              | Native ERC / LINT-046 comparison; cohort flags missing decoupling.             |
| `source-backed-dnp-capacitor.kicad_sch` | `U1.1`, `U2.1`, and DNP `C1.1` share `+3V3`; `C1.2` connects to `GND`.                                                          | LINT-046 DNP regression; kicad_skills treats the unpopulated part as coverage. |

| Fixture                                 | SHA-256                                                            |
| --------------------------------------- | ------------------------------------------------------------------ |
| `fault.kicad_sch`                       | `0d42a2f557d2488425a7b1767e7e3b782c4bfe2c2e11bc2344f41513c49c7fb9` |
| `control.kicad_sch`                     | `2e67336b13f8ff9b62dd4e40bd45a4116e4d825d78f361537ea3693d4e18d4a2` |
| `no-cap.kicad_sch`                      | `09ec95768fb247b1ec781a078f585b27eee66ae7e40bc0251cefb7ebef511e7a` |
| `source-backed-control.kicad_sch`       | `2a3632b71b5c7bc01b282cb2d23a5b49df5759364a99e588b98b659654c9d45f` |
| `source-backed-no-cap.kicad_sch`        | `5db3396470f1e3b8101e428dc25b41c4166f1748e4a68ad88a3ac2757173952a` |
| `source-backed-dnp-capacitor.kicad_sch` | `8184bd9c297b40d0192af1e446206939ec7d5466bc8e306a0292472da7424b6c` |

The trial used the MIT-licensed kicad-happy checkout at commit
`a6bba1add1e18b89e3aa0824b9769ed1d9d79174`. It ran the schematic analyzer
directly without installing the cohort workflow:

```sh
HAPPY=/path/to/kicad-happy
OUT=/private/tmp/kicad-happy-pp001
mkdir -p "$OUT"
.venv/bin/python -B -I "$HAPPY/skills/kicad/scripts/analyze_schematic.py" \
  tests/fixtures/design_lint/cohort-power-pin-dc/fault.kicad_sch \
  --no-hierarchy --only-deterministic --output "$OUT/fault.json"
.venv/bin/python -B -I "$HAPPY/skills/kicad/scripts/analyze_schematic.py" \
  tests/fixtures/design_lint/cohort-power-pin-dc/control.kicad_sch \
  --no-hierarchy --only-deterministic --output "$OUT/control.json"
.venv/bin/python -B -I "$HAPPY/skills/kicad/scripts/analyze_schematic.py" \
  tests/fixtures/design_lint/cohort-power-pin-dc/no-cap.kicad_sch \
  --no-hierarchy --only-deterministic --output "$OUT/no-cap.json"
```

At that commit, the fault produced `PP-001` plus the cohort's `RS-001` “no
declared source” warning. The control produced no `PP-001`, but still produced
`RS-001`. The Tooling `design_lint.evaluate` baseline returned `PASS` with no
candidate for an equivalent synthetic `NetlistContract` that had no authored
power-connectivity requirement.

The earlier source-less `no-cap.kicad_sch` run emitted informational `DO-DET`
“IC U1 missing decoupling on +3V3”; its capacitor-bearing control emitted
“Decoupling coverage on +3V3”. A source-backed rerun is recorded below.

## Source-backed cohort follow-up

At the same pinned commit, the analyzer was run twice on each source-backed
fixture using `--no-hierarchy --only-deterministic`. The no-cap reports each
contained informational, heuristic `DO-DET` observations for U1 and U2:
“IC U1 missing decoupling on +3V3” and “IC U2 missing decoupling on +3V3”.
The capacitor-bearing control contained the informational “Decoupling coverage
on +3V3” observation for C1 and no IC-missing-decoupling observation. The
candidate therefore still distinguishes symbol presence when the rail has an
explicit `power_out` source. It also recommends decoupling for U2, the synthetic
source component, showing that its applicability is broader than LINT-046's
`power_in` target. These observations are hints; they do not establish whether
either component needs a capacitor.

The two no-cap report files were byte-identical across repeats
(`1d18d969e58ff7debab294840a798e4daa6aaa218af719b4132977d797e90501`); the two
control reports were also byte-identical
(`8b059070f12dd6a44f59e1e6255775d2be622416a649c4bd05d47894601275dd`). The
JSON reports remained in `/private/tmp` and are not stored here. Reproduce with
the same command shown above, substituting these inputs and distinct output
paths:

```sh
for fixture in source-backed-no-cap source-backed-control; do
  .venv/bin/python -B -I "$HAPPY/skills/kicad/scripts/analyze_schematic.py" \
    "tests/fixtures/design_lint/cohort-power-pin-dc/$fixture.kicad_sch" \
    --no-hierarchy --only-deterministic --output "$OUT/$fixture.first.json"
  .venv/bin/python -B -I "$HAPPY/skills/kicad/scripts/analyze_schematic.py" \
    "tests/fixtures/design_lint/cohort-power-pin-dc/$fixture.kicad_sch" \
    --no-hierarchy --only-deterministic --output "$OUT/$fixture.repeat.json"
done
```

This corroborates the LINT-046 review-coverage hypothesis against native ERC;
it is not a unique detection beyond the local LINT-046 prompt. It does not show
that either schematic is electrically complete or that a capacitor is
required, suitably valued, placed, or physically effective.

## PP-001 source-backed recheck

On 2026-09-30, the same pinned kicad-happy commit was run twice on the
source-less fault, name-only control, source-backed no-cap fixture, and
source-backed capacitor control. The analyzer and detector files matched the
commit (`analyze_schematic.py` SHA-256
`beea21348a0794bd3ce02ea85cb537ff8efe7e63bad70bc7773d7bbe4e484315`,
`signal_detectors.py` SHA-256
`b4780c08ef9e3b97e852b759593bb8ffb34c89b9264054d3cf2865309e22a429`).
Filtered observations were identical on repeat, and each pair of full JSON
reports was byte-identical:

| Fixture                           | `PP-001`            | `RS-001`                | `DO-DET`                              |
| --------------------------------- | ------------------- | ----------------------- | ------------------------------------- |
| `fault.kicad_sch`                 | `U1.1` on `LOCAL_A` | `LOCAL_A` has no source | none                                  |
| `control.kicad_sch`               | none                | `+3V3` has no source    | capacitor coverage for `C1`           |
| `source-backed-no-cap.kicad_sch`  | none                | none                    | missing-cap prompts for `U1` and `U2` |
| `source-backed-control.kicad_sch` | none                | none                    | capacitor coverage for `C1`           |

The name-only control shows that `PP-001` itself does not report a missing
source when the rail is named `+3V3`; the analyzer's separate `RS-001` does
report it. On the source-backed pair, `PP-001` adds no observation and does
not distinguish capacitor presence. `DO-DET` does distinguish it, including
a prompt for source component `U2`; this broad applicability is not evidence
that `U2` needs a capacitor. The local LINT-046 prompt remains the bounded
review signal for this case. This is a parser-only cohort run; the native ERC
and local-lint comparisons are recorded separately above and below.

Candidate report SHA-256 values for the first run were
`2aa9755a58fd66b3ad171b5ef6769246d494104761808ef2bb790e903dab62cc` (`fault`),
`4aa2bcc531762f2163f46994766bf2cd97be7d6db296fca0fb82c5e0e19ebfae` (`control`),
`3287e90d8451e76d0e9951642ff2a9caa06426dc55cb3271236d35ba007beb4e` (`source-backed-no-cap`), and
`f76d83a1ca452d215bbe53996865b80522f9d361e40e0f0a1a88d38b46b01108` (`source-backed-control`).
Outputs stayed under `/private/tmp` and were not copied into the repository.

## kicad_skills `analog.missing_decoupling` trial

The `sabas0ba/kicad_skills` package at commit
`53d1af8bc550f60415b4b8e51a6d2d5924ada03f` was installed into an isolated
temporary Python 3.11 environment with `--no-build-isolation --no-deps`. The
trial used `python -I -m eda_toolkit.cli sch review --no-cli --json --output
<report> <fixture>`; this exercises the candidate's geometry fallback, not its
documented Docker wrapper, KiCad CLI export, or native ERC. Reports were
repeated at the same paths and were byte-identical. The no-cap cases exited 2
because the candidate also emitted an unrelated `power.no_ground` error; their
JSON still contained the targeted decoupling finding. Candidate source and all
reports remained outside the repository.

| Fixture                                 | `analog.missing_decoupling` result | CLI exit | Report SHA-256                                                     |
| --------------------------------------- | ---------------------------------- | -------- | ------------------------------------------------------------------ |
| `no-cap.kicad_sch`                      | U1 / `+3V3`                        | 2        | `f40ca6ee3c9c1dc35af3becd10c3234664725f427c9f2623399f6c8c924b19c6` |
| `control.kicad_sch`                     | none                               | 0        | `c0604e94d6bda0c230b7283c64a7e174559317ad583b297493a65a4949f4e21f` |
| `fault.kicad_sch`                       | none                               | 0        | `89ef835afa98afd78281a1625dbadf3813739b62c5de137f86b382b2eeb69f8a` |
| `source-backed-no-cap.kicad_sch`        | U1 / `+3V3`                        | 2        | `6dcd9b05db4e8b69cf3b298618879d2496b039388bdac235b0020a318a4ef988` |
| `source-backed-control.kicad_sch`       | none                               | 0        | `5d9727481ff0f8cbef3795de5ed9cb635d43f56c338d09beb3caa2b46d30cf07` |
| `source-backed-dnp-capacitor.kicad_sch` | none                               | 0        | `a12dd491b49e8aa02d6210bc210d557949a300ed17a1347f357a0c8682c0f89b` |

The two fitted no-cap inputs duplicate LINT-046's review; the capacitor-bearing
controls are quiet. On the DNP case, the candidate treats the `C1` reference
prefix as sufficient evidence of a decoupler and emits no finding. The native
Tooling lane below confirms that KiCad retains the DNP state and that LINT-046
still asks for review. This is a synthetic missed-population case for the
candidate predicate, not proof that a particular product requires a capacitor.

## Native Tooling regression

The six Tooling-owned fixtures are exported twice with the digest-pinned
KiCad 10.0.0 and 10.0.5 images. The regression asserts each source hash,
normalized parsed-netlist and ERC repeatability, and these outcomes:

| Fixture                                 | Native netlist / ERC expectation                                                                                                       | LINT-046 expectation                         | LINT-056 source-anchor/path expectation      |
| --------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------- | -------------------------------------------- |
| `no-cap.kicad_sch`                      | `U1.1` has native `power_in` type on `+3V3`; no rail source. ERC reports `power_pin_not_driven`.                                       | One default-review prompt for `+3V3`         | No prompt; no fitted capacitor-to-return     |
| `control.kicad_sch`                     | Fitted `C1` connects `+3V3` to `GND`, but no source is shown. ERC reports `power_pin_not_driven`; this is only a name-branch control.  | No prompt                                    | No prompt; recognized rail name is an anchor |
| `fault.kicad_sch`                       | `U1.1` is on unrecognized `LOCAL_A`; `C1` connects it to `GND`. ERC reports `power_pin_not_driven`.                                    | No prompt because the rail is not recognized | Source-anchor coverage REVIEW for `LOCAL_A`  |
| `source-backed-control.kicad_sch`       | `U1.1`, `U2.1` (`power_out`), and `C1.1` share `+3V3`. ERC has no `power_pin_not_driven` violation.                                    | No prompt                                    | No prompt; fitted `power_out` is an anchor   |
| `source-backed-no-cap.kicad_sch`        | `U1.1` and `U2.1` (`power_out`) share `+3V3`; no capacitor is present. ERC has no power-source error or capacitor-presence diagnostic. | One default-review prompt for `+3V3`         | No prompt; no fitted capacitor-to-return     |
| `source-backed-dnp-capacitor.kicad_sch` | `U1.1`, `U2.1`, and DNP `C1.1` share `+3V3`; native netlist preserves DNP state; no `power_pin_not_driven`.                            | One default-review prompt for `+3V3`         | No prompt; fitted `power_out` is an anchor   |

The source-backed no-cap and DNP-capacitor cases demonstrate additional review coverage over
native ERC for the narrow question “is a fitted capacitor symbol connected
from this recognized rail to a recognized return?” It does not establish that
a capacitor is required, correctly valued, placed, or physically effective.
The DNP fixture retains `C1.1` and `C1.2` assignments in the native netlist but
marks `C1` unpopulated. Its normalized netlist hash is
`be117c727859ab1794f1dbceaefbf383332b95ffa39377733c469a4a425fd5dd` on both
KiCad versions. The normalized ERC hashes are
`0f6cd81be9b01c2881cfe6dd20ff153a441df85ca366bab9a10fb7491e845d90` for
KiCad 10.0.0 and
`1dc9beb6f7751346d643dd91f2059c35e7059cee10c644cb22c6328a8daabc99` for
KiCad 10.0.5. Repeated exports match within each version.

LINT-056's prompt on `fault.kicad_sch` is a source-anchor coverage review, not
an additional defect detection: native ERC already reports
`power_pin_not_driven`. The review finding adds the unrecognized source-anchor
state and the exact `LOCAL_A` input pin/capacitor evidence. Both review and ERC
results are retained independently.

The native profiles are digest-pinned:

| KiCad version | Image                                                                                                |
| ------------- | ---------------------------------------------------------------------------------------------------- |
| 10.0.0        | `ghcr.io/kicad/kicad:10.0.0@sha256:9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3` |
| 10.0.5        | `ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c` |

Run the gated lane with a local checkout of the tooling-only KiCad template
repository (it supplies the pinned project profiles used by the hosted native
lane):

```sh
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test \
KICAD_RUN_NATIVE_IC_RAIL_CAPACITOR_FIXTURES=1 \
.venv/bin/python -B -m unittest tests.test_ci_hosted.NativeIcRailCapacitorFixtureTests
```

The container runs with networking disabled, a read-only root filesystem, a
read-only fixture mount, and an isolated writable output mount. Receipts stay
under ignored `build/ci/`. The lane checks native schematic-to-netlist export,
normalized ERC-repeatability, and lint determinism. It checks the specific
`power_pin_not_driven` result; unrelated library-table and isolated-label
warnings in these minimal synthetic schematics are not treated as power-source
evidence. These tests do not establish capacitor need, value, placement,
current, PCB connectivity, or physical return performance.
ERC JSON includes a generation date, so repeatability compares the pinned KiCad
version and normalized violation types, severities, descriptions, and item
positions rather than the raw report bytes.

The cohort's `PP-001` source describes its DC-path rule as heuristic while
emitting error severity. Tooling did not adopt that severity or the separate
missing-source assertion. Controls for external connectors, regulators,
ferrites, fuses, jumpers, DNP parts, and internal rails remain open for the
broader power-source-path concept.
