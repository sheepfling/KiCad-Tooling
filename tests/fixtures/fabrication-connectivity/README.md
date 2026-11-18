# Exported fabrication connectivity fixtures

These tooling-owned board files are small two-layer inputs for evaluating
Gerber/Excellon connectivity against KiCad's IPC-D-356 output. The
`multilayer/` subdirectory contains four-layer fault/control boards with an
inner-copper route and a blind-via unsupported case. They were derived from
synthetic tooling fixtures; no customer or product project was used.

| Board                              | Expected artifact result         | Controlled change                                                     |
| ---------------------------------- | -------------------------------- | --------------------------------------------------------------------- |
| `clean.kicad_pcb`                  | No open or short                 | Two pads share `SIGNAL` and have a connecting top-copper track.       |
| `open.kicad_pcb`                   | One open                         | Same `SIGNAL` pad assignments with the connecting track removed.      |
| `short.kicad_pcb`                  | One short                        | Pad 2 is assigned to `RETURN` while the track still carries `SIGNAL`. |
| `isolated.kicad_pcb`               | No open or short                 | The two pads remain on separate nets with no bridge.                  |
| `via.kicad_pcb`                    | No open, short, or missing drill | A plated through via is placed on the connected `SIGNAL` track.       |
| `bottom-pad-access-code.kicad_pcb` | Access-code control              | A bottom-side SMD pad exports access code `A02` on a two-layer board. |

The missing-drill case is an artifact mutation: remove the exported PTH drill
file from the `via` output while retaining its Gerbers and IPC-D-356 file. Do
not alter the source board for this case.

SHA-256 of each board source:

| Board                              | SHA-256                                                            |
| ---------------------------------- | ------------------------------------------------------------------ |
| `clean.kicad_pcb`                  | `30fefa4885b430de40bd3b225fbc503fd57028ed318cedc21e066b44013451ef` |
| `isolated.kicad_pcb`               | `46d64d96d1b0020141aef2ce129916d93f710ae1315b07544a7b5fb9daf1531c` |
| `open.kicad_pcb`                   | `44cc75701ff0c15c2cea412af6111c9265a6e3b4c21cd2fabdd2bc4e4acb05d9` |
| `short.kicad_pcb`                  | `bc69bce2cb1c86c07c547293e0dd4611e76cb4ecfe981073f0ca3c7015ddc81d` |
| `via.kicad_pcb`                    | `e91b7b2ad41a4500ef2a8d74ae2fbd707487abf1978b6f88f942ca77997012f2` |
| `bottom-pad-access-code.kicad_pcb` | `5f060b2f3182a54220d72d5542f2e3d38247b266789f8e02a2d9fdb9c4cb5dd6` |

The fixtures exercise artifact connectivity only. They do not encode a product
pinout, require unrelated nets to be common, or establish manufacturing
approval.

## Four-layer fixtures

| Board                                                    | Expected result     | Controlled case                                                                     |
| -------------------------------------------------------- | ------------------- | ----------------------------------------------------------------------------------- |
| `multilayer/four-layer-clean.kicad_pcb`                  | PASS                | Two full-stack through-hole pads connect through an In1.Cu route.                   |
| `multilayer/four-layer-via.kicad_pcb`                    | PASS                | A full-stack via shares the In1.Cu route between the through-hole pads.             |
| `multilayer/four-layer-bottom-pad-access-code.kicad_pcb` | Access-code control | A bottom-side SMD pad exports access code `A04` on a four-layer board.              |
| `multilayer/four-layer-open.kicad_pcb`                   | REVIEW / `OPEN`     | Removes only the In1.Cu route.                                                      |
| `multilayer/four-layer-short.kicad_pcb`                  | REVIEW / `SHORT`    | Assigns the second through-hole pad to `RETURN` while retaining the `SIGNAL` route. |
| `multilayer/four-layer-blind-via.kicad_pcb`              | UNSUPPORTED         | Adds a plated via spanning only F.Cu to In1.Cu.                                     |

The native lane exports all four copper layers, drills, and IPC-D-356 twice
with each digest-pinned KiCad version. The `four-layer-via` native control is
also mutated by removing only the via flash from `In2.Cu`; the other layer lands,
plated drill, source via, and routed connectivity remain present. Source SHA-256 values:

| Board                                                    | SHA-256                                                            |
| -------------------------------------------------------- | ------------------------------------------------------------------ |
| `multilayer/four-layer-clean.kicad_pcb`                  | `c1a066ec478600c8fc9031c53e8d7f4a827e11ce770c9d8086917c986d9db719` |
| `multilayer/four-layer-via.kicad_pcb`                    | `7917df50c740bbcaa831f7ce05acbc65da6e526e5f1e6dec9768cc9907dc877b` |
| `multilayer/four-layer-bottom-pad-access-code.kicad_pcb` | `d1d5890475438afc01d34fcbf5c9c6b78d9543c4b57edd28ee01e413c59d7990` |
| `multilayer/four-layer-open.kicad_pcb`                   | `6fde51d4e7ac915465987032dadf4d3a174409bd35d5a9d9e2dceacbcc94dc81` |
| `multilayer/four-layer-short.kicad_pcb`                  | `77ae0433992abbe43323e79727b5fc25dc2c1478564d5543c65eaf961c387397` |
| `multilayer/four-layer-blind-via.kicad_pcb`              | `a8ee8f8f89ab06dd2d75b80522e87956d2ceee13a0ca5a264998f5caed1f34ba` |
