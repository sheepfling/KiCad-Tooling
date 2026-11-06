# Synthetic LED current-window fixtures

These tooling-owned schematics exercise one project-authored LED current map.
They contain no product design or private project source.

| Fixture | Expected result | SHA-256 |
| --- | --- | --- |
| `control.kicad_sch` | 470 Ω nominal resistor with the authored 5% tolerance remains inside the 2.2–3.4 mA window | `a6be3691cf356ac8020d10341116d56a7cd9e36a6cb09b1c885c574d899ee17c` |
| `value-fault.kicad_sch` | 100 Ω nominal resistor exceeds the authored upper current bound | `ef95f66b22f00b3a23ab8db26a3a53c0f36d11dba1add141dc440449d0d1485f` |

The native fixture lane exports each schematic twice with the exact digest-
pinned KiCad 10.0.0 and 10.0.5 images. It checks repeatable native netlists,
ERC-clean fixtures, and the mapped rule result. The authored map in the test
provides all voltages, resistance bounds, tolerance, target current, and bases;
the tooling does not infer electrical requirements from the schematic.

Reproduce it with:

```sh
KICAD_RUN_NATIVE_LED_CURRENT_RANGE_FIXTURES=1 \
.venv/bin/python -I -m pytest -q tests/test_led_current_native_fixture_lane.py \
  -m 'design_lint and component_lint and native_kicad'
```

The calculated interval is an ideal DC source-minus-forward-voltage estimate.
It does not establish part ratings, LED brightness, dynamic behavior, power
dissipation, source impedance, PCB continuity, or manufacturing readiness.
