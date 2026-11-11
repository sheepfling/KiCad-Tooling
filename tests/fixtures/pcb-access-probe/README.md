# Synthetic PCB access probe snapshot

`snapshot.json` is a tooling-owned typed snapshot used by the mocked PCB access
fixture-lane test. It covers the full deterministic probe-envelope catalog,
including front/back exposure, DNP and netless neighbors, unavailable target
surfaces, pad apertures, tracks, zones, edges, and drilled openings. The plated
oblong slots are observed at the 500,001 nm control and 500,000 nm fault
boundaries. The test fills source hash, project version, image, probe hash, and
request hash from the temporary public-template checkout at runtime. This is
synthetic verification evidence, not product-board evidence.
