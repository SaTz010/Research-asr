"""Four-condition pairing, corpus weighting and honest uncertainty scopes."""
import copy
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from analyze_forced_nepali import paired_group
from compare_audited_references import text_scores

SETTINGS = {'seed': 42, 'replicates': 3, 'percentiles': [0, 100], 'minimum_videos_for_interval': 2}


def row(key, reference, local, api):
    return {'clip_id': key, 'video_id': key, 'channel': 'one', 'cmi': 20,
            'systems': {s: text_scores(reference, hyp) for s, hyp in [('local', local), ('whisper_api', api)]}}


class ForcedAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.auto = [row('v', 'a', 'a', 'b'), row('w', 'a b c', 'a b c', 'a b c')]
        self.forced = [row('v', 'a', 'b', 'a'), row('w', 'a b c', 'a b c', 'a b c')]
        self.weights = np.array([[2, 0], [1, 1], [0, 2]])

    def run_group(self, **kwargs):
        return paired_group(self.auto, self.forced, ['v', 'w'], self.weights, {**SETTINGS, **kwargs})

    def test_four_condition_corpus_weighting_and_direct_interaction(self):
        result = self.run_group()
        self.assertEqual(result['systems']['local']['forced_minus_auto_pp']['wer'], 25)
        self.assertEqual(result['systems']['whisper_api']['forced_minus_auto_pp']['wer'], -25)
        self.assertEqual(result['change_difference_local_minus_api_pp']['wer'], 50)
        self.assertEqual(result['change_difference_interval_95_pp']['wer'], [0, 200])
        self.assertEqual(result['systems']['local']['interval_95_pp']['wer'], [0, 100])
        self.assertEqual(result['systems']['whisper_api']['interval_95_pp']['wer'], [-100, 0])

    def test_pair_counts_and_no_input_mutation(self):
        before = copy.deepcopy([self.auto, self.forced])
        result = self.run_group()
        self.assertEqual(result['systems']['local']['paired_clip_changes']['wer'],
                         {'improved': 0, 'tied': 1, 'worsened': 1})
        self.assertEqual(result['systems']['whisper_api']['paired_clip_changes']['wer'],
                         {'improved': 1, 'tied': 1, 'worsened': 0})
        self.assertEqual([self.auto, self.forced], before)

    def test_condition_reordering_metadata_and_denominator_drift_rejected(self):
        for change in ['order', 'cmi', 'words', 'characters']:
            with self.subTest(change=change):
                changed = copy.deepcopy(self.forced)
                if change == 'order':
                    changed.reverse()
                elif change == 'cmi':
                    changed[0]['cmi'] = 21
                else:
                    field = 'reference_words' if change == 'words' else 'reference_characters'
                    for s in changed[0]['systems'].values():
                        s[field] += 1
                with self.assertRaises(ValueError):
                    paired_group(self.auto, changed, ['v', 'w'], self.weights, SETTINGS)

    def test_withhold_small_group_and_do_not_drop_zero_denominator_draws(self):
        small = self.run_group(minimum_videos_for_interval=3)
        self.assertEqual(small['interval_status'], 'withheld_fewer_than_minimum_videos')
        self.assertIsNone(small['systems']['local']['interval_95_pp'])
        single = paired_group(self.auto[:1], self.forced[:1], ['v', 'w'], self.weights,
                              {**SETTINGS, 'minimum_videos_for_interval': 1})
        self.assertEqual(single['invalid_zero_denominator_draws'], 1)
        self.assertEqual(single['interval_status'], 'withheld_zero_denominator_draws')
        self.assertIsNone(single['change_difference_interval_95_pp'])

    def test_identical_conditions_produce_exact_zero_changes(self):
        result = paired_group(self.auto, copy.deepcopy(self.auto), ['v', 'w'], self.weights, SETTINGS)
        for system in ['local', 'whisper_api']:
            self.assertEqual(result['systems'][system]['forced_minus_auto_pp']['wer'], 0)
            self.assertEqual(result['systems'][system]['interval_95_pp']['wer'], [0, 0])
        self.assertEqual(result['change_difference_interval_95_pp']['wer'], [0, 0])

    def test_empty_group_has_no_invented_scores(self):
        result = paired_group([], [], ['v', 'w'], self.weights, SETTINGS)
        self.assertEqual(result['clips'], 0)
        self.assertEqual(result['systems'], {})
        self.assertEqual(result['interval_status'], 'withheld_empty_group')


if __name__ == '__main__':
    unittest.main()
