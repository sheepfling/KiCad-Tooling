# Synthetic PCB access probe snapshot

`snapshot.json` is a tooling-owned typed snapshot used by the mocked PCB access
fixture-lane test. It exercises front/back exposure, DNP and netless neighbors,
an unavailable target surface, and circular versus unsupported apertures near
the probe-distance boundary. The test fills source hash, project version, image,
probe hash, and request hash from the temporary public-template checkout at
runtime. This is not a native KiCad export or a product-board fixture.
