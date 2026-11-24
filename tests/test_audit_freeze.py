"""Audit freeze refuses incomplete/inconsistent records and preserves human work."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from reference_audit import freeze_validated_audit, save_review, validate_reviews


class AuditFreezeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'reviews.json'
        self.pool = self.root / 'pool.json'
        self.selection_path = self.root / 'selection.json'
        self.pool.write_text('{}', encoding='utf-8')
        self.selection = {'evaluation_manifest_sha256': hashlib.sha256(self.pool.read_bytes()).hexdigest(),
                          'clips': [{'identity': {'clip_id': str(i), 'transcription': 'class'}} for i in range(1, 51)]}
        self.selection_path.write_text(json.dumps(self.selection), encoding='utf-8')
        self.state = {'reviewer': None, 'frozen': False, 'selection_sha256': hashlib.sha256(self.selection_path.read_bytes()).hexdigest(),
                      'reviews': [{'number': i, 'clip_id': str(i), 'verdict': 'match', 'corrected_reference': 'class',
                                   'token_languages': ['en'], 'normalized_tokens': ['class'], 'audited_cmi': 0,
                                   'notes': '', 'reviewed_at_utc': '2026-11-12T00:00:00+00:00',
                                   'tagging_method': 'script_suggestions_human_checked', 'suggested_token_languages': ['en']}
                                  for i in range(1, 51)]}
        self.path.write_text(json.dumps(self.state), encoding='utf-8')

    def freeze(self):
        return freeze_validated_audit(self.path, self.selection_path, self.pool, 'researcher_1')

    def test_freeze_preserves_exact_backup_and_reviews_is_idempotent_and_blocks_notebook_save(self):
        before = self.path.read_bytes()
        snapshot, summary = self.freeze()
        self.assertEqual(summary['reviewed_clips'], 50)
        self.assertEqual(snapshot.read_bytes(), self.path.read_bytes())
        frozen = json.loads(snapshot.read_text(encoding='utf-8'))
        self.assertEqual(frozen['reviews'], self.state['reviews'])
        self.assertEqual(frozen['reviewer'], 'researcher_1')
        self.assertEqual(frozen['pre_freeze_sha256'], hashlib.sha256(before).hexdigest())
        self.assertEqual(next(self.root.glob('*_pre_freeze.json')).read_bytes(), before)
        self.assertEqual(self.freeze(), (snapshot, summary))
        with self.assertRaisesRegex(ValueError, 'Audit is frozen'):
            save_review(self.path, 1, 'class', ['en'], 'match')

    def test_invalid_records_fail_without_writing_backup_or_snapshot(self):
        changes = [{'verdict': 'pending'}, {'verdict': 'unsure'}, {'audited_cmi': 25},
                   {'clip_id': 'wrong'}, {'normalized_tokens': ['wrong']}, {'verdict': 'corrected'},
                   {'suggested_token_languages': ['ne']}, {'token_languages': ['ambiguous']},
                   {'reviewed_at_utc': '2026-11-12T00:00:00'}, {'tagging_method': 'automatic'}]
        for change in changes:
            with self.subTest(change=change):
                state = copy.deepcopy(self.state)
                state['reviews'][0].update(change)
                self.path.write_text(json.dumps(state), encoding='utf-8')
                before = self.path.read_bytes()
                with self.assertRaises(ValueError):
                    self.freeze()
                self.assertEqual(self.path.read_bytes(), before)
                self.assertFalse(list(self.root.glob('*_pre_freeze.json')))
        self.assertFalse(list(self.root.glob('*_frozen.json')))
        with self.assertRaises(ValueError):
            validate_reviews(dict(self.state, reviews=self.state['reviews'][:-1]), self.selection)

    def test_changed_pool_selection_or_backup_is_not_overwritten(self):
        self.pool.write_text('{"changed":true}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Evaluation pool differs'):
            self.freeze()
        self.assertFalse(list(self.root.glob('*_frozen.json')))
        self.pool.write_text('{}', encoding='utf-8')
        snapshot, _ = self.freeze()
        snapshot.write_text('{}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Frozen audit differs'):
            self.freeze()

    def test_tag_only_corrections_do_not_require_corrected_transcript_verdict(self):
        state = copy.deepcopy(self.state)
        state['reviews'][0].update(token_languages=['other'], audited_cmi=None)
        with self.assertRaisesRegex(ValueError, 'CMI'):
            validate_reviews(state, self.selection)
        state['reviews'][0].update(token_languages=['ne'], audited_cmi=0)
        self.assertEqual(validate_reviews(state, self.selection)['reviews_with_tag_overrides'], [1])


if __name__ == '__main__':
    unittest.main()
