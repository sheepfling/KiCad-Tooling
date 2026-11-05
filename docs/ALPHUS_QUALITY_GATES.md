# Alphus quality checks

The optional `dev-experimental` extra pins Alphus to the `v0.0.2` tag commit
in `pyproject.toml`. The standard `dev` extra does not install it. CI explicitly
opts in because the package and prerelease jobs run its advisory checks and
regressions.
`quality-gates.toml` scopes runtime-types and Pydantic practices checks to Python
production and script files. The package CI job runs each in report mode: findings are
advisory, while an invalid policy or tool failure still fails the step.
The `python-style` check uses the same scope and is available on demand; it is
not included in CI while its broader guidance is being reviewed. The new
`input-contracts` and `complexity-candidates` profiles are also on-demand,
provisional review profiles and are not CI blockers. `test-quality` is a
provisional profile scoped to `tests/**/*.py`; the package job runs that
selector in report mode so findings do not block CI.

The installed package metadata and `dev-experimental` pin both resolve to
Alphus `v0.0.2` commit `3435f81aff7abac7716a5780d26319e8f314d61d`. A fresh
re-sniff at KiCad head `2dd91707624d23e8d83405e8df57326701dd0e1a` reports 116
runtime-type findings, 220 Python-style findings, one Pydantic warning, 37
source-family candidates, four input-mutation candidates, and 30 complexity
candidates. These are consumer review findings; they are not proof of defects.
The Python-style scan still reports zero opaque mappings.

Run the same advisory check locally from this checkout:

```sh
python -m pip install -e '.[dev,dev-experimental]'
python -I -m alphus --rule runtime-types --report
python -I -m alphus --rule pydantic-practices --report
python -I -m alphus --rule python-style --report --json
python -I -m alphus --profile input-contracts --json
python -I -m alphus --profile complexity-candidates --json
python -I -m alphus --rule test-quality --report
```

Select only the experimental regression tests with
`python -I -m pytest -m alphus_experimental`.

For a structured profile result, run `python -I -m alphus --profile
runtime-types --json`. The profile returns a failing exit code when it finds
violations, so it is diagnostic rather than a blocking CI gate. The check is
not a substitute for Pyright or the architecture tests. The review-only
posture can change after findings are resolved or their guidance is corrected.
The Pydantic profile is independently selectable as `pydantic-practices`; its
findings include informational and warning severities, so its profile exit code
alone does not indicate that its report is empty. `Field(default_factory=...)`
is a supported way to create per-instance mutable defaults; review contextual
guidance before changing it.

The `python-style` profile also uses the default `error` failure threshold. In
v0.0.2, some categories such as opaque mappings are warnings, so a warning-only
profile passes even when it contains findings. Inspect `severity_counts` and
the individual findings instead of treating a successful exit as an empty
report.

The `python-style` JSON output groups findings by file and category. For
example, this command prints only opaque mapping locations:

```sh
python -I -m alphus --rule python-style --report --json | python -c 'import json,sys; d=json.load(sys.stdin); print("\n".join(f"{p}:{n}" for p, v in d.items() for n in v["opaque_mappings"]))'
```

An opaque mapping can be an intentional external boundary. Review the data
owner and intended contract before converting it or adding a boundary marker.

## Architecture candidate scan

Alphus `v0.0.2` adds the `source-families` selector. The
`architecture-candidates` profile scopes it to `kicad_tooling/hwrepo/` and
enables bounded direct Python import evidence. It groups similarly named
siblings for architecture review; the groups are inventory prompts, not
instructions to split or move modules. The scan does not establish ownership,
coupling, or a public contract.

At source revision `2dd91707624d23e8d83405e8df57326701dd0e1a`, it reported 37
groups, including `design_lint_*` (101 files), `component_*` (27), and
`connector_*` (23). Inspect those candidates against the capability and
data-route map before proposing module moves.

Run the current candidate inventory with:

```sh
python -I -m alphus --profile architecture-candidates --json
```

The `complexity-candidates` profile runs the pinned Ruff C901 check at maximum
30 over `kicad_tooling/hwrepo/`. At KiCad head
`2dd91707624d23e8d83405e8df57326701dd0e1a`, the current scan reports 30
warning-level functions; review these as function-level refactoring candidates
rather than line-count limits. The profile is provisional and remains outside
CI while the service and data routes are being established.

The `input-contracts` profile reviews Python input mutation and read-only
contracts. At the same head, the scan reports four possible caller-visible
mutations in two functions. These findings can describe intentional mutable
contracts, so review ownership and callers before changing an annotation or
implementation.

`source-test-coverage` remains deferred until the repository has an explicit
source-to-test map and revision-matched execution evidence. `module-roles` and
`package-boundaries` also need the capability-owner and package-layer map before
their policy can distinguish intended routes from violations.
The `file-size` gate remains disabled while the architecture plan prioritizes
data ownership and routing decisions over line-count thresholds. No newly
available architecture gate currently has enough consumer-owned context to add
as a blocker; keep `source-families` as the advisory inventory and revisit the
other selectors after the route map is explicit.

For a common finding format, `--profile python-style --json` and
`--profile pydantic-practices --json` include `steps[].findings[]` with a
`rule_id`, path, line, severity, and message, plus `finding_rollups`. Rule IDs
identify the language, framework, category, and complaint; for example,
`alphus/python/pydantic/validation/dump-revalidation`. The Python-style
profile may exit nonzero when it reports findings. Review its JSON and exit
status separately; a successful Pydantic profile may still contain warnings.

The provisional `test-quality` rule checks large exact prose comparisons and,
when configured, reads of declared ephemeral documents. Its synthetic
fault/control regression confirms that it reports a prose golden, accepts a
structured mapping comparison, ignores same-content production files outside
the configured test paths, and produces repeatable JSON. It does not enforce
test-file size or pytest marker coverage. The repository architecture suite
and lint-suite ceilings own those checks.

## Test-quality profile and current re-sniff (2026-11-05)

The optional Alphus package is pinned and installed from tag `v0.0.2`, commit
`3435f81aff7abac7716a5780d26319e8f314d61d`. The installed distribution's VCS
metadata matches the dependency pin and tag. The catalog lists 62 built-in
selectors.

This re-sniff ran at KiCad head
`dab210cbe6353022089f1329f96e090fb35bb208`, which contains the case-folded USB
index and immutable resistor-path changes.

The configured file inventory now includes `tests/**/*.py` for the test-quality
profile. The runtime-types, Python-style, Pydantic-practices, and input-contracts
checks explicitly exclude tests, preserving their production scope. The
test-quality profile is provisional, selects only Python tests, and currently
reports zero findings. CI invokes its direct selector with `--report`.

The focused Alphus experimental suites passed 7 tests, including the regression
in `tests/test_alphus_test_quality_policy.py`. Its synthetic fault produces one
warning for a full-paragraph exact assertion; a structured mapping control stays
quiet, a matching production file is outside the configured test scope, and two
direct-rule report runs are byte-identical. The configured profile reports the
same warning at the advisory warning severity and exits successfully under its
error threshold. The test-quality selector reported no findings on the current
repository after adding this coverage. Ruff, formatting, and targeted Pyright
passed for the new suite.

This selector does not check test-module size or pytest marker coverage. Those
remain deterministic repository architecture checks, including the explicit
lint-suite ceilings.

The six existing profile totals remain 116 runtime-type errors, 220
Python-style errors (including zero opaque-mapping findings), one Pydantic
warning, 37 source-family candidates, four input-contract candidates, and 30
complexity candidates. The two error-level profiles still exit nonzero outside
report mode; this run is diagnostic and did not change those policies.

The separately scoped 1,500-line `file-size` candidate reports no oversized
modules in `kicad_tooling/hwrepo/`; the selector remains disabled while source
ownership and routes are being decided. `module-roles`, `package-boundaries`,
and `source-test-coverage` also remain deferred until their respective
ownership, package-layer, and source-to-test maps exist.

Raw profile and catalog JSON for this scan are stored in the external feedback
bundle under
`build/alphus-v0.0.2/sa01-typed-map-test-quality-gate-2026-11-05/`.
