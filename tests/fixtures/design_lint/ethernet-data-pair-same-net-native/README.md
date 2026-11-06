# Ethernet differential data pair same-net fixtures

These schematics are synthetic tooling fixtures. The PHY pin names use the
public [TI DP83826E/DP83826I datasheet](https://www.ti.com/lit/ds/symlink/dp83826i.pdf)
as alias context: `TD_P`/`TD_M` are transmit pins and `RD_P`/`RD_M` are receive
pins. The fixture does not represent a TI implementation or any product board.

- `control.kicad_sch` assigns the RX pair to distinct neutral nets.
- `fault.kicad_sch` assigns U1.3 (`RDP`) and U1.4 (`RDN`) to the same
  `ETH_RX_SHARED` net. The TX pair and MDC/MDIO pins remain separate.

Reviewed SHA-256 values:

- `control.kicad_sch`: `1f1a9c2d402f78ca88b80bb1ef9569fc08a2436b5cb98b3e92fb2ff01c6f74ad`
- `fault.kicad_sch`: `4a5adfdaeb19add80a6e3d382c425e5cdad27741fd2b48dbc5180863bc82cf84`

The existing complementary-pair native lane exports each schematic twice with
digest-pinned KiCad 10.0.0 and 10.0.5 images. It compares normalized netlists,
complete U1.1–U1.6 function/assignment evidence, a quiet distinct-net control,
and one localized same-net REVIEW finding. It checks native export
repeatability; it does not run ERC or DRC and does not establish electrical
approval or PCB continuity. Networking is disabled in the container, which
mounts only staged copies of these synthetic schematics and an output
directory.

```sh
KICAD_TEMPLATE_ROOT=/path/to/KiCad-Test KICAD_RUN_NATIVE_COMPLEMENTARY_PAIR_FIXTURES=1 \
  .venv/bin/python -I -m pytest -q \
  tests/test_complementary_pair_native_fixture_lane.py \
  -m 'design_lint and interface_lint and native_kicad and design_lint_rule(rule_id="bus.complementary_pair_assignment")'
```
