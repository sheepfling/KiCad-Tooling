# Import measured time series

Install the optional chart dependency and place a UTF-8 CSV inside the selected
project island. Select the exact header used for time and declare its input
format: `s`, `ms`, `us`, `ns`, or `iso8601`. ISO 8601 timestamps need a UTC offset.
Declare each plotted channel as `COLUMN=UNIT`; up to eight channels are accepted.

```sh
python -m pip install -e '.[charts]'
kicad-team measured-series --root /path/to/project-checkout \
  --project controller \
  --source examples/projects/controller/docs/measurement.csv \
  --time-column timestamp --time-unit iso8601 \
  --channel voltage=V --channel current=A --format json
```

The importer accepts one CSV up to 8 MiB and 100,000 strictly ordered samples.
It writes a fresh ignored `build/measured-series/` receipt containing the
original `source.csv`, a `data.csv` with full precision seconds and channel
values, a PNG and SVG plot, and `measured-series.json`. The report records the
selected columns and units, source path and SHA-256, artifact hashes, sample
count, and any parse or plot error. A malformed file still gets a failure
receipt with the original bytes. Source paths must belong to the selected
project island and cannot be linked, executable, hidden, or generated files.

MCP `import_measured_time_series` uses the same mappings and service when
exports are enabled; `channels` is an array of `COLUMN=UNIT` strings. Its
`view_id` names a fresh receipt. The plot uses elapsed seconds, grouping
channels by the declared unit, while the retained CSV keeps absolute seconds
(UTC seconds for ISO 8601 input). `source.csv` preserves every original byte;
`data.csv` retains exact decimal channel values and converted time. The plot
uses floating-point coordinates only for display.

## Compare two saved runs

Select two successful receipts for the same project and one exact channel name.
Declare whether their timestamps should be shown as absolute seconds or elapsed
seconds from each run's first sample:

```sh
kicad-team measured-comparison --root /path/to/project-checkout \
  --project controller \
  --baseline build/measured-series/baseline/measured-series.json \
  --candidate build/measured-series/candidate/measured-series.json \
  --channel voltage --alignment elapsed --format json
```

MCP `compare_measured_runs` takes `project_id`, `baseline`, `candidate`,
`channel`, `alignment`, and a fresh `view_id` when exports are enabled. The
shared service verifies both saved reports, all recorded measurement artifacts,
sample counts, and exact channel units before plotting. A changed or missing
project source is labeled historical; the saved source CSV remains hash-checked.
The offline page overlays both traces, lets reviewers show or hide a run, and
reports the nearest displayed values on hover. It retains both full original
CSVs. For large runs, the display preserves endpoints and per-bucket extrema;
the saved CSVs remain the full-precision evidence. It shows whether the selected
time windows overlap and does not interpolate, infer matching test conditions,
or apply acceptance limits.

The importer and comparison do not establish that data came from physical
hardware. Record capture conditions in project source when they matter for
review. Numerical differences and cross-run acceptance decisions need an
explicit, project-authored comparison contract.
