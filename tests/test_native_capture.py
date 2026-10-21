"""Compile production capture/gate bodies with explicit renderer/JSON doubles.

This tests filesystem identity and deterministic timing, not native SDL/gameplay.
The actual complete bridge is separately built and graphically qualified.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class NativeCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which("c++")
        if compiler is None:
            raise unittest.SkipTest("C++ compiler absent; native component tests not executed")
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        native = (Path(__file__).resolve().parents[1] / "native/cdda_harness.cpp").read_text()
        # Exact delimited functions, not a general C++ parser or a reimplementation.
        publish = native[native.index("bool publish( "):native.index("void publish_control( ")]
        gate = native[native.index("void ordinary_gate( "):native.index("bool same_frame_png( ", native.index("void ordinary_gate( "))]
        compare = native[native.rindex("bool same_frame_png( "):native.index("void exact_frame_gate()")]
        fixture = Path(__file__).with_name("native_capture_fixture.cpp").read_text()
        source = cls.root / "capture.cpp"
        source.write_text(fixture.replace("// PRODUCTION_FUNCTIONS", compare + gate + publish))
        cls.binary = cls.root / "capture"
        result = subprocess.run([compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", str(source),
                                 "-o", str(cls.binary)], capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise AssertionError(result.stderr)

    def test_capture_identity_and_original_gate_invariants(self):
        for scenario in ("heartbeat", "explicit", "expiry", "encoding-expiry", "backwards",
                         "changed-pixels", "changed-geometry", "changed-metadata", "failed-capture",
                         "missing-file", "authority", "deadline", "source-age"):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory(dir=self.root) as directory:
                result = subprocess.run([str(self.binary), scenario], cwd=directory, capture_output=True,
                                        text=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, f"{scenario} passed\n")

    def test_capture_fingerprint_uses_complete_observation_serializer(self):
        native = (Path(__file__).resolve().parents[1] / "native/cdda_harness.cpp").read_text()
        fingerprint = native[native.index("std::string capture_metadata("):native.index("bool publish( ")]
        self.assertIn('write_observation( out, "", "", "", true, "capture", 0, geometry );', fingerprint)
        self.assertEqual(fingerprint.count("write_observation("), 1)
        self.assertNotIn("erase", fingerprint)
