"""Compile production marker draw/join bodies; renderer and engine are doubles.

The same patcher output is built into the real game for separate qualification.
"""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

from harness.gameplay.mission_contracts import validate_visible_ui
from harness.gameplay.evidence import EvidenceStore
from harness.gameplay.interactions import check_visible_row_agreement
from harness.gameplay.policy_program import PolicyProgram
from harness.gameplay.program_input import program_view
from tests.test_gameplay_evidence import observation, png
from tests import test_setup


class NativeVisibleUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which("c++")
        if compiler is None:
            raise unittest.SkipTest("C++ compiler absent")
        cls.fixture = test_setup.SetupTests(methodName="runTest")
        cls.fixture.setUp()
        cls.addClassCleanup(cls.fixture.doCleanups)
        repository, source = cls.fixture.patch_fixture()
        patched = cls.fixture.run_patch(repository, source)
        if patched.returncode:
            raise AssertionError(patched.stderr)
        root = Path(__file__).resolve().parents[1]
        native = (root / "native/cdda_harness.cpp").read_text()
        inventory = (source / "src/inventory_ui.cpp").read_text()
        types = native[native.index("struct visible_row {"):native.index("bool ui_top = false;")]
        serializer = native[native.index("std::string ui_text("):native.index("std::string encode_ui(")]
        functions = native[native.index("void ui_redraw("):native.index("bool enabled()\n")]
        locals_start = inventory.index("        std::optional<std::string> harness_label;")
        locals_end = inventory.index("        size_t count", locals_start)
        label_start = inventory.index("                if( allows_selecting() && cell_index == 0")
        label_end = inventory.index("            }\n\n            x1 = x2;", label_start)
        tail_start = inventory.index("        if( entry.is_item() ) {\n            int xx = p.x;")
        tail_end = inventory.index("    }\n\n    if( pages_count() > 1 )", tail_start)
        fixture = (root / "tests/native_visible_ui_fixture.cpp").read_text()
        for marker, body in (("UI_TYPES", types), ("UI_SERIALIZER", serializer),
                ("UI_FUNCTIONS", functions), ("ROW_LOCALS", inventory[locals_start:locals_end]),
                ("LABEL_HOOK", inventory[label_start:label_end]), ("DRAW_TAIL", inventory[tail_start:tail_end])):
            fixture = fixture.replace("// PRODUCTION_" + marker, body)
        path = cls.fixture.root / "ui.cpp"
        path.write_text(fixture)
        cls.binary = path.with_suffix("")
        result = subprocess.run([compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", str(path),
            "-o", str(cls.binary)], capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise AssertionError(result.stderr)

    def ui(self, scenario):
        result = subprocess.run([str(self.binary), scenario], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        return validate_visible_ui(json.loads(result.stdout))

    def test_actual_draw_literals_survive_serializer_and_program_projection(self):
        for case, expected in (("unmarked", "-"), ("marked", "+"), ("partial", "#"),
                ("disabled", "+"), ("symbols-visible", "+"), ("unfocused", "+")):
            with self.subTest(case=case):
                ui = self.ui(case)
                self.assertEqual(ui["rows"][0]["rendered_marker"], expected)
                self.assertEqual(ui["rows"][0]["text"], "item")
                self.assertEqual(ui["selected"], None if case == "unfocused" else "row-0")
                self.assertEqual(ui["rows"][0]["enabled"], case != "disabled")
                view = program_view({**observation(), "ui": ui})
                self.assertEqual(view["schema"], "program-view/2")
                self.assertEqual(view["ui"], ui)

    def test_unknown_hidden_and_ineligible_marker_is_not_unmarked(self):
        for case in ("clipped-marker", "symbols-clipped", "inactive", "not-multiselect", "uilist"):
            with self.subTest(case=case):
                self.assertIsNone(self.ui(case)["rows"][0]["rendered_marker"])
        for case in ("nonselecting", "nonitem", "off-row", "omitted-label"):
            with self.subTest(case=case):
                self.assertEqual(self.ui(case)["rows"], [])
        self.assertIsNone(self.ui("topmost"))

    def test_duplicate_labels_and_overflow_keep_each_original_row(self):
        ui = self.ui("duplicates")
        self.assertEqual([r["text"] for r in ui["rows"]], ["item", "item"])
        self.assertEqual([r["rendered_marker"] for r in ui["rows"]], ["-", "+"])
        ui = self.ui("overflow")
        self.assertEqual(len(ui["rows"]), 32)
        self.assertEqual({r["rendered_marker"] for r in ui["rows"]}, {"-"})
        self.assertEqual(ui["selected"], "row-0")

    def test_retained_marker_reopens_without_changing_label_agreement_and_passive_program(self):
        directory = self.fixture.root / "retained-marker"
        bridge = directory / "bridge"
        bridge.mkdir(parents=True)
        references = []
        code = """function step(view,state) {
          const marker = view.schema === 'program-view/2' ? view.ui.rows[0].rendered_marker : null;
          return {status:marker === '+' ? 'done' : 'yield', state, input:null,
            reason:marker === null ? 'unknown marker' : 'literal ' + marker};
        }"""
        with EvidenceStore(bridge, directory / "evidence") as store, PolicyProgram(code) as program:
            for number, case in enumerate(("unmarked", "marked", "clipped-marker"), 1):
                ui = self.ui(case)
                value = observation(number)
                value.update(category="INVENTORY", ui=ui, scene=None)
                value["boundary"]["kind"] = "menu"
                (bridge / value["frame"]).write_bytes(png())
                ref = store.ingest(value, received_monotonic=100, now_monotonic=100,
                    now_timestamp_ms=value["timestamp_ms"])
                references.append((ref, ui))
                retained = store.observation(ref)
                check_visible_row_agreement(dict(control="vertical", rows=[dict(label="item", enabled=True)],
                    selected=0), retained)
                result = program.step(program_view(retained), {}, timeout_seconds=.05)
                self.assertEqual(result["status"], "done" if case == "marked" else "yield")
                self.assertIsNone(result["input"])
        with EvidenceStore(bridge, directory / "evidence") as reopened:
            for ref, ui in references:
                self.assertEqual(program_view(reopened.observation(ref))["ui"], ui)
