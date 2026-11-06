# Alphus quality checks

Alphus is an optional development tool. The `dev` extra in `pyproject.toml`
pins tag `v0.0.2` at commit
`3435f81aff7abac7716a5780d26319e8f314d61d`; it is not a runtime dependency.
Consumer feedback, complaint IDs, and raw trial reports are maintained outside
this repository.

## Run configured profiles

Install the development extra, then run from this checkout:

```sh
python -m pip install -e '.[dev]'
python -I -m alphus --root . --config quality-gates.toml --profile runtime-types --json
python -I -m alphus --root . --config quality-gates.toml --profile python-style --json
python -I -m alphus --root . --config quality-gates.toml --profile pydantic-practices --json
python -I -m alphus --root . --config quality-gates.toml --profile module-role-boundaries --json
python -I -m alphus --root . --config quality-gates.toml --profile shared-utility-duplication --json
```

The policy also defines `architecture-candidates`, `input-contracts`,
`complexity-candidates`, `test-quality`, `module-role-boundaries`, and
`shared-utility-duplication`. Run the local review profiles by substituting the
profile name above.
`module-role-boundaries` is a mainline profile when invoked. It checks explicit
ownership contracts for cross-probe, design-lint candidate aggregation, and
governance lint: the coordinator may compose those stages but may not define
their registered implementation functions. This is a source-derived boundary
check, not an inferred or general-purpose God-file detector; it is independent
of physical line count. `shared-utility-duplication` is also mainline: it finds
repeated production Python helper bodies and file SHA-256 implementations.
Its scan excludes tests and scripts, and its canonical file hash owner is
`hwrepo/evidence.py`. `scripts/ci.py` invokes both mainline profiles in the
package and prerelease CI sequences. The
`alphus_experimental` pytest marker selects the small policy integration tests:

```sh
python -I -m pytest -m alphus_experimental
```

## Read results in context

The other configured profiles support local review and do not block CI.
`module-role-boundaries` and `shared-utility-duplication` are the explicit
exceptions. Inspect `severity_counts`, individual findings, and the configured
failure threshold. A profile can return exit code 1 because it found errors; a
zero exit code can still include warning findings when the threshold only
fails on errors. Review the owning contract and callers before changing source
or suppressing a finding.

Architecture candidates are prompts to compare against the capability and
data-route maps. The module-role profile checks only the named owner boundaries
configured here. A filename family or complexity result does not by itself
establish module ownership or a need to split a file. `file-size`,
`package-boundaries`, and `source-test-coverage` remain deferred until their
consumer contracts are defined.

## New selector review

Alphus `v0.0.3` was evaluated separately from the pinned development version.
It adds the `test-layout` selector. That check assumes source-mirrored test
paths, while this repository organizes suites around behavior; the selector
remains unconfigured. The evaluation and consumer feedback are recorded
outside this repository.

On 2026-11-06, the upstream refs were checked again. `main` remains at
`c880093f7ccb73c2af78ffb5c7de8c15d2b75b0e` with 62 built-in selectors, the
same catalog as `v0.0.2`. The latest release tag is `v0.0.3`, peeled to
`186323772564aab918a3519265b4043762f50200`; its 63rd selector is only
`test-layout`. That selector remains a poor fit for this repository's
behavior-organized suites. The `v0.0.3` commit and current `main` are parallel
commits from `v0.0.2`, so the current `main` does not include that selector.
`file-size`, `package-boundaries`, and `source-test-coverage` already exist in
the pinned catalog but remain deferred until their consumer-owned limits,
package-layer map, and revision-matched source/test evidence are ready. No new
selector or gate is ready to enable. Recheck the catalog before changing the
development pin.

## Cross-probe drawing-binding re-sniff (2026-11-06)

The installed Alphus package, `pyproject.toml`, and live `v0.0.2` tag resolve
to commit `3435f81aff7abac7716a5780d26319e8f314d61d`. A frozen scan covered
2,604 Python files across `kicad_tooling/`, `scripts/`, and `tests/`, with
inventory SHA-256 `fe56eddb9778bb576a6557b23e6ea651a81afdb241874291df5f2a28a079ab3f`
and policy SHA-256
`25876352db808b0e9f33e73a2dd81ff97d01469d5c685d700bb4e500e1b5c34f`.
All nine configured profiles ran against the same before/after inventory:

| Profile                      | Findings | Severity    | Exit |
| ---------------------------- | -------: | ----------- | ---: |
| `runtime-types`              |      116 | 116 errors  |    1 |
| `python-style`               |      226 | 226 errors  |    1 |
| `pydantic-practices`         |        4 | 4 warnings  |    0 |
| `architecture-candidates`    |       41 | 41 warnings |    0 |
| `input-contracts`            |        4 | 4 warnings  |    0 |
| `complexity-candidates`      |       28 | 28 warnings |    0 |
| `test-quality`               |        0 | none        |    0 |
| `module-role-boundaries`     |        0 | none        |    0 |
| `shared-utility-duplication` |        0 | none        |    0 |

The Python-style findings remain 139 legacy Pydantic field labels, 75 local
imports, 10 mutable module constants, and two unslotted dataclasses, with
zero opaque-mapping findings. The changed cross-probe drawing route had no
Alphus findings. This scan confirmed no new complaint; the existing consumer
feedback set remains in the external ledger.

The live `main` selector catalog has the same SHA-256 as pinned `v0.0.2` and
contains 62 selectors. `v0.0.3` has 63 and adds only `test-layout`, which
remains incompatible with behavior-organized test paths. The deferred
`package-boundaries` check describes distribution dependency edges, not the
internal capability layers in this architecture map. `source-test-coverage`
needs explicit source/test relationships and revision-matched execution
evidence from a clean tracked checkout. `file-size` supplies physical-line
limits rather than data-route or ownership evidence. No additional gate is
ready to enable. Raw reports and the selector comparison are under the ignored
`build/alphus-v0.0.2/resniff-2026-11-06-cross-probe-drawing-bindings/`.

## Named-variant position-export re-sniff (2026-11-06)

The development dependency remains pinned to the exact Alphus `v0.0.2` tag
commit `3435f81aff7abac7716a5780d26319e8f314d61d`; installed distribution
metadata and the live tag agree. All nine configured profiles were rerun
against a stable inventory of 2,616 Python files. Their counts match the prior
scan: `runtime-types` 116, `python-style` 226, `pydantic-practices` 4,
`architecture-candidates` 41, `input-contracts` 4, and
`complexity-candidates` 28. `test-quality`, `module-role-boundaries`, and
`shared-utility-duplication` remain at zero. No finding points to the new
position-export route, and the style report still has zero opaque-mapping
findings.

An isolated `v0.0.3` install adds only `test-layout` to the 62-selector
`v0.0.2` catalog. Its trial on the current behavior-organized test tree reports
1,137 errors: 946 unmirrored test directories and 191 misplaced test modules.
The selector remains disabled. `file-size`, `package-boundaries`, and
`source-test-coverage` also remain deferred until their consumer-owned
thresholds, layer map, and revision-matched source/test evidence are ready.
No new gate is ready to enable. The separate external Alphus feedback ledger
records the recurring tool pain points and this scan; it remains outside this
repository.

## Release board-variant selection re-sniff (2026-11-06)

The `dev` dependency still pins Alphus `v0.0.2` at
`3435f81aff7abac7716a5780d26319e8f314d61d`; installed metadata and the tag
agree. All nine configured profiles ran against a stable inventory of 2,621
Python files under `kicad_tooling/`, `scripts/`, and `tests/`. Before and after
inventory hashes match at
`c316d13692992dede5bf74bffe3f5cf12c7826ae0b02b36be933de71df359fc6`. The
policy SHA-256 remains
`25876352db808b0e9f33e73a2dd81ff97d01469d5c685d700bb4e500e1b5c34f`.

| Profile                      | Findings | Errors | Warnings | Exit |
| ---------------------------- | -------: | -----: | -------: | ---: |
| `runtime-types`              |      116 |    116 |        0 |    1 |
| `python-style`               |      226 |    226 |        0 |    1 |
| `pydantic-practices`         |        4 |      0 |        4 |    0 |
| `architecture-candidates`    |       41 |      0 |       41 |    0 |
| `input-contracts`            |        4 |      0 |        4 |    0 |
| `complexity-candidates`      |       28 |      0 |       28 |    0 |
| `test-quality`               |        0 |      0 |        0 |    0 |
| `module-role-boundaries`     |        0 |      0 |        0 |    0 |
| `shared-utility-duplication` |        0 |      0 |        0 |    0 |

The new route has no runtime-type, Python-style, Pydantic, input-contract, or
complexity finding; opaque-mapping findings remain zero. The existing
`architecture-candidates` count stays at 41. Its `release_*` advisory now
lists nine files, up from eight, because it groups the new 235-line resolver
with other release owners. This is additional evidence for APL-KT-003: a
filename-family count lacks the route, ownership, and cohesion context needed
to judge the group. It is not a new complaint or a line-split request.

The pinned catalog still has 62 selectors and no `test-layout` selector. The
live upstream `main` at
`c880093f7ccb73c2af78ffb5c7de8c15d2b75b0e` has the same 62 selector contracts
as `v0.0.2`; its catalog source hash is
`7920cfc31dd9ea5a14e4b8d8800899061d9f7fc6879d281c85e53a3bbcdd799e`. The
latest tag remains `v0.0.3`, which adds only `test-layout`; that selector
remains unsuitable for behavior-organized tests. The untagged
`release/v0.1.0` branch at `d25ded12d33a07858a34a784b9d9e73631dd249a` has 60
selector contracts, adds none over `main`, and removes `repeated-numeric-limits`
and `source-test-coverage`. No branch-only gate is ready for this consumer.
`file-size`, `package-boundaries`, and `source-test-coverage` remain deferred
until their route, ownership, and source/test evidence contracts are defined.
No new gate is ready to enable.
Raw profile reports, the catalog, upstream refs, and before/after inventories
are under the ignored
`build/alphus-v0.0.2/resniff-2026-11-06-release-board-variant-selection/`;
the external feedback bundle preserves the complaint ledger and route
evidence.
