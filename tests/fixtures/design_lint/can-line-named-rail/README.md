# Synthetic CAN line named-rail fixtures

These tooling-authored schematics check the bounded `CANH`/`CANL` named-rail
review. The fault assigns CANH to `GND` and CANL to `+3V3`; the control assigns
the same unique line-function pair to neutral bus labels. Both fixtures are
exported repeatedly with the digest-pinned KiCad 10.0.0 and 10.0.5 images.

The synthetic functions and net names are review clues. The pair does not
establish electrical potential, correct bus topology, a defect, PCB copper, or
physical continuity. Project policy can leave the finding at REVIEW, block it,
turn the rule off, or ignore an exact reviewed finding. These files are not
product designs and are not for manufacture.

Reviewed source hashes:

- Fault: `c50e8988e1ab51fa4cf57d1fb9f6b5cd3dd8be7ab6331a361a9cc190b47e279a`
- Control: `1a7b40e9d2b44fe45548cb870787aa8790487faebe905f36060ba72d99f92947`
