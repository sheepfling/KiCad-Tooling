# Synthetic footprint-alias named power-input fixtures

These tooling-owned schematics use distinct synthetic connector symbols with the
same value and footprint, complete matching pin metadata, and no PART_ID. The
fault leaves one explicit BIAS_IN power-input contact open while another pin
remains a common-net anchor. The control assigns the BIAS_IN contact on both
peers. The prompt is REVIEW evidence only; it does not assert the contacts must
connect.
