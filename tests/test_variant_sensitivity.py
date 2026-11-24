"""Accepted renderings are explicit, clip-scoped and never fuzzy truth labels."""
import copy
from contextlib import redirect_stdout
import io
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch

from jiwer import process_words
import nbformat

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import variant_sensitivity as variant


def clip(number, reference='class', local='क्लास', api='class'):
    return {'number': number, 'clip_id': f'clip/{number}', 'published_reference': reference,
            'outputs': {'local': local, 'whisper_api': api}}


class VariantTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / 'variant_reviews.json'
        patched = patch.object(variant, 'ANNOTATIONS', self.path)
        patched.start()
        self.addCleanup(patched.stop)
        self.bundle = {'source_sha256': {'manifest': 'frozen'}, 'clips': [clip(1), clip(2)]}

    def test_script_and_spelling_variants_need_explicit_approval(self):
        self.assertEqual(variant.variant_counts('आज class छ', 'आज क्लास छ', set())['word_errors'], 1)
        accepted = variant.variant_counts('आज class छ', 'आज क्लास छ', {('class', 'क्लास')})
        self.assertEqual(accepted['word_errors'], 0)
        self.assertEqual(accepted['approved_variant_matches'], 1)
        self.assertEqual(variant.variant_counts('sanskar', 'sonskar', set())['word_errors'], 1)
        self.assertEqual(variant.variant_counts('sanskar', 'sonskar', {('sanskar', 'sonskar')})['word_errors'], 0)

    def test_similar_words_synonyms_inflections_and_transitive_aliases_are_not_automatic(self):
        for ref, hyp in [('cat', 'cut'), ('task', 'tasks'), ('large', 'big'), ('कर', 'घर')]:
            self.assertEqual(variant.variant_counts(ref, hyp, set())['word_errors'], 1)
        self.assertEqual(variant.variant_counts('foo', 'baz', {('foo', 'bar'), ('bar', 'baz')})['word_errors'], 1)

    def test_insertions_deletions_and_large_wer_remain_counted(self):
        result = variant.variant_counts('class today', 'क्लास extra extra extra', {('class', 'क्लास')})
        self.assertEqual(result['word_errors'], 3)
        self.assertEqual(result['wer'], 1.5)
        self.assertEqual(variant.variant_counts('class today', '', {('class', 'क्लास')})['deletions'], 2)
        with self.assertRaises(ValueError):
            variant.variant_counts('', 'extra', set())
        with self.assertRaises(ValueError):
            variant.variant_counts('program counter', 'one', {('program counter', 'one')})

    def test_distance_realigns_and_agrees_with_standard_edit_distance_when_unapproved(self):
        rng = random.Random(42)
        for _ in range(60):
            ref = ' '.join(rng.choices(['a', 'b', 'c'], k=rng.randint(1, 8)))
            hyp = ' '.join(rng.choices(['a', 'b', 'c'], k=rng.randint(0, 10)))
            strict = variant.variant_counts(ref, hyp, set())
            expected = process_words(ref, hyp)
            self.assertEqual(strict['word_errors'], expected.substitutions+expected.deletions+expected.insertions)
            relaxed = variant.variant_counts(ref, hyp, {('a', 'b')})
            self.assertLessEqual(relaxed['word_errors'], strict['word_errors'])

    def test_duplicate_pair_occurrences_are_reviewed_once_within_a_clip(self):
        rows = variant.candidates(clip(1, 'class class', 'क्लास क्लास', 'क्लास class'))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['occurrences'], {'local': 2, 'whisper_api': 1})

    def test_unreviewed_scores_are_provisional_and_approval_does_not_leak_to_other_clips(self):
        state = variant.load_reviews(self.bundle)
        initial = variant.analyze(self.bundle, state)
        self.assertFalse(initial['review_complete'])
        self.assertEqual(initial['pair_decision_counts'], {'pending': 2})
        variant.save_decisions(self.bundle, 1, 'reviewer', True, {1: 'same'})
        result = variant.analyze(self.bundle, variant.load_reviews(self.bundle))
        local = result['systems']['local']
        self.assertEqual(local['strict']['word_errors'], 2)
        self.assertEqual(local['approved_variants_only']['word_errors'], 1)
        self.assertEqual(result['fully_reviewed_clips'], 1)
        self.assertFalse(result['review_complete'])
        self.assertEqual(result['strict_alignment_substitution_occurrences']['local'], {'same': 1, 'pending': 1})

    def test_resuming_preserves_previous_decisions_and_history(self):
        first = variant.save_decisions(self.bundle, 1, 'reviewer', True, {1: 'same'})
        variant.save_decisions(self.bundle, 1, 'reviewer', True, {1: 'pending'})
        state = variant.load_reviews(self.bundle)
        self.assertEqual(state['reviews'][0]['decisions'], {'1': 'same'})
        self.assertEqual(state['history'][0], first)

    def test_unheard_invalid_or_changed_provenance_cannot_be_accepted(self):
        variant.load_reviews(self.bundle)
        before = self.path.read_bytes()
        for number, listened, decisions in [(True, True, {1: 'same'}), (1, False, {1: 'same'}),
                                            (1, True, {1: 'pending'}), (1, True, {9: 'same'}),
                                            (1, True, {1: 'similar'}), (1, True, {True: 'same'})]:
            with self.subTest(decisions=decisions), self.assertRaises(ValueError):
                variant.save_decisions(self.bundle, number, 'reviewer', listened, decisions)
            self.assertEqual(self.path.read_bytes(), before)
        changed = copy.deepcopy(self.bundle)
        changed['source_sha256']['manifest'] = 'changed'
        with self.assertRaises(ValueError):
            variant.load_reviews(changed)
        state = variant.load_reviews(self.bundle)
        state['reviews'][0]['decisions']['1'] = 'same'
        with self.assertRaises(ValueError):
            variant.analyze(self.bundle, state)

    def test_unsure_and_reference_issues_are_counted_but_not_forgiven(self):
        variant.save_decisions(self.bundle, 1, 'reviewer', True, {1: 'unsure'})
        variant.save_decisions(self.bundle, 2, 'reviewer', True, {1: 'reference_issue'})
        result = variant.analyze(self.bundle, variant.load_reviews(self.bundle))
        self.assertTrue(result['review_complete'])
        self.assertEqual(result['systems']['local']['edit_reduction_under_approved_variants'], 0)
        self.assertEqual(result['strict_alignment_substitution_occurrences']['local'], {'unsure': 1, 'reference_issue': 1})

    def test_invalid_choice_identifies_the_pair_and_preserves_saved_work(self):
        variant.load_reviews(self.bundle)
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "pair 1='smae'"):
            variant.save_decisions(self.bundle, 1, 'reviewer', True, {1: 'smae'})
        self.assertEqual(self.path.read_bytes(), before)

    def test_missing_extra_or_string_ids_have_specific_messages(self):
        variant.load_reviews(self.bundle)
        for decisions, message in [({}, 'missing pair IDs: 1'), ({2: 'same'}, 'unexpected pair IDs: 2'),
                                   ({'1': 'same'}, 'Pair IDs must be integers')]:
            with self.subTest(decisions=decisions), self.assertRaisesRegex(ValueError, message):
                variant.save_decisions(self.bundle, 1, 'reviewer', True, decisions)

    def test_notebook_is_noninteractive_code_safe_and_preserves_existing_file(self):
        (self.root / 'notebooks').mkdir()
        with patch.object(variant, 'ROOT', self.root):
            path = variant.prepare_notebook(self.bundle)
            nb = nbformat.read(path, as_version=4)
            nbformat.validate(nb)
            for cell in nb.cells:
                if cell.cell_type == 'code':
                    compile(cell.source, '<variant-cell>', 'exec')
            text = '\n'.join(c.source for c in nb.cells)
            self.assertIn("1: 'pending'", text)
            self.assertNotIn('input(', text)
            self.assertIn('listened = False', text)
            before = path.read_bytes()
            variant.prepare_notebook(self.bundle)
            self.assertEqual(path.read_bytes(), before)

    def test_completed_export_does_not_claim_reference_issues_are_validated_errors(self):
        variant.save_decisions(self.bundle, 1, 'reviewer', True, {1: 'same'})
        variant.save_decisions(self.bundle, 2, 'reviewer', True, {1: 'reference_issue'})
        (self.root / 'results/metrics').mkdir(parents=True)
        (self.root / 'reports').mkdir()
        before = self.path.read_bytes()
        with patch.object(variant, 'ROOT', self.root), redirect_stdout(io.StringIO()):
            result = variant.export_results(self.bundle)
        text = (self.root / 'reports/variant_sensitivity_20261122.md').read_text(encoding='utf-8')
        self.assertTrue(result['review_complete'])
        self.assertIn('All pair decisions have been saved', text)
        self.assertIn('Reference/alignment-issue pairs: 1', text)
        self.assertIn('Accepted pairs for transparency', text)
        self.assertNotIn('At preparation, no variants are approved', text)
        self.assertEqual(self.path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
