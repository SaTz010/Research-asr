"""Public-test candidates must never become invented training exclusions."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from audit_codemix_training_overlap import match_public_test, source_split_overlap


def entry(text='Hello world', duration=1):
    return {'identity': {'clip_id': 'test/v/0-1000', 'transcription': text,
                         'decoded_duration_s': duration, 'video_id': 'v',
                         'start_ms': 0, 'end_ms': 1000, 'speaker_id': 'channel'}}


class OverlapAuditTests(unittest.TestCase):
    def test_normalized_text_and_duration_candidate_does_not_claim_training_exclusion(self):
        result = match_public_test([entry()], [{'id': 'alias', 'reference': 'hello, WORLD!', 'duration_s': 1.0005}])[0]
        self.assertEqual(result['evidence'], 'unique_public_test_candidate')
        self.assertEqual(result['public_test_ids'], ['alias'])
        self.assertIn('unverified', result['training_membership'])

    def test_number_rewriting_and_duration_mismatch_are_not_fuzzy_matched(self):
        for public in [{'id': 'alias', 'reference': 'one', 'duration_s': 1},
                       {'id': 'alias', 'reference': '1', 'duration_s': 1.01}]:
            self.assertEqual(match_public_test([entry('1')], [public])[0]['evidence'], 'no_exact_public_test_candidate')

    def test_ambiguous_and_invalid_public_rows_rejected_or_retained_honestly(self):
        rows = [{'id': 'a', 'reference': 'hello world', 'duration_s': 1},
                {'id': 'b', 'reference': 'hello world', 'duration_s': 1}]
        self.assertEqual(match_public_test([entry()], rows)[0]['evidence'], 'ambiguous_public_test_candidates')
        with self.assertRaises(ValueError): match_public_test([entry()], rows + [rows[0]])
        with self.assertRaises(ValueError): match_public_test([entry()], [{'id': 'a', 'reference': 'x', 'duration_s': float('nan')}])

    def test_source_split_membership_is_separate_from_author_training(self):
        manifest = {'dataset': {'revision': 'fixed'}, 'clips': [entry()]}
        identity = entry()['identity']
        metadata = {'revision': 'fixed', 'shards': [{'split': 'test', 'rows': [identity]},
                                                   {'split': 'train', 'rows': [{**identity, 'video_id': 'different', 'speaker_id': 'different'}]}]}
        result = source_split_overlap(manifest, metadata)
        self.assertEqual(result['test']['exact_clip_key_overlap'], 1)
        self.assertEqual(result['train']['exact_clip_key_overlap'], 0)
        self.assertEqual(result['train']['shared_channel_ids'], [])
        metadata['revision'] = 'other'
        with self.assertRaises(ValueError): source_split_overlap(manifest, metadata)


if __name__ == '__main__':
    unittest.main()
