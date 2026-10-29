# Alphus quality checks

The development extra pins Alphus to the revision in `pyproject.toml`.
`quality-gates.toml` scopes runtime-types and Pydantic practices checks to Python
production and script files. The package CI job runs each in report mode: findings are
advisory, while an invalid policy or tool failure still fails the step.
The `python-style` check uses the same scope and is available on demand; it is
not included in CI while its broader guidance is being reviewed.

Run the same advisory check locally from this checkout:

```sh
python -I -m alphus --rule runtime-types --report
python -I -m alphus --rule pydantic-practices --report
python -I -m alphus --rule python-style --report --json
```

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

The `python-style` JSON output groups findings by file and category. For
example, this command prints only opaque mapping locations:

```sh
python -I -m alphus --rule python-style --report --json | python -c 'import json,sys; d=json.load(sys.stdin); print("\n".join(f"{p}:{n}" for p, v in d.items() for n in v["opaque_mappings"]))'
```

An opaque mapping can be an intentional external boundary. Review the data
owner and intended contract before converting it or adding a boundary marker.

For a common finding format, `--profile python-style --json` and
`--profile pydantic-practices --json` include `steps[].findings[]` with a
`rule_id`, path, line, severity, and message, plus `finding_rollups`. Rule IDs
identify the language, framework, category, and complaint; for example,
`alphus/python/pydantic/validation/dump-revalidation`. The Python-style
profile may exit nonzero when it reports findings. Review its JSON and exit
status separately; a successful Pydantic profile may still contain warnings.
