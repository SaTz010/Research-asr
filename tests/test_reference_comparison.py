"""Reference sensitivity keeps paired predictions fixed and aggregates real edits."""
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from compare_audited_references import compare_subset, markdown_report, text_scores


def fixture():
    entries = [{'identity': {'clip_id': 'a', 'transcription': 'one', 'cmi': 0}},
               {'identity': {'clip_id': 'b', 'transcription': 'four', 'cmi': 0}}]
    reviews = [{'number': 1, 'clip_id': 'a', 'corrected_reference': 'one two three', 'verdict': 'corrected', 'audited_cmi': 0, 'notes': 'Added spoken words.'},
               {'number': 2, 'clip_id': 'b', 'corrected_reference': 'four', 'verdict': 'match', 'audited_cmi': 0, 'notes': ''}]
    predictions = {system: {entry['identity']['clip_id']: {'status': 'received', 'transcription': entry['identity']['transcription'], 'hypothesis': hyp}
                           for entry, hyp in zip(entries, hypotheses)}
                   for system, hypotheses in [('local', ['one two three', '']), ('whisper_api', ['', 'four'])]}
    return entries, reviews, predictions


class ReferenceComparisonTests(unittest.TestCase):
    def test_corpus_weighting_denominators_and_score_changes_can_have_either_sign(self):
        args = fixture()
        before = copy.deepcopy(args)
        result = compare_subset(*args)
        self.assertEqual(args, before)
        self.assertEqual(result['exact_text_changed_clips'], 1)
        self.assertEqual(result['reference_disagreement']['word_errors'], 2)
        self.assertEqual(result['reference_disagreement']['reference_words'], 4)
        self.assertEqual(result['reference_disagreement']['wer'], 0.5)
        local = result['systems']['local']
        self.assertEqual(local['published']['wer'], 1.5)
        self.assertEqual(local['corrected']['wer'], 0.25)
        self.assertEqual(local['published']['reference_words'], 2)
        self.assertEqual(local['corrected']['reference_words'], 4)
        self.assertLess(local['corrected_minus_published_percentage_points']['wer'], 0)
        self.assertGreater(result['systems']['whisper_api']['corrected_minus_published_percentage_points']['wer'], 0)

    def test_normalization_only_edit_and_source_cmi_rounding_are_not_substantive_changes(self):
        entries, reviews, predictions = fixture()
        entries[0]['identity'].update(transcription='One!', cmi=33.33)
        reviews[0].update(corrected_reference='one', audited_cmi=100/3)
        for saved in predictions.values():
            saved['a']['transcription'] = 'One!'
        result = compare_subset(entries, reviews, predictions)
        self.assertEqual(result['exact_text_changed_clips'], 1)
        self.assertEqual(result['normalized_text_changed_clips'], 0)
        self.assertEqual(result['cmi_changed_beyond_rounding_clips'], 0)
        self.assertEqual(result['reference_disagreement']['wer'], 0)
        self.assertGreater(result['reference_disagreement']['raw_wer'], 0)
        self.assertEqual(text_scores('नेपालमा १२ class छन्।', 'नेपालमा 12 class छन्')['wer'], 0)

    def test_tag_only_cmi_change_keeps_reference_scores_unchanged(self):
        entries, reviews, predictions = fixture()
        reviews[0].update(corrected_reference='one', verdict='match', audited_cmi=50)
        result = compare_subset(entries, reviews, predictions)
        self.assertEqual(result['exact_text_changed_clips'], 0)
        self.assertEqual(result['cmi_band_changed_numbers'], [1])
        self.assertEqual(result['cmi_changed_beyond_rounding_clips'], 1)
        for scores in result['systems'].values():
            self.assertEqual(scores['published'], scores['corrected'])

    def test_missing_failed_duplicate_or_mispaired_inputs_are_rejected(self):
        for failure in ['missing', 'failed', 'reference', 'duplicate_selection', 'duplicate_review', 'unsure']:
            with self.subTest(failure=failure):
                entries, reviews, predictions = fixture()
                if failure == 'missing':
                    predictions['whisper_api'].pop('a')
                elif failure == 'failed':
                    predictions['whisper_api']['a']['status'] = 'api_error'
                elif failure == 'reference':
                    predictions['local']['a']['transcription'] = 'wrong pairing'
                elif failure == 'duplicate_selection':
                    entries[1] = entries[0]
                elif failure == 'duplicate_review':
                    reviews[1] = reviews[0]
                else:
                    reviews[0]['verdict'] = 'unsure'
                with self.assertRaises(ValueError):
                    compare_subset(entries, reviews, predictions)

    def test_readable_report_escapes_source_markup_and_does_not_edit_inputs(self):
        entries, reviews, predictions = fixture()
        unsafe = 'one|two <script>alert(1)</script>'
        entries[0]['identity']['transcription'] = unsafe
        for saved in predictions.values():
            saved['a']['transcription'] = unsafe
        result = compare_subset(entries, reviews, predictions)
        before = copy.deepcopy(result)
        report = markdown_report(result)
        self.assertEqual(result, before)
        self.assertIn('one\\|two', report)
        self.assertIn('&lt;script&gt;', report)
        self.assertNotIn('<script>', report)


if __name__ == '__main__':
    unittest.main()
