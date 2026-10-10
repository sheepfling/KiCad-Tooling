#!/usr/bin/env python3
import hashlib
import json
import sys
from pathlib import Path

arguments = sys.argv[1:]
mounts = [arguments[index + 1] for index, item in enumerate(arguments[:-1]) if item == "-v"]
work_root = Path(next(item.split(":", 1)[0] for item in mounts if item.endswith(":/work:ro")))
output_root = Path(next(item.split(":", 1)[0] for item in mounts if item.endswith(":/output:rw")))
board = work_root / arguments[-2].removeprefix("/work/")
image = next(item for item in arguments if "@sha256:" in item)
version = image.split("@", 1)[0].rsplit(":", 1)[1]
rows = (
    ("J1.1", "DATA", "Synthetic:Conn1", ("J1.1", "D1.1"), (1850000, 2000000)),
    ("D1.1", "DATA", "Synthetic:TVS", ("J1.1", "D1.1"), (2500000, 2000000)),
    ("D1.2", "GND", "Synthetic:TVS", ("D1.2",), (2500000, 3000000)),
    ("U1.1", "VDD", "Synthetic:IC_QFN", ("U1.1", "C1.1"), (0, 0)),
    ("U1.2", "GND", "Synthetic:IC_QFN", ("U1.2", "C1.2"), (0, 1000)),
    ("C1.1", "VDD", "Synthetic:Cap_0603", ("U1.1", "C1.1"), (500000, 0)),
    ("C1.2", "GND", "Synthetic:Cap_0603", ("U1.2", "C1.2"), (500000, 1000)),
)
plane_uuid = "00000000-0000-0000-0000-0000000000a1"
return_via_id = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
protection_via_id = "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
snapshot = {
    "schema_version": "10",
    "board_sha256": hashlib.sha256(board.read_bytes()).hexdigest(),
    "kicad_version": version,
    "zones_refilled": True,
    "pads": [
        {
            "pad": reference,
            "net": net,
            "footprint": footprint,
            "dnp": False,
            "connected_pads": list(connected),
            "connected_vias": (
                [return_via_id]
                if reference == "C1.2"
                else [protection_via_id]
                if reference == "D1.2"
                else []
            ),
            "connected_zones": (
                [{"uuid": plane_uuid, "layer": "B.Cu"}] if reference in ("U1.2", "C1.2") else []
            ),
            "connected_islands": (
                [{"uuid": plane_uuid, "layer": "B.Cu", "island_index": 0}]
                if reference in ("U1.2", "C1.2")
                else []
            ),
            "positions_nm": [list(position)],
        }
        for reference, net, footprint, connected, position in rows
    ],
    "vias": [
        {
            "id": return_via_id,
            "net": "GND",
            "x_nm": 500000,
            "y_nm": 1000,
            "start_layer": "F.Cu",
            "end_layer": "B.Cu",
            "diameter_nm": 400000,
            "drill_nm": 200000,
            "kind": "through",
            "multiplicity": 1,
        },
        {
            "id": "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            "net": "DATA",
            "x_nm": 2000000,
            "y_nm": 2000000,
            "start_layer": "F.Cu",
            "end_layer": "B.Cu",
            "diameter_nm": 400000,
            "drill_nm": 200000,
            "kind": "through",
            "multiplicity": 1,
        },
        {
            "id": protection_via_id,
            "net": "GND",
            "x_nm": 2500000,
            "y_nm": 3000000,
            "start_layer": "F.Cu",
            "end_layer": "B.Cu",
            "diameter_nm": 400000,
            "drill_nm": 200000,
            "kind": "through",
            "multiplicity": 1,
        },
    ],
    "net_ties": [],
    "zones": [
        {
            "uuid": plane_uuid,
            "layer": "B.Cu",
            "name": "Synthetic GND return plane",
            "net": "GND",
            "filled_island_count": 1,
            "unanchored_pad_island_indexes": [],
            "filled_islands": [
                {
                    "island_index": 0,
                    "outline_nm": [[0, 0], [1000000, 0], [1000000, 1000000], [0, 1000000]],
                    "holes_nm": [],
                }
            ],
        },
        {
            "uuid": "00000000-0000-0000-0000-0000000000a2",
            "layer": "In1.Cu",
            "name": "Synthetic GND antipad plane",
            "net": "GND",
            "filled_island_count": 1,
            "unanchored_pad_island_indexes": [0],
            "filled_islands": [
                {
                    "island_index": 0,
                    "outline_nm": [
                        [1000000, 1000000],
                        [4000000, 1000000],
                        [4000000, 4000000],
                        [1000000, 4000000],
                    ],
                    "holes_nm": [
                        [
                            [2000000, 1750000],
                            [2500000, 1750000],
                            [2500000, 2250000],
                            [2000000, 2250000],
                        ]
                    ],
                }
            ],
        },
    ],
    "access_probe_observations": [],
    "access_probe_requests_sha256": None,
    "tracks": [
        {
            "uuid": "00000000-0000-0000-0000-000000000101",
            "net": "VDD",
            "layer": "F.Cu",
            "width_nm": 250000,
            "start_nm": [0, 0],
            "end_nm": [500000, 0],
            "geometry_kind": "segment",
            "start_pads": ["U1.1"],
            "end_pads": ["C1.1"],
            "start_vias": [],
            "end_vias": [],
            "start_tracks": [],
            "end_tracks": [],
        },
        {
            "uuid": "00000000-0000-0000-0000-000000000102",
            "net": "GND",
            "layer": "F.Cu",
            "width_nm": 250000,
            "start_nm": [0, 1000],
            "end_nm": [500000, 1000],
            "geometry_kind": "segment",
            "start_pads": ["U1.2"],
            "end_pads": ["C1.2"],
            "start_vias": [],
            "end_vias": [],
            "start_tracks": [],
            "end_tracks": [],
        },
        {
            "uuid": "00000000-0000-0000-0000-000000000103",
            "net": "DATA",
            "layer": "F.Cu",
            "width_nm": 250000,
            "start_nm": [2000000, 2000000],
            "end_nm": [3000000, 2000000],
            "geometry_kind": "segment",
            "start_pads": [],
            "end_pads": [],
            "start_vias": ["ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"],
            "end_vias": [],
            "start_tracks": [],
            "end_tracks": [],
        },
        {
            "uuid": "00000000-0000-0000-0000-000000000104",
            "net": "VDD",
            "layer": "F.Cu",
            "width_nm": 250000,
            "start_nm": [0, 500000],
            "end_nm": [100000, 500000],
            "geometry_kind": "segment",
            "start_pads": [],
            "end_pads": [],
            "start_vias": [],
            "end_vias": [],
            "start_tracks": [],
            "end_tracks": [],
        },
        {
            "uuid": "00000000-0000-0000-0000-000000000105",
            "net": "GND",
            "layer": "F.Cu",
            "width_nm": 250000,
            "start_nm": [2500000, 3000000],
            "end_nm": [3000000, 3000000],
            "geometry_kind": "segment",
            "start_pads": ["D1.2"],
            "end_pads": [],
            "start_vias": [protection_via_id],
            "end_vias": [],
            "start_tracks": [],
            "end_tracks": [],
        },
    ],
    "copper_layers": ["F.Cu", "In1.Cu", "B.Cu"],
}
destination = output_root / arguments[-1].removeprefix("/output/")
destination.write_text(json.dumps(snapshot), encoding="utf-8")
