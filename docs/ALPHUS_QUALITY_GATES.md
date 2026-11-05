# Alphus quality checks

The optional `dev-experimental` extra pins Alphus to the `v0.0.2` tag commit
in `pyproject.toml`. The standard `dev` extra does not install it. CI explicitly
opts in because the package and prerelease jobs run its advisory checks and
regressions.
`quality-gates.toml` scopes runtime-types and Pydantic practices checks to Python
production and script files. The package CI job runs each in report mode: findings are
advisory, while an invalid policy or tool failure still fails the step.
The `python-style` check uses the same scope and is available on demand; it is
not included in CI while its broader guidance is being reviewed.

Run the same advisory check locally from this checkout:

```sh
python -m pip install -e '.[dev,dev-experimental]'
python -I -m alphus --rule runtime-types --report
python -I -m alphus --rule pydantic-practices --report
python -I -m alphus --rule python-style --report --json
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

Run the current candidate inventory with:

```sh
python -I -m alphus --profile architecture-candidates --json
```

The other new gate that appears relevant is `cyclomatic-complexity`. A trial
using Ruff C901 at maximum 20 reported 83 functions across 855 selected
`hwrepo` modules; maximum 30 still reported 30. It remains a calibration item
instead of joining this profile or CI while we establish the service and data
routes. `source-test-coverage` is another new candidate, but it requires an
explicit source-to-test map and revision-matched execution evidence; revisit it
after those routes are documented.

For a common finding format, `--profile python-style --json` and
`--profile pydantic-practices --json` include `steps[].findings[]` with a
`rule_id`, path, line, severity, and message, plus `finding_rollups`. Rule IDs
identify the language, framework, category, and complaint; for example,
`alphus/python/pydantic/validation/dump-revalidation`. The Python-style
profile may exit nonzero when it reports findings. Review its JSON and exit
status separately; a successful Pydantic profile may still contain warnings.
