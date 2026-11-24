"""Check billing arithmetic and CMI boundaries without network access."""

from decimal import Decimal
import json
from pathlib import Path
import unittest

from src.budget import cmi_band, estimate_budget


class BudgetTests(unittest.TestCase):
    def test_round_each_clip_before_summing(self):
        budget = estimate_budget([1.1, 2], {'whisper-1': '.006'}, reserve_fraction=0)
        self.assertEqual(budget['clips'], 2)
        self.assertEqual(budget['requests_all_models'], 2)
        self.assertEqual(Decimal(budget['rounded_duration_total_usd']), Decimal('.0004'))
        self.assertEqual(budget['planning_billable_minutes_per_model_per_condition'], 4 / 60)

    def test_multiple_models_conditions_and_reserve(self):
        budget = estimate_budget([60], {'whisper-1': '.006', 'gpt-transcribe': '.0045', 'chirp_3': '.016'}, conditions=2)
        self.assertEqual(budget['requests_all_models'], 6)
        self.assertEqual(Decimal(budget['rounded_duration_total_usd']), Decimal('.053'))
        self.assertEqual(Decimal(budget['with_reserve_usd']), Decimal('.0636'))
        self.assertEqual(budget['planning_amount_rounded_up_usd'], '0.07')

    def test_integer_seconds_do_not_get_an_extra_second(self):
        budget = estimate_budget([60, 120], {'model': '1'}, reserve_fraction=0)
        self.assertEqual(budget['audio_minutes_once'], 3)
        self.assertEqual(Decimal(budget['rounded_duration_total_usd']), 3)

    def test_invalid_cost_inputs_fail(self):
        for duration in [0, -1, True, 'NaN', 'Infinity']:
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                estimate_budget([duration], {'model': '.006'})
        for conditions in [0, -1, True, 1.5]:
            with self.subTest(conditions=conditions), self.assertRaises(ValueError):
                estimate_budget([1], {'model': '.006'}, conditions=conditions)
        with self.assertRaises(ValueError):
            estimate_budget([], {'model': '.006'})
        with self.assertRaises(ValueError):
            estimate_budget([1], {'model': '-.006'})
        with self.assertRaises(ValueError):
            estimate_budget([1], {'model': '.006'}, reserve_fraction='NaN')

    def test_cmi_boundaries_and_invalid_values(self):
        for value, expected in [(0, '[0,10]'), (10, '[0,10]'), (10.01, '(10,20]'),
                                (20, '(10,20]'), (30, '(20,30]'), (40, '(30,40]'), (50, '(40,50]')]:
            self.assertEqual(cmi_band(value), expected)
        for value in [None, True, -1, 50.01, 'NaN', 'Infinity']:
            self.assertEqual(cmi_band(value), 'invalid_or_missing')

    def test_recorded_test_metadata_reconciles_with_estimate(self):
        root = Path(__file__).resolve().parents[1]
        data = json.loads((root / 'data/manifests/budget_metadata_20261022.json').read_text(encoding='utf-8'))
        prices = json.loads((root / 'configs/api_prices_20261022.json').read_text(encoding='utf-8'))
        rows = [row for shard in data['shards'] for row in shard['rows'] if row['split'] == 'test' and row['speech_type'] == 'cs']
        budget = estimate_budget([row['duration_s'] for row in rows], prices['usd_per_audio_minute'])
        self.assertEqual(len(rows), 1201)
        self.assertEqual(budget['requests_all_models'], 3603)
        self.assertEqual(budget['planning_amount_rounded_up_usd'], '6.68')
        self.assertAlmostEqual(budget['planning_billable_minutes_per_model_per_condition'] * 60, 12589)


if __name__ == '__main__':
    unittest.main()
