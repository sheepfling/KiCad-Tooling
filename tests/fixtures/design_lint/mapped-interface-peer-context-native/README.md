# Open mapped peer signal context

`open-peer.kicad_sch` is a tooling-owned synthetic schematic. J1.2 is assigned
to `SHARED_RX_NET`; J2.7 is left unconnected. The native lane compares two
current maps over the exact same schematic: an unreasoned mapped open produces
review context from J1.2, while a reviewed intentional-open reason is the valid
control.

The fixture only demonstrates that current, source-matched connector peer
assignments can make an existing open-signal finding easier to review. Peer
grouping does not require common nets, validate the chosen net, or establish
PCB copper continuity. It contains no product or customer design.

Source SHA-256:

- `open-peer.kicad_sch`: `8ac7fb8938022ec33b46c599a001ab3b6240b27ae79fdbb0e63362a4ff401b1b`

The exact-version native lane repeats the export with digest-pinned KiCad
10.0.0 and 10.0.5 images and checks the normalized netlist identity.
