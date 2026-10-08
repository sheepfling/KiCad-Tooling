# Synthetic STM32 CubeMX pin-map native fixtures

These fixtures exercise the project-owned STM32-to-KiCad pin map against
native netlists exported by the digest-pinned KiCad 10.0.0 and 10.0.5 images.
They contain a four-pin synthetic MCU symbol and invented signals. The fixture
does not represent a real STM32 package, board, or proprietary project.

The native lane exports each schematic twice, parses both exports into the
same `NetlistContract` type used by design lint, and checks these cases:

| Case           | Source                                   | Expected map result             |
| -------------- | ---------------------------------------- | ------------------------------- |
| `control`      | `valid.kicad_sch` and `valid.ioc`        | No pin-map finding              |
| `net-drift`    | `net-drift.kicad_sch` and `valid.ioc`    | `U1.PA0` net mismatch           |
| `signal-drift` | `valid.kicad_sch` and `signal-drift.ioc` | `U1.PA0` CubeMX signal mismatch |

The test requires `KICAD_TEMPLATE_ROOT` to point to a checkout with the pinned
`controller` (KiCad 10.0.0) and `raspberry-pi-status-led` (KiCad 10.0.5)
profiles. Run the opt-in native regression after installing the tooling dev
dependencies:

```sh
KICAD_RUN_NATIVE_STM32_PIN_MAP_FIXTURES=1 \
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test \
python -I -B -m unittest discover -s tests -t . -p 'test_ci_hosted.py' \
  -k test_cube_mx_and_schematic_pin_map_faults_export_repeatably
```

Native command receipts are retained below ignored `build/`. This lane does not
run ERC or DRC, compile firmware, validate silicon capabilities, or prove PCB
routing. It demonstrates that the exact KiCad-version netlist export preserves
the pins and nets consumed by this deterministic comparison.

## Source hashes

| File                  | SHA-256                                                            |
| --------------------- | ------------------------------------------------------------------ |
| `valid.kicad_sch`     | `5656bf52778eb58d224d7b211999cb816c26bbf7220fc6430887b74ee3b42716` |
| `net-drift.kicad_sch` | `399e94cf7213b926e435c1053a43da4ad6a2e82a419d8763ebd3df10b4b50738` |
| `valid.ioc`           | `f36873f874ab1ac1252ec8012b491042eca3ed24129dbd51d5f6053d50821c42` |
| `signal-drift.ioc`    | `5bcd5d407060c7c7978e773f1929e6713c275b23c6cc7563faecce2e6a61867a` |
