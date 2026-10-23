# Synthetic serial TX/RX same-net fixtures

The two schematics contain a single synthetic UART controller with native
`USART1_TX` and `USART1_RX` pin functions. The fault assigns both pins to
`UART1_DATA`; the full-duplex control assigns them to separate nets. The rule
is default-off because single-wire, loopback, or otherwise shared TX/RX
topologies can be intentional. Enabling it asks for review and does not decide
which topology the project requires.

The native regression exports each schematic twice on digest-pinned KiCad
10.0.0 and 10.0.5 images and compares normalized typed-netlist evidence. The
fixtures are tooling-owned and contain no product or project source.

| Case                            | Source SHA-256                                                     | Normalized netlist SHA-256 (10.0.0 and 10.0.5)                     |
| ------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ |
| `full-duplex-control.kicad_sch` | `238844665e1a91d13efb3f263d5947983f6252b2771284b9be5835f5cb739436` | `49c62a33d7d8abe3d580a46c28303ddf9000ef308c8e2d428c9fb6384cbab840` |
| `same-net.kicad_sch`            | `944405130158dcca8d6f8205a094e9428f56736bc0cf8bba2da1e52ab4c826cd` | `677d7de719b2edbdd47cab8d393f015edc662aca77edd8a09d9906840e08ffc7` |

Each fixture's repeated raw netlist export matched within each KiCad version. The native images were
`ghcr.io/kicad/kicad:10.0.0@sha256:9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3`
and
`ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c`.
