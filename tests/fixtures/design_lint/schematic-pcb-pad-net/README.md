# Schematic-to-PCB pad net fixtures

These synthetic sources isolate one pin-to-pad comparison. The schematic
connects `U1.1` to `SENSE` and assigns `Synthetic:Probe_Module` to U1. The
control board assigns its matching pad to `SENSE`; the fault board leaves that
pad unassigned. The expected rule result is clean control and one REVIEW
finding for U1.1 on the fault board.

The fixture compares KiCad source assignments only. It contains no routed
copper and does not establish whether real connector peers should be bonded or
whether any physical path is continuous. All files are tooling-owned synthetic
regression inputs and are not for manufacture.

Pinned source hashes:

- `control.kicad_sch`: `343664d4ba1570250da0eb5b52dc23f7ba214c33e1db580c236dc0008fcaf394`
- `control.kicad_pcb`: `8e83c6c49c271bc686a9d067128e65e823416bd40a1659c9238c1cf743dfb519`
- `fault.kicad_pcb`: `1beeaaefba6942b2b0cc49834f0fea28f710282ba76365fc4688c64c0d4fc1e9`
