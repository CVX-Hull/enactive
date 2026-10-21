"""Geometry/input data validation; this is not native delivery qualification."""
from copy import deepcopy
import unittest

from harness.gameplay.contracts import ContractError
from harness.gameplay.native_input import geometry_schema, validate_geometry, validate_input
from tests.test_controller import frame_geometry


class NativeInputTests(unittest.TestCase):
    def test_geometry_requires_bounded_positive_allocated_output_and_viewport(self):
        base = frame_geometry()
        self.assertEqual(validate_geometry(base), base)
        for changes in (dict(window_width=True), dict(output_width=0), dict(viewport=[0, 0, 0, 1]),
                        dict(viewport=[1, 0, 1, 1]), dict(output_width=16384, output_height=16384),
                        dict(viewport=[0, -1, 1, 1]), dict(extra=1)):
            with self.subTest(changes=changes), self.assertRaises(ContractError):
                validate_geometry(base | changes)
        copied = geometry_schema()
        copied.clear()
        self.assertTrue(geometry_schema())

    def test_closed_direct_payload_and_pinned_text_range(self):
        valid = [dict(type="key", key="UP", modifiers=["SHIFT"]),
                 dict(type="text", text="é"), dict(type="text", text="\u0301"),
                 dict(type="click", button="left", x=0, y=0, geometry=frame_geometry())]
        for value in valid:
            self.assertEqual(validate_input(value), value)
        for value in [dict(type="text", text=text) for text in ("ab", "\n", "\x00", "\u2028", "🙂", "\ud800")]:
            with self.subTest(value=repr(value)), self.assertRaises(ContractError):
                validate_input(value)
        bad = [valid[0] | dict(modifiers=["CTRL", "CTRL"]), valid[0] | dict(key="F999"),
               valid[2] | dict(extra="x"), valid[3] | dict(x=1), valid[3] | dict(x=True)]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ContractError):
                validate_input(value)
        value = deepcopy(valid[-1])
        decoded = validate_input(value)
        decoded["geometry"]["viewport"][0] = 9
        self.assertEqual(value["geometry"]["viewport"][0], 0)
        self.assertEqual(validate_input(dict(type="text", text="ab"), text_limit=24)["text"], "ab")
