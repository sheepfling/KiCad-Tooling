"""ASCII waveform reading for replayable electrical charts and coverage checks."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kicad_tooling.hwrepo.waveform_data import read_waveform

REAL = (
    "Title: transient\nFlags: real\nNo. Variables: 2\nNo. Points: 3\n"
    "Variables:\n0 time time\n1 v(out) voltage\nValues:\n"
    "0 0\n1\n1 0.001\n4.9\n2 0.005\n5\n"
)
COMPLEX = (
    "Title: AC\nFlags: complex\nNo. Variables: 2\nNo. Points: 2\n"
    "Variables:\n0 frequency frequency grid=3\n1 v(out) voltage\nValues:\n"
    "0 1000,0\n1,2\n1 2000,0\n3,-4\n"
)


class WaveformDataTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="waveform-data-")
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "waveforms.raw"

    def test_transient_data_retains_axis_names_types_and_sample_values(self) -> None:
        self.path.write_text(REAL)
        waveform = read_waveform(self.path, expected_axis="time")
        self.assertEqual(waveform.axis_name, "time")
        self.assertEqual(waveform.axis, (0.0, 0.001, 0.005))
        self.assertEqual(
            [(series.name, series.unit) for series in waveform.series], [("v(out)", "voltage")]
        )
        self.assertEqual(waveform.series[0].values, (1 + 0j, 4.9 + 0j, 5 + 0j))

    def test_ac_data_retains_complex_samples_and_declared_frequency_axis(self) -> None:
        self.path.write_text(COMPLEX.replace("1,2", "1, 2"))
        waveform = read_waveform(self.path, expected_axis="frequency")
        self.assertEqual(waveform.axis, (1000.0, 2000.0))
        self.assertEqual(waveform.series[0].values, (1 + 2j, 3 - 4j))
        with self.assertRaisesRegex(ValueError, "does not match"):
            read_waveform(self.path, expected_axis="time")

    def test_rejects_declared_shape_index_and_name_corruption(self) -> None:
        for text, reason in (
            (REAL.replace("No. Points: 3", "No. Points: 4"), "Truncated"),
            (REAL.replace("No. Variables: 2", "No. Variables: 3"), "variable count"),
            (REAL.replace("1 v(out) voltage", "0 v(out) voltage"), "variable index"),
            (REAL.replace("1 v(out) voltage", "1 time voltage"), "Duplicate"),
            (REAL.replace("2 0.005", "1 0.005"), "point index"),
            (REAL + "7\n", "extra waveform values"),
        ):
            with self.subTest(reason=reason):
                self.path.write_text(text)
                with self.assertRaisesRegex(ValueError, reason):
                    read_waveform(self.path)

    def test_rejects_nonfinite_incomplete_and_invalid_axes(self) -> None:
        for text, reason in (
            (REAL.replace("4.9", "nan"), "Non-finite"),
            (REAL.replace("1 0.001", "1 -0.001"), "strictly increasing"),
            (REAL.replace("0 0", "0 -0.01"), "nonnegative"),
            (REAL.replace("Flags: real", "Flags: complex"), "real or complex"),
            (COMPLEX.replace("1,2", "1,nan"), "Non-finite"),
            (COMPLEX.replace("0 1000,0", "0 0,0"), "positive"),
            (COMPLEX.replace("0 1000,0", "0 1000,1"), "imaginary"),
            (COMPLEX.replace("3,-4", "3"), "real or complex"),
        ):
            with self.subTest(reason=reason):
                self.path.write_text(text)
                with self.assertRaisesRegex(ValueError, reason):
                    read_waveform(self.path)

    def test_rejects_non_ascii_binary_artifact(self) -> None:
        self.path.write_bytes(b"\xff\xfe")
        with self.assertRaisesRegex(ValueError, "UTF-8 ASCII"):
            read_waveform(self.path)


if __name__ == "__main__":
    unittest.main()
