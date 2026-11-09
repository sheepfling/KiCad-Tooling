# I2C address collision native fixtures

These synthetic KiCad 10 schematics give two fitted addressable targets a
complete, shared `MAIN_SDA`/`MAIN_SCL` bus map. The fault straps both A0 pins to `GND`, resolving
both authored responder addresses to `0x50`. The control straps U1 A0 to `GND`
and U2 A0 to `+3V3`, resolving their authored addresses to `0x50` and `0x51`.

The only board topology difference is U2's A0 net. Each symbol has an explicit
SDA, SCL, and A0 pin; no device identity or address is inferred from a value or
reference. `Synthetic:EEPROM` and the net names are fixture-only assertions.
These sources do not model I2C pull-ups, muxes, firmware, or a commercial part.
They exist to verify exact native export into the already source-bound address
map check.

Each source must be exported twice by the digest-pinned KiCad 10.0.0 and 10.0.5
images. The native contract must preserve both complete three-pin inventories,
shared SDA/SCL segment nets, and U1/U2 A0 assignments. The fault requests one
`bus.i2c_address_collision` review; the control is quiet. Same-address devices
on different authored segments remain a synthetic control in
`tests/test_i2c_address_collisions.py`.

Run the exact-version lane from the tooling checkout with:

```sh
KICAD_RUN_NATIVE_I2C_ADDRESS_COLLISION_FIXTURES=1 \
  .venv/bin/python -I -m pytest -q \
  tests/test_i2c_address_collision_native_fixture_lane.py \
  -m 'design_lint_rule(rule_id="bus.i2c_address_collision")'
```

Reviewed source SHA-256 values:

- `control.kicad_sch`: `109b7699426f756fbf1b592e2950547b8fbbb145e338e2accbd52841d8bcbb1f`
- `fault.kicad_sch`: `f9bfcd74c809e5b7956584162d43c12bae8fa5a98cf827480138c5beb2ff861e`
