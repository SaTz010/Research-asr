"""Held-out data eligibility, deterministic selection and honest human review state."""
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from budget import cmi_band
from prepare_test_set import (BANDS, build_review_notebook, exclude_audio_duplicates,
                              frozen_write, metadata_audit, select_audit)
from asr_common import normalize_text
from reference_audit import save_review, suggest_language_tags, tagged_cmi


def row(video='v', start=0, split='test', **changes):
    value = {'split': split, 'speech_type': 'cs', 'video_id': video, 'speaker_id': 'channel',
             'start_ms': start, 'end_ms': start + 3000, 'duration_s': 3., 'cmi': 25.,
             'reference_words': 4, 'reference_sha256': video + str(start),
             'source_file': split + '.parquet', 'row_in_file': start}
    return dict(value, **changes)


class TestPreparationTests(unittest.TestCase):
    def test_metadata_missing_duplicate_overlap_invalid_and_shared_channel(self):
        good = row('good')
        missing = row('bad', video_id=None)
        duplicate = row('duplicate')
        interval = row('overlap', start=1000)
        other = row('overlap', split='validation')
        malformed = row('malformed', cmi=True, duration_s=float('nan'))
        eligible, excluded, flags = metadata_audit([good, missing, duplicate, copy.deepcopy(duplicate), interval, other, malformed])
        self.assertEqual(eligible, [good])
        self.assertEqual(len(excluded), 5)
        self.assertIn('cross_split_interval_overlap', excluded[3]['reasons'])
        self.assertIn('invalid_cmi', excluded[4]['reasons'])
        self.assertEqual(flags[0]['flags'], ['shared_source_channel'])
        self.assertEqual(json.loads(json.dumps(excluded)), excluded)

    def test_touching_intervals_are_allowed_but_within_test_overlap_is_not(self):
        a, b = row(start=0), row(start=3000)
        self.assertEqual(len(metadata_audit([a, b])[0]), 2)
        self.assertEqual(len(metadata_audit([a, row(start=2999)])[0]), 0)

    def test_audio_duplicates_excluded_together(self):
        entries = [{'identity': {'clip_id': str(i), 'audio_sha256': checksum}} for i, checksum in enumerate(['a', 'b', 'a'])]
        retained, excluded = exclude_audio_duplicates(entries)
        self.assertEqual([e['identity']['clip_id'] for e in retained], ['1'])
        self.assertEqual(len(excluded), 2)
        self.assertEqual(excluded[0]['matching_clip_ids'], ['0', '2'])

    def test_audit_seed_balance_interleaving_and_input_order_independence(self):
        entries = [{'identity': {'clip_id': f'{band}/{i}', 'cmi': cmi,
                                'speaker_id': str(i % 2), 'video_id': str(i % 10)}}
                   for band, cmi in enumerate([5, 15, 25, 35, 45]) for i in range(30)]
        chosen = select_audit(entries)
        self.assertEqual(chosen, select_audit(list(reversed(entries))))
        self.assertEqual(len({e['identity']['clip_id'] for e in chosen}), 50)
        for session in [chosen[:25], chosen[25:]]:
            self.assertEqual(Counter(cmi_band(e['identity']['cmi']) for e in session), Counter({b: 5 for b in BANDS}))
        self.assertEqual(Counter(e['identity']['speaker_id'] for e in chosen), Counter({'0': 25, '1': 25}))
        with self.assertRaises(ValueError):
            select_audit(entries[:5])

    def test_frozen_artifacts_reuse_but_refuse_changed_data(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'frozen.json'
            frozen_write(path, {'x': 1})
            before = path.read_bytes()
            frozen_write(path, {'x': 1})
            self.assertEqual(path.read_bytes(), before)
            with self.assertRaises(ValueError):
                frozen_write(path, {'x': 2})
            self.assertEqual(path.read_bytes(), before)

    def test_cmi_ignores_other_and_does_not_guess_ambiguity(self):
        self.assertEqual(tagged_cmi('म आज online class मा छु 25', ['ne', 'ne', 'en', 'en', 'ne', 'ne', 'other']), 100 * 2 / 6)
        self.assertIsNone(tagged_cmi('word', ['ambiguous']))
        self.assertIsNone(tagged_cmi('25', ['other']))
        self.assertEqual(tagged_cmi('hello', ['en']), 0)
        for tags in [[], ['bad'], ['en', 'ne']]:
            with self.assertRaises(ValueError):
                tagged_cmi('word', tags)

    def test_suggestions_follow_normalized_tokens_and_flag_mixed_or_unknown_scripts(self):
        self.assertEqual(suggest_language_tags('म आज online-class मा छु २५ +'),
                         ['ne', 'ne', 'en', 'en', 'ne', 'ne', 'other', 'other'])
        self.assertEqual(suggest_language_tags('onlineमा 漢字 नमस्ते hello'),
                         ['ambiguous', 'ambiguous', 'ne', 'en'])
        # Script suggestions deliberately cannot resolve lexical language in transliteration.
        self.assertEqual(suggest_language_tags('अनलाइन namaste'), ['ne', 'en'])
        self.assertEqual(suggest_language_tags(''), [])

    def test_manual_review_validates_pairing_preserves_original_and_previous_decisions(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'data/manifests').mkdir(parents=True)
            (root / 'data/annotations').mkdir()
            selection = root / 'data/manifests/reference_audit_20261105_selection.json'
            selection.write_text(json.dumps({'clips': [{'identity': {'clip_id': 'test/id/0-3000', 'transcription': 'hello'}}]}))
            path = root / 'data/annotations/reference_audit_20261105.json'
            frozen_write(path, {'selection_sha256': hashlib.sha256(selection.read_bytes()).hexdigest(), 'frozen': False,
                                'reviews': [{'number': 1, 'clip_id': 'test/id/0-3000', 'verdict': 'pending'}]})
            with self.assertRaises(ValueError):
                save_review(path, 1, 'changed', ['en'], 'match')
            with self.assertRaises(ValueError):
                save_review(path, 1, None, [], 'match')
            self.assertEqual(save_review(path, 1, 'hello', ['en'], 'match')['reviewed'], 1)
            save_review(path, 1, 'class', ['en'], 'corrected')
            state = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(state['previous_reviews'][0]['corrected_reference'], 'hello')
            self.assertEqual(json.loads(selection.read_text())['clips'][0]['identity']['transcription'], 'hello')
            self.assertEqual(state['reviews'][0]['tagging_method'], 'manual')
            save_review(path, 1, 'नेपाली अनलाइन', ['ne', 'en'], 'corrected', tagging_method='script_suggestions_human_checked')
            state = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(state['reviews'][0]['token_languages'], ['ne', 'en'])
            self.assertEqual(state['reviews'][0]['suggested_token_languages'], ['ne', 'ne'])
            self.assertEqual(state['reviews'][0]['tagging_method'], 'script_suggestions_human_checked')
            with self.assertRaisesRegex(ValueError, 'Unknown tagging method'):
                save_review(path, 1, 'hello', ['en'], 'match', tagging_method='automatic_verified')
            state['frozen'] = True
            frozen_write(root / 'frozen-copy.json', state)
            path.write_text(json.dumps(state))
            with self.assertRaises(ValueError):
                save_review(path, 1, 'hello', ['en'], 'match')

    def test_review_notebook_compiles_without_predictions_or_executed_cells(self):
        notebook = build_review_notebook({'clips': [{}] * 50})
        code = [c for c in notebook['cells'] if c['cell_type'] == 'code']
        for c in code:
            self.assertIsNone(c['execution_count'])
            self.assertEqual(c['outputs'], [])
            compile(''.join(c['source']), '<review>', 'exec')
        source = '\n'.join(''.join(c['source']) for c in code)
        self.assertNotIn('predictions', source)
        self.assertEqual(source.count("verdict = 'pending'"), 50)

    def test_assisted_notebook_requires_human_confirmation_and_saves_only_selected_draft(self):
        selection = {'clips': [{'identity': {'transcription': 'अनलाइन class'}}]}
        notebook = build_review_notebook(selection, assisted=True)
        code = [''.join(c['source']) for c in notebook['cells'] if c['cell_type'] == 'code']
        for source in code:
            compile(source, '<assisted-review>', 'exec')
        environment = {'drafts': {}, 'suggest_language_tags': suggest_language_tags,
                       'normalize_text': normalize_text, 'save_review': Mock(), 'progress_path': Path('not-used')}
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            exec(code[2], environment)
            environment['drafts'][2] = ('a different clip', ['en'] * 3)
            exec(code[3], environment)
            environment['save_review'].assert_not_called()
            save_code = code[3].replace("verdict = 'pending'", "verdict = 'match'")
            with self.assertRaisesRegex(ValueError, 'Check all tag suggestions'):
                exec(save_code, environment)
            environment['save_review'].assert_not_called()
            with self.assertRaisesRegex(ValueError, 'word numbers'):
                exec(code[3].replace('tag_overrides = {}', "tag_overrides = {0: 'en'}"), environment)
            save_code = save_code.replace('tags_reviewed = False', 'tags_reviewed = True').replace('tag_overrides = {}', "tag_overrides = {1: 'en'}")
            exec(save_code, environment)
        environment['save_review'].assert_called_once_with(Path('not-used'), 1, 'अनलाइन class', ['en', 'en'], 'match', '',
                                                          tagging_method='script_suggestions_human_checked')


if __name__ == '__main__':
    unittest.main()
