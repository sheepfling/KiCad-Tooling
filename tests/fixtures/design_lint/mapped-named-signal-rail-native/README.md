# Mapped named-signal rail fixtures

These tooling-owned schematics use the native pin function `PWM_SYNC`, mapped
as a signal contact by a complete source-matched connector interface. The fault
assigns that contact to `GND`; the control assigns it to the ordinary
`PWM_SYNC` net. The rule reports a review clue only: the authored role and net
label do not prove electrical potential or establish that the assignment is
wrong.

The source-hashed native fault and control export twice with digest-pinned
KiCad 10.0.0 and 10.0.5 images. No project board or customer source is used.
