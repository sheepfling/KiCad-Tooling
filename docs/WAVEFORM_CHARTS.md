# Review simulation waveforms

Install the optional `charts` extra, then export plots from a saved electrical
analysis receipt in the project checkout:

```sh
kicad-team electrical-charts --receipt build/electrical/<run>/electrical.json
```

The exporter checks retained inputs against the analysis receipt and writes a
fresh chart receipt under `build/`. Open its `index.html` to choose a case. Each
available transient or AC case has an offline interactive page, PNG, SVG, and
CSV containing the complete retained samples. The page groups traces by unit,
lets you show or hide traces, links value and phase cursors, supports horizontal
drag zoom and reset, and moves the cursor with arrow keys when a plot is focused.
AC frequency is logarithmic and derived phase is unwrapped in degrees. A phase
panel appears only when the saved vectors support it. The page keeps at most
4,000 display points per trace, including endpoints and value/phase extrema;
the CSV retains every native sample. The viewer uses no network resources and
does not rerun the simulator. MCP `export_electrical_charts` uses the same
service when exports are enabled.

When a transient case includes an average or RMS measurement, each trace has
two panels: a full-run overview, including startup, and a detail of that
measurement's own window. Their axes scale independently so a startup spike
does not hide small steady-state variations. The shaded region identifies the
authored measurement window; average and RMS limits apply to that window's
statistic, not to every individual sample. Other transient cases show the full
run. AC charts retain their frequency scale and applicable phase displays.

## Compare two saved AC runs

Select one matching case and measurement from two distinct electrical analysis
receipts in the same project:

```sh
kicad-team electrical-ac-comparison --root /path/to/project-checkout \
  --project controller \
  --baseline build/electrical/baseline/electrical.json \
  --candidate build/electrical/candidate/electrical.json \
  --case passband --measure gain --format json
```

MCP `compare_electrical_ac_runs` takes `project_id`, `baseline`, `candidate`,
`case_id`, `measure_id`, and a fresh `view_id` when exports are enabled. Both
surfaces use the same typed service. The comparison checks each saved report,
requirements file, and waveform against its retained hash. It requires the
same measurement expression, statistic, unit, and scalar or derived-magnitude
meaning; different source revisions and frequency grids can be shown together.
The offline overlay uses each run's own frequency samples without interpolation,
marks disjoint ranges, and retains full CSV and requirements copies. The report
records both source input hash inventories and original analysis statuses.
It does not claim that either historical run applies to today's checkout.

These plots represent saved ngspice model output and declared measurements.
Their cursors show nearest **displayed** samples; consult the full CSV for exact
numeric review. They do not import arbitrary measurement files or establish
physical behavior, bandwidth, stability margin, or acceptance across runs.
For project-owned CSV measurements, use the separate
[measured-series importer](MEASURED_SERIES.md) with explicit time and unit mappings.
