# CAN termination-heuristic native fixtures

These tooling-owned schematic fixtures verify the `bus.can_excess_termination`
and `bus.can_missing_termination` review heuristics using normalized netlists
exported by native KiCad. The missing-termination fault keeps two 120 Ω
termination options in the schematic but marks both DNP, so the check must use
fitted-state evidence.

- `control.kicad_sch` has three synthetic CAN peers and two fitted direct
  120 Ω resistors. Both heuristics must be quiet.
- `fault.kicad_sch` adds a third fitted direct 120 Ω resistor. The excess
  heuristic must prompt and the missing heuristic must be quiet.
- `missing.kicad_sch` marks both direct resistors DNP. The missing heuristic
  must prompt and the excess heuristic must remain quiet.

Each source is exported twice and compared after typed netlist normalization.
The exact-version lane uses digest-pinned KiCad 10.0.0 and 10.0.5 images
selected by the public template's `controller` and `raspberry-pi-status-led`
toolchains. Both checks are REVIEW clues: external and split termination can
be valid. They do not model physical bus endpoints, resistor tolerance,
placement, impedance, or PCB copper.

Run the native lane from an installed editable tooling checkout with the public
reference-template checkout available:

```sh
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test \
KICAD_RUN_NATIVE_CAN_TERMINATION_FIXTURES=1 \
python3.11 -I -B -m pytest -q \
  -m 'design_lint and interface_lint and native_kicad and (design_lint_rule(rule_id="bus.can_missing_termination") or design_lint_rule(rule_id="bus.can_excess_termination"))' \
  tests/test_can_native_fixture_lanes.py -k can_termination_heuristics
```

Reviewed source hashes:

| Fixture             | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `control.kicad_sch` | `3baa84f1494dc7cdd8b4bef63aa1df792adccfbc8b429895b6d8fc1c45ed7`    |
| `fault.kicad_sch`   | `97f8f0b2feaff11d2a8dd73e6ccb0f4e8f745b5a550813728b703a7216d28756` |
| `missing.kicad_sch` | `b60b3cde1767d6b44c4995b6683b711bbd74941094818187653a203710cf5a96` |
