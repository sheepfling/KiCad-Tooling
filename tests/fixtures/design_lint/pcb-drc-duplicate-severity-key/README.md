# PCB DRC duplicate severity-key native fixtures

These tooling-owned `.kicad_pro` files configure the synthetic dangling-track
board at `../pcb-reference-zone-island/fault.kicad_pcb`. KiCad 10.0.8's
digest-pinned native DRC run is expected to apply the last repeated value for
the known `track_dangling` key: `ignore` suppresses its warnings and `warning`
reports them. A unique `warning` setting is the valid control.

This measures one known key on one exact patch. It does not generalize native
behavior to other DRC keys or patches, determine the intended setting, assert
a board defect, or establish manufacturing readiness. No project board or
settings were copied into these fixtures.
