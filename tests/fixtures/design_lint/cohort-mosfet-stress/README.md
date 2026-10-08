# Synthetic MOSFET operating-state stress cohort trial

These schematics and state manifests are synthetic Tooling-owned fixtures.
They contain no proprietary design source, part data, or board information.

## Fixtures

`mosfet.kicad_sch` contains synthetic Q1 with D/G/S pins, `Vds_max=60 V`,
`Vgs_max=20 V`, and a synthetic rating citation. The manifests declare scalar,
steady-state net potentials. They do not model tolerance, uncertainty, ripple,
switching transients, or waveforms.

| Input                        | Purpose                                                 |
| ---------------------------- | ------------------------------------------------------- |
| `control.json`               | `off` at 0 V; `on` at D=48 V, G=10 V, S=0 V             |
| `fault.json`                 | `on` at D=80 V and G=25 V to exceed both limits         |
| `boundary.json`              | `on` at D=60 V and G=20 V, exactly at both limits       |
| `missing-state.json`         | Requires `off` and `on` but declares only `off`         |
| `missing-potential.json`     | Omits the `on`-state D potential                        |
| `mosfet-dnp.kicad_sch`       | Marks Q1 DNP while retaining the control state manifest |
| `mosfet-wrong-mpn.kicad_sch` | Changes Q1's MPN while retaining its ratings and wiring |

Fixture SHA-256 values:

| File                         | SHA-256                                                            |
| ---------------------------- | ------------------------------------------------------------------ |
| `mosfet.kicad_sch`           | `e03ef9d41fd5ac132245b253da58a015ebafa6ee0a6fb71a74e6738085c8e994` |
| `mosfet-dnp.kicad_sch`       | `7d43b696e63e572e675c4c1e479394efa05905a7cb7a2c291ae5d7c5bf455323` |
| `mosfet-wrong-mpn.kicad_sch` | `3012b20b0726e3fbaaa0a05c45fd1fb00c14820b6e58e0396b04d161cbcef459` |
| `control.json`               | `ae29bd0b98634f823edcf60ab23ab02339df290711c32166fa032fb85ec41d80` |
| `fault.json`                 | `0663aa9ab35e271d642000533cd61a8b62583b226dc992abfdca68d87a91c3c1` |
| `boundary.json`              | `dae188321f477ab1ce71bcfde7f4d8df19fcec7799e4c3adf5dd634c9729625e` |
| `missing-state.json`         | `3f924151525d7e73baba8022d0f214d3fdd2077ac52e12b7cdcad20cb82c3e97` |
| `missing-potential.json`     | `46a50e9211f1b69352d8a744dfea780d98fb8612213527da1326e5c6028087d9` |

## Candidate and installation

The read-only trial used `kicad-tools==0.21.1`, declared MIT-licensed and Python 3.10+ by its
[project metadata](https://github.com/rjwalters/kicad-tools/blob/main/pyproject.toml). The upstream
README documents the standard `pip install kicad-tools` flow
([README](https://github.com/rjwalters/kicad-tools/blob/main/README.md)). The trial used Python
3.11.16 in a disposable virtual environment under `/private/tmp`; pip installed the 18-package
set in [`requirements-kicad-tools-0.21.1.lock`](requirements-kicad-tools-0.21.1.lock). No optional
native C++ backend was needed for this analysis command, and no runtime dependency was added to
the tooling package.

The tested package's `kicad_tools` Python-source tree contained 854 files and
had SHA-256
`9179ca04e7a3f739b6b4b6ba15ebaa0a7c8cc7ad2abacf6cd2d235fe865cea85` using a
sorted relative-path, NUL, file-bytes, NUL digest. The environment's `pip
freeze`, command help, version, report outputs, and exit codes are retained
under the ignored `build/cohort-trials/kicad-tools-0.21.1/` directory in this
checkout.

The feature is not listed in the upstream README or published
[CLI reference](https://github.com/rjwalters/kicad-tools/blob/main/docs/reference/cli.md).
The installed 0.21.1 command's `kct analyze --help` and
`kct analyze component-stress --help` do expose it. This documentation gap did
not prevent the basic pip install, but it makes the command harder to discover.

Reproduce the installation in a disposable environment, then run from the
repository root:

```sh
python3.11 -m venv /tmp/kicad-tools-0.21.1
/tmp/kicad-tools-0.21.1/bin/python -m pip install --no-cache-dir -r tests/fixtures/design_lint/cohort-mosfet-stress/requirements-kicad-tools-0.21.1.lock
KCT=/tmp/kicad-tools-0.21.1/bin/kct
FIXTURE=tests/fixtures/design_lint/cohort-mosfet-stress
OUT=build/cohort-trials/kicad-tools-0.21.1
KICAD=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
mkdir -p "$OUT"
"$KCT" analyze component-stress "$FIXTURE/mosfet.kicad_sch" --states "$FIXTURE/control.json" --format json > "$OUT/control.json"
"$KCT" analyze component-stress "$FIXTURE/mosfet.kicad_sch" --states "$FIXTURE/control.json" --format json > "$OUT/control-repeat.json"
"$KCT" analyze component-stress "$FIXTURE/mosfet.kicad_sch" --states "$FIXTURE/fault.json" --format json > "$OUT/fault.json"; test "$?" -eq 1
"$KCT" analyze component-stress "$FIXTURE/mosfet.kicad_sch" --states "$FIXTURE/fault.json" --format json > "$OUT/fault-repeat.json"; test "$?" -eq 1
"$KCT" analyze component-stress "$FIXTURE/mosfet.kicad_sch" --states "$FIXTURE/boundary.json" --format json > "$OUT/boundary.json"
"$KCT" analyze component-stress "$FIXTURE/mosfet.kicad_sch" --states "$FIXTURE/missing-state.json" --format json > "$OUT/missing-state.json"; test "$?" -eq 1
"$KCT" analyze component-stress "$FIXTURE/mosfet.kicad_sch" --states "$FIXTURE/missing-potential.json" --format json > "$OUT/missing-potential.json"; test "$?" -eq 1
"$KCT" analyze component-stress "$FIXTURE/mosfet-dnp.kicad_sch" --states "$FIXTURE/control.json" --format json > "$OUT/dnp-control.json"
"$KCT" analyze component-stress "$FIXTURE/mosfet-wrong-mpn.kicad_sch" --states "$FIXTURE/control.json" --format json > "$OUT/wrong-mpn.json"
"$KICAD" version
"$KICAD" sch erc --format json --severity-all --output "$OUT/erc-kicad-10.0.6.json" "$FIXTURE/mosfet.kicad_sch"
"$KICAD" sch erc --format json --severity-all --output "$OUT/erc-kicad-10.0.6-repeat.json" "$FIXTURE/mosfet.kicad_sch"
```

The failing invocations return status 1 because the upstream CLI gates on
`FAIL` or unresolved rows by default. Its report describes the analysis as
advisory, so a local implementation must set its own REVIEW/BLOCK/OFF policy
and must not inherit this exit behavior blindly.

## Results

| Case                   | Result                                                              | CLI status | Report SHA-256                                                                      |
| ---------------------- | ------------------------------------------------------------------- | ---------: | ----------------------------------------------------------------------------------- |
| Control                | Four checks PASS across `off` and `on`                              |          0 | `40c7cd30d457678b8818fda09ca54830ab16775afef65b72337f9774bb42f9fa`                  |
| Over-stress            | `on/vds` is 80/60 V and `on/vgs` is 25/20 V; both FAIL              |          1 | `f2610c15e39414fcd1fd43a4f9e3e4e47e0ea2845ce45f204076287fe452870e`                  |
| Exact limits           | Both checks at 60/60 V and 20/20 V PASS                             |          0 | `e756ed13a3d775b72f530bc0f8a8d361745541258071c283e978bdb9bcd9c921`                  |
| Missing required state | Both `on` checks are UNRESOLVED; `missing_states` names `on`        |          1 | `27d6c8afd81b22cad05f4aaaa034c5831b7ab3dfcfcda09b7eb74e4e39044be9`                  |
| Missing D potential    | `on/vds` is UNRESOLVED; `on/vgs` still PASSes                       |          1 | `aeda802e7e8dc1ee91ff848333e2b186552d5fd7de5c67f2e4e20c9a00b36828`                  |
| DNP component          | All four checks PASS; the candidate still evaluates Q1              |          0 | Same as control: `40c7cd30d457678b8818fda09ca54830ab16775afef65b72337f9774bb42f9fa` |
| Changed MPN            | All four checks PASS; no expected project part identity is compared |          0 | `923672b103fead2cebc20804a005d23c1b3bfd55440dfa0d114c95474b5813d6`                  |

Repeated control reports were byte-identical at SHA-256
`40c7cd30d457678b8818fda09ca54830ab16775afef65b72337f9774bb42f9fa`;
repeated fault reports were byte-identical at
`f2610c15e39414fcd1fd43a4f9e3e4e47e0ea2845ce45f204076287fe452870e`.
The reports localize each result to Q1, a named state, VDS or VGS, the two
terminal nets and potentials, computed stress, rating, and remaining margin.

## Comparison and disposition

The KiCad CLI resolved from this checkout's configured macOS installation
reported version 10.0.6. It ran ERC twice against the retained schematic
(SHA-256 `e03ef9d41fd5ac132245b253da58a015ebafa6ee0a6fb71a74e6738085c8e994`).
Each report has ten findings: one undriven synthetic gate input, isolated
labels, off-grid endpoints, and absent synthetic library warnings. The
normalized ERC reports match at SHA-256
`bf45b9f09d1e78c484e5c15db1e71bef25e4d49418924de0a2ed4e00d1d5258d` after
parsing JSON, removing only the top-level `date`, and serializing with sorted
keys and compact separators; raw report hashes are
`5516e90faf7f790b7d9dc1cf432d05b3b353a40682eac254fd9dc7cbbb80d734` and
`d22079abbf6766e47ca1e98b60dd628a187de124dedd9c8ebbcc3d18c88b11f9`. Reports
are retained under the ignored `build/cohort-trials/kicad-tools-0.21.1/`
directory. This deliberately sparse fixture is not a clean native baseline.
ERC also sees the same schematic for each state manifest and cannot evaluate
the authored operating-state values.

LINT-064 compares a project-authored maximum voltage stress with an exact
part's sourced rating and utilization limit, but its schema requires an exact
two-pin component inventory and permits only one requirement per component. It
cannot directly express both D-S and G-S stress for this three-pin MOSFET.
LINT-064 therefore was not run head-to-head: it cannot represent the same
requirement. The cohort trial identifies a candidate capability gap in
multi-terminal, per-state coverage, but does not measure local review effort or
the additional defect detection a new contract would provide.

The trial used scalar potentials only. It does not establish behavior for
duplicate states, incorrect pin roles or pin/net maps, input-order
metamorphics, or multiple devices. DNP evaluation and exact expected-part
identity are confirmed candidate gaps, so the cohort analyzer remains deferred.
LINT-073 now implements a local project-authored contract with exact native
three-pin identity, DNP handling, authored potential intervals, required-state
coverage, and source-bound electrical evidence. See the separate
[tooling-owned synthetic fixture record](../mosfet-stress/README.md). No proprietary
project source or fixture was used, and no candidate code was copied.
