"""Reproducibility and accounting boundaries for offline experiments."""
import random
import unittest

from tools.memory_study.common import json_bytes, rng


class CommonStudyTests(unittest.TestCase):
    def test_streams_do_not_depend_on_global_rng_or_other_consumers(self):
        original = random.getstate()
        try:
            first = [rng(3, "L").getrandbits(64), rng(3, "C").getrandbits(64)]
            random.seed(999)
            random.random()
            other = rng(3, "other")
            for _ in range(100):
                other.random()
            self.assertEqual(first, [rng(3, "L").getrandbits(64),
                                     rng(3, "C").getrandbits(64)])
            self.assertNotEqual(first[0], first[1])
            self.assertNotEqual(first[0], rng(4, "L").getrandbits(64))
        finally:
            random.setstate(original)

    def test_json_counts_utf8_and_rejects_nonfinite_data(self):
        self.assertEqual(json_bytes({"é": 1}), 8)
        self.assertEqual(json_bytes({"b": 2, "a": 1}), 13)
        with self.assertRaises(ValueError):
            json_bytes({"value": float("nan")})


if __name__ == "__main__":
    unittest.main()
