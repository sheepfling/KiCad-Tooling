# PCB footprint instance-path trailing separator

These tooling-owned synthetic boards differ only in the direct footprint
`path` value:

- `fault.kicad_pcb` ends its one-segment UUID path with `/`.
- `control.kicad_pcb` contains a second canonical UUID segment and no trailing
  separator.

The source lint reports the fault as a REVIEW prompt. Exact pinned KiCad
10.0.0 and 10.0.5 DRC runs load both boards and produce identical violation
and unconnected-item evidence. This does not test the GUI's Update-from-
Schematic operation or prove the footprint association is lost.

The fixtures contain no cohort board or product data. Their SHA-256 digests
are:

```text
ae1f89e15d3e7fe63f304a4799aa686cae64610e551a723f96795db48876575a  fault.kicad_pcb
50fc820fdf771bf42e9e28e8f70d03246609de106ec2ec59a44154e1a1aaac79  control.kicad_pcb
```

Run source and parity checks with:

```sh
.venv/bin/python -I -m pytest \
  tests/test_pcb_footprint_path_integrity.py \
  tests/test_design_lint_mcp_parity_pcb_footprint_path_trailing_separator.py \
  -m 'design_lint and pcb_lint and design_lint_rule(rule_id="pcb.footprint_path_trailing_separator")'
```

Run pinned native DRC evidence with Docker and:

```sh
KICAD_RUN_NATIVE_PCB_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_pcb_footprint_path_integrity_native.py \
  -m 'design_lint and pcb_lint and native_kicad and design_lint_rule(rule_id="pcb.footprint_path_trailing_separator")'
```
