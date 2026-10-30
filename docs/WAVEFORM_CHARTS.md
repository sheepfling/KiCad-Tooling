# Review simulation waveforms

Install the optional `charts` extra, then export plots from a saved electrical
analysis receipt in the project checkout:

```sh
kicad-team electrical-charts --receipt build/electrical/<run>/electrical.json
```

The exporter checks retained inputs against the analysis receipt and writes a
fresh chart receipt under `build/`. For each available transient or AC case, it
produces a PNG, SVG, and a CSV containing the complete retained samples. It
does not rerun the simulator. The MCP `export_electrical_charts` operation
uses the same service and requires exports to be enabled.

When a transient case includes an average or RMS measurement, each trace has
two panels: a full-run overview, including startup, and a detail of that
measurement's own window. Their axes scale independently so a startup spike
does not hide small steady-state variations. The shaded region identifies the
authored measurement window; average and RMS limits apply to that window's
statistic, not to every individual sample. Other transient cases show the full
run. AC charts retain their frequency scale and applicable phase displays.

These plots represent the saved ngspice model output and declared measurements.
They do not import arbitrary measurement files or establish physical behavior.
For project-owned CSV measurements, use the separate
[measured-series importer](MEASURED_SERIES.md) with explicit time and unit mappings.
