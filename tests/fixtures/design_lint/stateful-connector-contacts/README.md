# Stateful connector contact fixtures

These tooling-owned schematics test a project-mapped physical contact pair that
closes when a plug is removed and opens when it is inserted. The fault
permanently connects both contact terminals to `AUDIO_TIP`; the control keeps
the two terminals on separate schematic nets so the physical contact can
change state. The part identity and contact-state basis are synthetic.

No production schematic, vendor library, or proprietary project file is used.
The native acceptance test exports both fixtures twice with the exact
project-selected KiCad 10.0.0 and 10.0.5 images and checks the normalized
netlist assignments and lint findings.
