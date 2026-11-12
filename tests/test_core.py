"""Unit tests for instroke_core. Run from the repository root:

    python -m unittest discover -s tests
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "instroke"))

from instroke_core import (cost_for, format_duration, hash_password, parse_switch_message,  # noqa: E402
                           update_settings, vat_breakdown, verify_password)


class ParseSwitchMessage(unittest.TestCase):
    def test_valid_lines(self):
        self.assertEqual(parse_switch_message(b"5 1\r\n"), (5, 1))
        self.assertEqual(parse_switch_message(b"23 0\n"), (23, 0))
        self.assertEqual(parse_switch_message(b"0 1"), (0, 1))  # old firmware without a newline

    def test_rejects_malformed_input(self):
        for raw in (b"", b"\r\n", b"5", b"5 1 2", b"x 1", b"5 2", b"24 1", b"-1 1", b"\xff\xfe\r\n", b"5 10 1"):
            with self.subTest(raw=raw):
                self.assertIsNone(parse_switch_message(raw))


class Pricing(unittest.TestCase):
    def test_full_hour(self):
        self.assertEqual(cost_for(8, 3600), 8.00)

    def test_rounds_down_to_five_cents(self):
        self.assertEqual(cost_for(8, 1), 0.00)      # 0.2 cents
        self.assertEqual(cost_for(8, 23), 0.05)     # 5.1 cents
        self.assertEqual(cost_for(8, 22), 0.00)     # 4.9 cents
        self.assertEqual(cost_for(10.5, 1800), 5.25)

    def test_negative_time_costs_nothing(self):
        self.assertEqual(cost_for(8, -10), 0.00)


class Vat(unittest.TestCase):
    def test_vat_is_contained_in_the_gross_price(self):
        self.assertEqual(vat_breakdown(11.90, 0.19), (10.00, 1.90))
        self.assertEqual(vat_breakdown(8.00, 0.19), (6.72, 1.28))
        self.assertEqual(vat_breakdown(12.00, 0.20), (10.00, 2.00))

    def test_net_plus_vat_equals_gross(self):
        for cents in range(0, 5000, 5):
            gross = cents / 100
            net, vat = vat_breakdown(gross)
            self.assertAlmostEqual(net + vat, gross, places=2)


class Duration(unittest.TestCase):
    def test_format(self):
        self.assertEqual(format_duration(0), "00:00:00")
        self.assertEqual(format_duration(3725), "01:02:05")
        self.assertEqual(format_duration(26 * 3600), "26:00:00")  # keeps counting past a day


class Passwords(unittest.TestCase):
    def test_round_trip(self):
        record = hash_password("geheim1", iterations=1000)
        self.assertTrue(verify_password("geheim1", record))
        self.assertFalse(verify_password("geheim2", record))
        self.assertNotIn("geheim1", json.dumps(record))

    def test_salt_makes_hashes_differ(self):
        self.assertNotEqual(hash_password("same", iterations=1000)["hash"],
                            hash_password("same", iterations=1000)["hash"])

    def test_missing_record(self):
        self.assertFalse(verify_password("anything", None))


class Settings(unittest.TestCase):
    def test_update_keeps_other_keys_and_unicode(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "settings.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"names": ["A", "B"], "prices": [8, 8], "comport": "COM5"}, f)

            def rename(s):
                s["names"][1] = "Größer Tisch"

            update_settings(path, rename)
            with open(path, encoding="utf-8") as f:
                saved = json.load(f)
            self.assertEqual(saved["names"], ["A", "Größer Tisch"])
            self.assertEqual(saved["comport"], "COM5")
            self.assertFalse(os.path.exists(path + ".tmp"))


if __name__ == "__main__":
    unittest.main()
