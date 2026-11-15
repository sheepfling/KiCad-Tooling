# Exported fabrication connectivity fixtures

These tooling-owned board files are small two-layer inputs for evaluating
Gerber/Excellon connectivity against KiCad's IPC-D-356 output. They were derived
from the synthetic `pcb-unassigned-copper-pad/control.kicad_pcb` fixture; no
customer or product project was used.

| Board                | Expected artifact result         | Controlled change                                                     |
| -------------------- | -------------------------------- | --------------------------------------------------------------------- |
| `clean.kicad_pcb`    | No open or short                 | Two pads share `SIGNAL` and have a connecting top-copper track.       |
| `open.kicad_pcb`     | One open                         | Same `SIGNAL` pad assignments with the connecting track removed.      |
| `short.kicad_pcb`    | One short                        | Pad 2 is assigned to `RETURN` while the track still carries `SIGNAL`. |
| `isolated.kicad_pcb` | No open or short                 | The two pads remain on separate nets with no bridge.                  |
| `via.kicad_pcb`      | No open, short, or missing drill | A plated through via is placed on the connected `SIGNAL` track.       |

The missing-drill case is an artifact mutation: remove the exported PTH drill
file from the `via` output while retaining its Gerbers and IPC-D-356 file. Do
not alter the source board for this case.

SHA-256 of each board source:

| Board                | SHA-256                                                            |
| -------------------- | ------------------------------------------------------------------ |
| `clean.kicad_pcb`    | `30fefa4885b430de40bd3b225fbc503fd57028ed318cedc21e066b44013451ef` |
| `isolated.kicad_pcb` | `46d64d96d1b0020141aef2ce129916d93f710ae1315b07544a7b5fb9daf1531c` |
| `open.kicad_pcb`     | `44cc75701ff0c15c2cea412af6111c9265a6e3b4c21cd2fabdd2bc4e4acb05d9` |
| `short.kicad_pcb`    | `bc69bce2cb1c86c07c547293e0dd4611e76cb4ecfe981073f0ca3c7015ddc81d` |
| `via.kicad_pcb`      | `e91b7b2ad41a4500ef2a8d74ae2fbd707487abf1978b6f88f942ca77997012f2` |

The fixtures exercise artifact connectivity only. They do not encode a product
pinout, require unrelated nets to be common, or establish manufacturing
approval.
