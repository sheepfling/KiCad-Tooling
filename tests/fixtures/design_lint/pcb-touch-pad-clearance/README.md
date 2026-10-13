# Synthetic touch-pad clearance board

This board exists only to regression-test exact pad-to-filled-zone geometry
capture. The connector pad uses the `SIGNAL` net; a separate filled `GND` zone
has a deliberate copper gap around it. The fixture does not prescribe a
product clearance or represent a customer design.

The native lane measures this gap with the KiCad version selected by the
fixture case. It tests the measured value against two independently authored
thresholds so both below-minimum and valid-control cases exercise the native
geometry path.
