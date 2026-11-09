# I2C address map native fixtures

These synthetic KiCad 10 schematics give two fitted addressable targets a
complete, shared `MAIN_SDA`/`MAIN_SCL` bus map. The collision fault straps both
A0 pins to `GND`, resolving both responder addresses to `0x50`. The control
straps U1 A0 to `GND` and U2 A0 to `+3V3`, resolving their observed addresses
to `0x50` and `0x51`.

The only board topology difference is U2's A0 net. Each symbol has an explicit
SDA, SCL, and A0 pin; no device identity or address is inferred from a value or
reference. `Synthetic:EEPROM` and the net names are fixture-only assertions.
These sources do not model I2C pull-ups, muxes, firmware, or a commercial part.
They verify exact native export into the source-bound address-map checks.

Each source must be exported twice by the digest-pinned KiCad 10.0.0 and 10.0.5
images. The native contract must preserve both complete three-pin inventories,
shared SDA/SCL segment nets, and U1/U2 A0 assignments. Against the accurate
map, the collision fault requests one `bus.i2c_address_collision` review and
the control is quiet. Against an authored map that expects U2 at `0x50`, the
same control source requests one `bus.i2c_address_mismatch` review for U2 at
`0x51`. The corrected `0x51` map is quiet. Same-address devices on different
authored segments remain a synthetic control in
`tests/test_i2c_address_collisions.py`.

The same native control export also exercises `bus.i2c_unmapped_responder`.
An authored map containing U1 but omitting fitted U2 must keep U1's address
coverage complete and issue one review for U2. Listing both responders is the
control with no finding for this rule; the overall design-lint report may still
be in review because of other checks. This checks a missing map entry; it does
not decide that every SDA/SCL device needs an address, or that a bridge, mux,
or translator is an addressable endpoint.

Run the exact-version lane from the tooling checkout with:

```sh
KICAD_RUN_NATIVE_I2C_ADDRESS_MAP_FIXTURES=1 \
  .venv/bin/python -I -m pytest -q \
  tests/test_i2c_address_map_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad'
```

Reviewed source SHA-256 values:

- `control.kicad_sch`: `109b7699426f756fbf1b592e2950547b8fbbb145e338e2accbd52841d8bcbb1f`
- `fault.kicad_sch`: `f9bfcd74c809e5b7956584162d43c12bae8fa5a98cf827480138c5beb2ff861e`
