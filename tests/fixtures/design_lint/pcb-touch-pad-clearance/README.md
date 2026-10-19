# Synthetic touch-pad clearance board

This board exists only to regression-test exact pad-to-filled-zone geometry
capture. The connector pad uses the `SIGNAL` net; a separate filled `GND` zone
has a deliberate copper gap around it. The fixture does not prescribe a
product clearance or represent a customer design.

The native lane measures round, oval, rotated oval, and plated through-hole
pads with the KiCad version selected by the fixture case. The rotated and
unrotated ovals face matching straight zone edges at the same offset; their
measured gap must differ by the pad's 0.5 mm change in horizontal half-extent.
The through-hole pads exercise both a below-minimum fault and an inclusive
boundary control against separate filled-zone edges. Independently authored
thresholds exercise review behavior. The native lane also runs KiCad DRC on the
same board and checks that its default rules emit no `clearance` violation
while the project-authored minima still produce the expected lint finding. The
DRC report is repeated and its normalized violation evidence must match. This
compares coverage; it does not establish a universal clearance or fabrication
criterion.
