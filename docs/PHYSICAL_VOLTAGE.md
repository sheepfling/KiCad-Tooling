# Review a measured voltage envelope

Import a project-owned voltage CSV with `kicad-team measured-series` first.
The physical voltage review reads that saved receipt and two project-owned JSON
records: capture context and an optional authored requirement. It never creates
or edits either project record.

The capture record names the exact CSV path and SHA-256 from the measured-series
receipt. Its channel must be one of the imported CSV headers. For example:

```json
{
  "schema_version": "1",
  "kind": "voltage_envelope",
  "project_id": "controller",
  "test_id": "supply-startup",
  "source_csv": "examples/projects/controller/docs/startup.csv",
  "source_sha256": "<64-character SHA-256 of startup.csv>",
  "channel": "vout",
  "unit": "V",
  "conditions": {"load": "100 mA", "ambient": "25 C"},
  "captured_at": "2026-10-30T10:00:00Z",
  "instrument": "Bench scope asset 42",
  "recorded_origin": "bench"
}
```

An authored requirement can set a lower bound, an upper bound, or both:

```json
{
  "schema_version": "1",
  "kind": "voltage_envelope",
  "project_id": "controller",
  "test_id": "supply-startup",
  "channel": "vout",
  "unit": "V",
  "conditions": {"load": "100 mA", "ambient": "25 C"},
  "limit": {"minimum_v": "4.75", "maximum_v": "5.25"},
  "basis": "Project-owned test requirement"
}
```

Both records must be regular, non-executable JSON files in the selected project
island. The CLI selects exact inputs and writes a fresh ignored build receipt:

```sh
kicad-team physical-voltage --root /path/to/project-checkout \
  --project controller \
  --measured-receipt build/measured-series/run-1/measured-series.json \
  --capture examples/projects/controller/docs/startup-capture.json \
  --requirement examples/projects/controller/docs/startup-limit.json \
  --format json
```

MCP `export_physical_voltage_review` uses the same service and accepts
`project_id`, `view_id`, `measured_receipt`, `capture`, and optional
`requirement` when exports are enabled. Open `index.html` in the returned
directory for the offline plot, condition table, source identity, issues, and
links to copied evidence. `physical-voltage.json` is the structured review.

The limit comparison runs only when the selected receipt and live source are
current, the channel exists, the capture and requirement both declare `V`,
the test and channel identities match, and the condition maps match exactly.
Every retained sample is compared with exact decimal values; equality at a
bound passes. A missing or invalid requirement, unit or condition mismatch,
unsupported kind, and stale source are reported separately. The plot uses
display coordinates only; values in the report and retained CSV remain exact.

The capture context records a project's claim about its origin and conditions.
This review does not verify the instrument, physical origin, procedure, safety,
thermal or signal-integrity behavior, or release approval.
