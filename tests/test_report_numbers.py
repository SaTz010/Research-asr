"""Report building must reject changed scores, signs and stale verified results."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import build_research_report as report


class ReportNumberTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = report.SOURCE.read_text(encoding='utf-8')

    def test_current_report_matches_verified_results(self):
        report.verify_numbers(self.text)

    def test_plain_language_summary_must_match_the_full_benchmark(self):
        original = '| Local Whisper Large V2 | 90.95% | 69.60% |'
        self.assertIn(original, self.text)
        with self.assertRaisesRegex(ValueError, 'summary scores'):
            report.verify_numbers(self.text.replace(original, original.replace('90.95%', '90.00%')))

    def test_reader_structure_requires_contents_and_glossary(self):
        for original in ['<!-- contents -->', '## Appendix C Glossary and how to read the scores']:
            with self.subTest(original=original), self.assertRaises(ValueError):
                report.verify_structure(self.text.replace(original, ''))

    def test_visible_long_revision_ids_are_excluded_from_main_text(self):
        report.verify_structure(self.text)
        with self.assertRaisesRegex(ValueError, 'technical appendix'):
            report.verify_structure(self.text.replace('## Abstract',
                '## Abstract\n\nDataset revision: dd00ca41dd38774cd6097c372c16939d7f3746df'))

    def test_changed_interval_or_difference_sign_is_rejected(self):
        original = '| -5.46 | [-9.79, -2.31] |'
        self.assertIn(original, self.text)
        for changed in ['| -5.46 | [-9.79, +2.31] |', '| +5.46 | [-9.79, -2.31] |']:
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, 'uncertainty table'):
                report.verify_numbers(self.text.replace(original, changed))

    def test_changed_reference_sensitivity_interval_is_rejected(self):
        original = '+6.23 pp with corrected references, interval [-9.21, +24.75]'
        self.assertIn(original, self.text)
        with self.assertRaisesRegex(ValueError, 'audit interval'):
            report.verify_numbers(self.text.replace(original, original.replace('-9.21', '-0.21')))

    def test_changed_band_score_is_rejected(self):
        original = '| 90.22% | 93.61% |'
        self.assertIn(original, self.text)
        with self.assertRaisesRegex(ValueError, 'band table'):
            report.verify_numbers(self.text.replace(original, '| 0.00% | 93.61% |'))

    def test_changed_variant_score_is_rejected(self):
        original = '| 128 / 185 | 69.19% |'
        self.assertIn(original, self.text)
        with self.assertRaisesRegex(ValueError, 'variant score table'):
            report.verify_numbers(self.text.replace(original, '| 128 / 185 | 67.57% |'))

    def test_changed_qualitative_count_or_variant_decision_count_is_rejected(self):
        for original, changed, message in [
            ('| Script or spelling difference | 6 | 5 |', '| Script or spelling difference | 7 | 5 |', 'category table'),
            ('Current decisions are 31 same,', 'Current decisions are 37 same,', 'decision counts'),
        ]:
            self.assertIn(original, self.text)
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, message):
                report.verify_numbers(self.text.replace(original, changed))

    def test_changed_annotations_require_matching_follow_up_verification(self):
        original_read = Path.read_bytes
        target = report.ROOT / 'data/annotations/word_variants_20261122.json'

        def modified_read(path):
            return b'{}' if path == target else original_read(path)

        with patch.object(Path, 'read_bytes', modified_read), self.assertRaisesRegex(ValueError, 'diagnostic inputs'):
            report.verify_numbers(self.text)

    def test_recomputed_variant_date_is_allowed_but_changed_counts_are_rejected(self):
        original_read = Path.read_bytes
        target = report.ROOT / 'results/metrics/variant_sensitivity_20261122.json'
        saved = json.loads(original_read(target))
        saved['computed_on'] = '2099-01-01'

        def modified_read(path):
            return json.dumps(saved).encode('utf-8') if path == target else original_read(path)

        with patch.object(Path, 'read_bytes', modified_read):
            report.verify_numbers(self.text)
            saved['systems']['local']['approved_variants_only']['word_errors'] += 1
            with self.assertRaisesRegex(ValueError, 'diagnostic inputs'):
                report.verify_numbers(self.text)

    def test_changed_result_file_requires_matching_independent_verification(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = root / 'results/metrics'
            folder.mkdir(parents=True)
            for filename in ['cmi_analysis_20261116.json', 'paired_uncertainty_20261119.json',
                             'paired_uncertainty_20261119_verified.json', 'audited_reference_comparison_20261116.json']:
                shutil.copyfile(report.ROOT / 'results/metrics' / filename, folder / filename)
            target = folder / 'paired_uncertainty_20261119.json'
            saved = json.loads(target.read_bytes())
            saved['overall']['interval_95_pp']['wer'][1] = 0
            target.write_text(json.dumps(saved), encoding='utf-8')
            with patch.object(report, 'ROOT', root), self.assertRaisesRegex(ValueError, 'verified uncertainty'):
                report.verify_numbers(self.text)


if __name__ == '__main__':
    unittest.main()
