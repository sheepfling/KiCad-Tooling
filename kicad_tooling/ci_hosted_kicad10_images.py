"""Digest-pinned KiCad 10 images shared by exact native fixture lanes."""

KICAD_10_NATIVE_TOOLCHAINS = (
    (
        "10.0.0",
        (
            "ghcr.io/kicad/kicad:10.0.0@sha256:"
            "9549d3a08e0822f9434a9eda0782c812451ab4a733c73535f9e8beed42039bc3"
        ),
    ),
    (
        "10.0.5",
        (
            "ghcr.io/kicad/kicad:10.0.5@sha256:"
            "fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c"
        ),
    ),
)

# Exact-version matrix for the source-audited global ERC severity catalogs.
# Keep it separate so adding ERC releases does not multiply every native lane.
KICAD_10_ERC_SEVERITY_TOOLCHAINS = (
    *KICAD_10_NATIVE_TOOLCHAINS,
    (
        "10.0.6",
        (
            "ghcr.io/kicad/kicad:10.0.6@sha256:"
            "18693567392b80da435f9fa952ce3a3e534c66eb5a6033f5b9c80aa3b19dd3ec"
        ),
    ),
    (
        "10.0.7",
        (
            "ghcr.io/kicad/kicad:10.0.7@sha256:"
            "3224d1bf143185ecc1bd3a1082a36f37f0f4e59d707983a16515a845e3737fc6"
        ),
    ),
    (
        "10.0.8",
        (
            "ghcr.io/kicad/kicad:10.0.8@sha256:"
            "3f4a01786dfbe803a65f345c3342b765db9add913f5e9448f8356793714ddc34"
        ),
    ),
)
