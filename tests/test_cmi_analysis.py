"""CMI reporting preserves corpus weighting, fixed bins and paired reference versions."""
import copy
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from analyze_cmi import audit_rows, bands, build_rows, duration_groups, rho, summarize
from compare_audited_references import compare_subset, text_scores
from test_reference_comparison import fixture


def row(key, ref, hyp, cmi, duration=10, channel='a', video='v'):
    return {'clip_id': key, 'video_id': video, 'channel': channel, 'cmi': cmi, 'duration_s': duration,
            'systems': {s: text_scores(ref, hyp) for s in ['local', 'whisper_api']}}


class CmiAnalysisTests(unittest.TestCase):
    def test_corpus_weighting_empty_hypotheses_and_insertions(self):
        rows = [row('a', 'one', 'one two three', 0), row('b', 'one two three', '', 50)]
        result = summarize(rows)
        self.assertEqual(result['systems']['local']['word_errors'], 5)
        self.assertEqual(result['systems']['local']['reference_words'], 4)
        self.assertEqual(result['systems']['local']['wer'], 1.25)
        self.assertNotEqual(result['systems']['local']['wer'], np.mean([2, 1]))
        self.assertIsNone(summarize([])['systems']['local'])

    def test_frozen_band_boundaries_include_each_clip_once(self):
        rows = [row(str(i), 'one', '', cmi) for i, cmi in enumerate([0, 10, 10.001, 20, 20.001, 30, 30.001, 40, 40.001, 50])]
        before = copy.deepcopy(rows)
        grouped = bands(rows)
        self.assertEqual([g['clips'] for g in grouped.values()], [2] * 5)
        self.assertEqual(sum(g['systems']['local']['word_errors'] for g in grouped.values()), 10)
        self.assertEqual(rows, before)
        with self.assertRaises(ValueError):
            bands([row('bad', 'one', '', 50.01)])

    def test_spearman_ranks_ties_constants_and_nonfinite_rejection(self):
        self.assertAlmostEqual(rho([1, 2, 3], [3, 2, 1]), -1)
        self.assertAlmostEqual(rho([1, 1, 2], [1, 2, 3]), np.sqrt(3) / 2)
        self.assertIsNone(rho([1, 1, 1], [1, 2, 3]))
        self.assertIsNone(rho([1, 2], [1, 2]))
        for x, y in [([1], []), ([1, float('nan'), 3], [1, 2, 3])]:
            with self.assertRaises(ValueError):
                rho(x, y)

    def test_duration_quantile_ties_do_not_drop_observations(self):
        rows = [row(str(i), 'one', '', 0, duration=d) for i, d in enumerate([1, 1, 1, 1, 2, 2, 2, 2])]
        result = duration_groups(rows)
        self.assertEqual(result['cutpoints_s'], [1, 1.5, 2])
        self.assertEqual([g['clips'] for g in result['groups'].values()], [4, 0, 4, 0])
        self.assertEqual(sum(g['clips'] for g in result['groups'].values()), 8)

    def test_channel_and_video_units_are_distinct(self):
        rows = [row('a', 'one', '', 10), row('b', 'one two', 'one', 20, channel='b', video='w'),
                row('c', 'one two three', 'one', 30, channel='b', video='w')]
        result = summarize(rows)
        self.assertEqual(result['channels'], {'a': 1, 'b': 2})
        self.assertEqual(result['videos'], 2)
        self.assertEqual(result['systems']['local']['reference_words'], 6)
        self.assertAlmostEqual(result['spearman']['cmi_vs_local_minus_api_wer'] or 0, 0)

    def test_audit_rebinning_uses_the_paired_reference_version(self):
        entries, reviews, predictions = fixture()
        for i, entry in enumerate(entries):
            entry['identity'].update(video_id='v', speaker_id='c', duration_s=10)
            reviews[i]['audited_cmi'] = 50
        rows = build_rows({'clips': entries}, predictions)
        comparison = compare_subset(entries, reviews, predictions)
        original = audit_rows(comparison, rows, 'published')
        corrected = audit_rows(comparison, rows, 'corrected')
        self.assertEqual(bands(original)['[0,10]']['clips'], 2)
        self.assertEqual(bands(corrected)['(40,50]']['clips'], 2)
        self.assertEqual(summarize(original)['systems']['local']['reference_words'], 2)
        self.assertEqual(summarize(corrected)['systems']['local']['reference_words'], 4)
        self.assertEqual(original[0]['clip_id'], corrected[0]['clip_id'])

    def test_full_analysis_rejects_failed_outputs(self):
        entries, _, predictions = fixture()
        entries[0]['identity'].update(video_id='v', speaker_id='c', duration_s=10)
        predictions['local']['a']['status'] = 'failed'
        with self.assertRaises(ValueError):
            build_rows({'clips': entries}, predictions)


if __name__ == '__main__':
    unittest.main()
