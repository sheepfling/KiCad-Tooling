# Synthetic CAN line named-rail fixtures

These tooling-authored schematics check the bounded `CANH`/`CANL` named-rail
review for both an IC and a connector. The fault assigns both endpoints' CANH
pins to `GND` and both CANL pins to `+3V3`; the control connects each endpoint
to the neutral `CANH_BUS` and `CANL_BUS` nets. Both cases retain one unique
CANH/CANL pair and complete native pin inventories per reference. The fixtures
are exported repeatedly with digest-pinned KiCad 10.0.0 and 10.0.5 images.

The synthetic functions and net names are review clues. The pair does not
establish electrical potential, correct bus topology, a defect, PCB copper, or
physical continuity. Project policy can leave the finding at REVIEW, block it,
turn the rule off, or ignore an exact reviewed finding. These files are not
product designs and are not for manufacture.

Reviewed source hashes:

- Fault: `b35e61b7b03a30af1df1fcbba40e6cfe3fd3e59c3a4022929f37fba42bace526`
- Control: `9f4fa5661ffbc0552ecd89657663b14f9377dbcbf4e3bca2370958763b9f7ce8`
