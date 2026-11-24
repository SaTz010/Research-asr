"""Listening decisions stay separate, require evidence and preserve previous work."""
from contextlib import redirect_stdout
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import shutil
import unittest
from unittest.mock import patch

import nbformat

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import error_example_review as review


class ErrorExampleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / 'reviews.json'
        self.patch = patch.object(review, 'REVIEWS', self.path)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.bundle = {'source_sha256': {'manifest': 'fixed'}, 'clips': [
            {'number': n, 'clip_id': str(n), 'cmi': cmi, 'published_reference': 'class',
             'outputs': {'local': 'class', 'whisper_api': 'class'}} for n, cmi in enumerate([5, 15], 1)]}

    def save(self, **changes):
        args = dict(bundle=self.bundle, number=1, reviewer='researcher', listened=True,
                    reference_assessment='matches_audio', reference_notes='',
                    local_categories=['no_clear_error'], local_notes='Heard class; output class matches.',
                    api_categories=['no_clear_error'], api_notes='Heard class; output class matches.')
        args.update(changes)
        return review.save_example(**args)

    def test_initialization_is_pending_and_reopening_preserves_saved_judgments(self):
        first = review.progress(self.bundle)
        self.assertEqual([r['status'] for r in first['reviews']], ['pending', 'pending'])
        self.save()
        before = self.path.read_bytes()
        reopened = review.progress(self.bundle)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(reopened['reviews'][0]['status'], 'reviewed')
        self.assertEqual(review.summary(self.bundle)['pending_numbers'], [2])

    def test_saved_text_reproduction_keeps_provenance_without_private_wavs(self):
        original_root = review.ROOT
        for name in ['configs/evaluation_protocol_20261112.json', 'reports/protocol_20261112.md']:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original_root / name, target)
        with patch.object(review, 'ROOT', self.root):
            bundle = review.load_examples(verify_audio=False)
            self.assertEqual(len(bundle['clips']), 10)
            self.assertFalse(bundle['audio_integrity_checked'])
            self.assertTrue(all(not c['audio_path'].exists() for c in bundle['clips']))
            with self.assertRaises(FileNotFoundError):
                review.load_examples()

    def test_unheard_unfilled_or_invalid_decisions_do_not_overwrite(self):
        review.progress(self.bundle)
        before = self.path.read_bytes()
        for changes in [dict(listened=False), dict(listened=1), dict(reference_assessment='pending'),
                        dict(local_categories=[]), dict(api_notes=''), dict(local_categories=['bad']),
                        dict(local_categories=['no_clear_error', 'wrong_word']),
                        dict(local_categories=['wrong_word', 'wrong_word']),
                        dict(reference_assessment='possible_reference_issue', reference_notes=''), dict(number=True)]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.save(**changes)
            self.assertEqual(self.path.read_bytes(), before)

    def test_edits_keep_history_and_uncertainty_is_explicit(self):
        first = self.save()
        second = self.save(reference_assessment='unsure', reference_notes='Word at end is inaudible.',
                           local_categories=['script_or_spelling_difference', 'uncertain'],
                           local_notes='Different script; cannot identify the last word.')
        state = review.progress(self.bundle)
        self.assertEqual(state['history'], [first])
        self.assertEqual(state['reviews'][0], second)
        self.assertEqual(review.summary(self.bundle)['uncertain_numbers'], [1])

    def test_input_drift_and_reviewer_changes_are_rejected(self):
        self.save()
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.save(reviewer='another researcher')
        changed = copy.deepcopy(self.bundle)
        changed['source_sha256']['manifest'] = 'changed'
        with self.assertRaises(ValueError):
            review.progress(changed)
        self.assertEqual(self.path.read_bytes(), before)

    def test_alignment_html_escapes_source_markup_and_never_classifies_speech(self):
        self.bundle['clips'][0]['published_reference'] = '<img src=x> class'
        with redirect_stdout(io.StringIO()), patch('IPython.display.display') as display:
            review.show_outputs(self.bundle, 1)
        html = '\n'.join(call.args[0].data for call in display.call_args_list)
        self.assertNotIn('<img', html)
        self.assertIn('&lt;img', html)
        self.assertFalse(self.path.exists())

    def test_notebook_cells_compile_and_existing_user_edits_are_preserved(self):
        (self.root / 'notebooks').mkdir()
        with patch.object(review, 'ROOT', self.root):
            path = review.prepare_notebook(self.bundle)
            notebook = nbformat.read(path, as_version=4)
            nbformat.validate(notebook)
            for cell in notebook.cells:
                if cell.cell_type == 'code':
                    compile(cell.source, '<review-cell>', 'exec')
            source = '\n'.join(c.source for c in notebook.cells)
            self.assertIn('listened = False', source)
            self.assertNotIn('input(', source)
            self.assertIn('show_audio(examples, 1)', source)
            edited = path.read_text(encoding='utf-8')+'\n'
            path.write_text(edited, encoding='utf-8')
            with redirect_stdout(io.StringIO()):
                review.prepare_notebook(self.bundle)
            self.assertEqual(path.read_text(encoding='utf-8'), edited)


if __name__ == '__main__':
    unittest.main()
