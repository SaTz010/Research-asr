"""Paired clustering, corpus weighting and honest interval eligibility."""
import copy
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from analyze_uncertainty import bootstrap_group, influence, paired_clips, video_counts, video_design

SETTINGS = {'seed': 42, 'replicates': 100, 'percentiles': [2.5, 97.5], 'minimum_videos_for_interval': 2}


def row(key, video, channel, words, local, api):
    return {'clip_id': key, 'video_id': video, 'channel': channel, 'systems': {
        s: {'word_errors': e, 'reference_words': words, 'character_errors': 2 * e, 'reference_characters': 2 * words}
        for s, e in [('local', local), ('whisper_api', api)]}}


class UncertaintyTests(unittest.TestCase):
    def test_bootstrap_keeps_video_channel_strata_and_is_reproducible(self):
        rows = [row(str(i), str(i), 'a' if i < 2 else 'b', 2, 1, 0) for i in range(5)]
        before = copy.deepcopy(rows)
        videos, channels, weights = video_design(rows, SETTINGS)
        self.assertTrue(np.all(weights[:, :2].sum(axis=1) == 2))
        self.assertTrue(np.all(weights[:, 2:].sum(axis=1) == 3))
        self.assertTrue(np.any(weights > 1))
        np.testing.assert_array_equal(weights, video_design(rows, SETTINGS)[2])
        self.assertEqual(rows, before)

    def test_corpus_weighting_and_exact_paired_percentiles(self):
        rows = [row('a', 'v', 'c', 1, 0, 1), row('b', 'w', 'c', 9, 9, 0)]
        videos = ['v', 'w']
        weights = np.array([[2, 0], [1, 1], [0, 2]])
        settings = {**SETTINGS, 'replicates': 3, 'percentiles': [0, 100]}
        result = bootstrap_group(rows, videos, weights, settings)
        self.assertAlmostEqual(result['local_minus_api_pp']['wer'], 80)
        self.assertEqual(result['interval_95_pp']['wer'], [-100, 100])
        self.assertNotAlmostEqual(result['local_minus_api_pp']['wer'], 0)

    def test_common_draws_preserve_constant_paired_gap_despite_system_variation(self):
        rows = [row('a', 'v', 'c', 2, 1, 0), row('b', 'w', 'c', 4, 4, 2)]
        videos, _, weights = video_design(rows, SETTINGS)
        result = bootstrap_group(rows, videos, weights, SETTINGS)
        self.assertEqual(result['interval_95_pp']['wer'], [50, 50])
        self.assertEqual(result['interval_95_pp']['cer'], [50, 50])

    def test_small_groups_have_no_interval_and_zero_draws_are_not_replaced(self):
        rows = [row('a', 'v', 'c', 1, 0, 1)]
        weights = np.array([[2, 0], [1, 1], [0, 2]])
        small = bootstrap_group(rows, ['v', 'w'], weights, SETTINGS)
        self.assertIsNone(small['interval_95_pp'])
        self.assertEqual(small['interval_status'], 'withheld_fewer_than_minimum_videos')
        eligible = bootstrap_group(rows, ['v', 'w'], weights, {**SETTINGS, 'minimum_videos_for_interval': 1})
        self.assertIsNone(eligible['interval_95_pp'])
        self.assertEqual(eligible['invalid_zero_denominator_draws'], 1)
        self.assertEqual(eligible['interval_status'], 'withheld_zero_denominator_draws')

    def test_video_removal_drops_all_its_clips_with_shared_denominators(self):
        rows = [row('a', 'v', 'a', 1, 0, 1), row('b', 'v', 'a', 1, 0, 1), row('c', 'w', 'b', 9, 9, 0)]
        result = influence(rows, ['v', 'w'], {'v': 'a', 'w': 'b'})
        first = result['leave_one_video_out'][0]
        self.assertEqual(first['removed_clips'], 2)
        self.assertEqual(first['removed_reference_words'], 2)
        self.assertEqual(first['local_minus_api_pp']['wer'], 100)
        self.assertEqual(result['leave_one_channel_out']['a']['local_minus_api_pp']['wer'], 100)
        self.assertEqual(result['leave_one_video_out_range_pp']['wer'], [-100, 100])

    def test_duplicate_mismatched_or_invalid_counts_and_cross_channel_video_rejected(self):
        for failure in ['duplicate', 'denominator', 'negative', 'zero', 'float', 'unknown_video', 'cross_channel']:
            with self.subTest(failure=failure):
                rows = [row('a', 'v', 'a', 2, 1, 0), row('b', 'w', 'b', 3, 2, 1)]
                if failure == 'duplicate':
                    rows.append(rows[0])
                elif failure == 'denominator':
                    rows[0]['systems']['local']['reference_words'] = 3
                elif failure in ['negative', 'float']:
                    rows[0]['systems']['local']['word_errors'] = -1 if failure == 'negative' else .5
                elif failure == 'zero':
                    rows[0]['systems']['local']['reference_words'] = 0
                elif failure == 'unknown_video':
                    rows[0]['video_id'] = 'unknown'
                else:
                    rows[1]['video_id'] = 'v'
                with self.assertRaises(ValueError):
                    if failure == 'cross_channel':
                        video_design(rows, SETTINGS)
                    else:
                        video_counts(rows, ['v', 'w'])

    def test_clip_wins_and_ties_are_not_the_corpus_gap(self):
        rows = [row('a', 'v', 'a', 1, 0, 1), row('b', 'v', 'a', 1, 1, 1), row('c', 'w', 'b', 10, 10, 0)]
        result = paired_clips(rows)['wer']
        self.assertEqual((result['local_lower_error'], result['tied'], result['api_lower_error']), (1, 1, 1))
        self.assertEqual(result['difference_pp']['mean'], 0)
        corpus = bootstrap_group(rows, ['v', 'w'], np.array([[1, 1]]), SETTINGS)
        self.assertAlmostEqual(corpus['local_minus_api_pp']['wer'], 75)


if __name__ == '__main__':
    unittest.main()
