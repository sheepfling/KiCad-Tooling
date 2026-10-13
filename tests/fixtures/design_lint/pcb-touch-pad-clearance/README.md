# Synthetic touch-pad clearance board

This board exists only to regression-test exact pad-to-filled-zone geometry
capture. The connector pad uses the `SIGNAL` net; a separate filled `GND` zone
has a deliberate copper gap around it. The fixture does not prescribe a
product clearance or represent a customer design.

The native lane measures round, oval, and rotated oval pads with the KiCad
version selected by the fixture case. The rotated and unrotated ovals face
matching straight zone edges at the same offset; their measured gap must differ
by the pad's 0.5 mm change in horizontal half-extent. Independently authored
thresholds exercise below-minimum review behavior.
