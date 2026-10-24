# Two-pin LED same-net fixtures

These tooling-owned synthetic schematics exercise
`component.two_pin_led_same_net` with both the exact stock `Device:LED`
identity and a custom LED recognized by an exact project role map. The faults
assign both LED terminals to `LED_TIED`; the controls assign the anode and
cathode to separate schematic nets. Symbols are embedded in the schematics so
the native fixtures do not depend on an external symbol library revision.

| Source                               | SHA-256                                                            | Expected result                                     |
| ------------------------------------ | ------------------------------------------------------------------ | --------------------------------------------------- |
| `same-net-led.kicad_sch`             | `a5ff10fb374138ee4409dfd1e40d7652798497b35c41ed2b5f4c3be7744d3fc7` | One `component.two_pin_led_same_net` review finding |
| `distinct-nets-led.kicad_sch`        | `95cfa1e927bcfea5b251538b742164704541e9e139825bf6faee5a1909efae74` | No same-net LED finding                             |
| `mapped-same-net-led.kicad_sch`      | `46a4a1a375f4c43cd26665eecc213077cc667c9ba860680ff8d68dae4d0c9326` | One finding with exact custom-role evidence         |
| `mapped-distinct-nets-led.kicad_sch` | `d5090afdf19fa8b95acefb34ee024b0200ba984bfbe4f34cf2adc37ef0290b85` | No same-net LED finding                             |

The authored source fixtures are exported twice through the digest-pinned
KiCad 10.0.0 and 10.0.5 native lane. Custom fixtures also verify exact
PART_ID, symbol, footprint, and pin-signature role-map matching. The lane checks
native symbol inventory, pin-net assignments, repeatability, and lint results;
it does not establish LED behavior, current, footprint mapping, board continuity,
or physical population.

Run the focused synthetic rule tests with:

```sh
.venv/bin/python -I -m pytest tests/test_two_pin_leds.py \
  -m 'design_lint and component_lint and design_lint_rule(rule_id="component.two_pin_led_same_net")'
```

Run the native fixture pair with:

```sh
KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES=1 .venv/bin/python -I -m pytest \
  tests/test_two_pin_component_native_fixture_lane.py \
  -m 'design_lint and component_lint and native_kicad and design_lint_rule(rule_id="component.two_pin_led_same_net")'
```
