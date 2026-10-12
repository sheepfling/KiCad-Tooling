# Synthetic all-open component peer fixtures

These files use two fitted copies of one embedded synthetic component. Both
pins use native `passive` types and generic `Pin_1`/`Pin_2` functions. Pin 1 is
a shared `DATA` anchor. Pin 2 is open on both peers in the fault; the control
assigns the peers to separate `LOAD_A` and `LOAD_B` nets.

| Fixture | Pin 1 assignments | Pin 2 assignments | Expected lint result |
| --- | --- | --- | --- |
| `fault.kicad_sch` | U1/U2 on `DATA` | both open | `component.generic_peer_pin_all_open` prompts for U1.2 and U2.2 when explicitly enabled |
| `control.kicad_sch` | U1/U2 on `DATA` | `LOAD_A` / `LOAD_B` | no all-open prompt |

The rule is default-off. The shared anchor provides comparison context but does
not establish that Pin 2 should connect. The fixtures contain no project design
or proprietary source and do not represent a real component requirement.

Source SHA-256:

- `fault.kicad_sch`: `0cc0e21feb53a94306378599d69e920fc0f7b54d9ce792ba56c523ad42c658ae`
- `control.kicad_sch`: `bf6920996fb0fea85bc4c7124fa69db79a1b58a1dabc89c1bb6b436a7cd40b8b`
