"""Reproduction must catch drift at any nested count/denominator, allowing tiny float roundoff."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from reproduce_results import compare


class ReproductionTests(unittest.TestCase):
    def test_nested_counts_types_and_coverage_cannot_drift(self):
        expected = {'clips': [{'words': 185, 'errors': 128, 'rate': 128/185}], 'complete': True}
        compare(copy.deepcopy(expected), expected)
        for changed in [{'clips': [], 'complete': True},
                        {'clips': [{'words': 186, 'errors': 128, 'rate': 128/185}], 'complete': True},
                        {'clips': expected['clips'], 'complete': 1}]:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                compare(changed, expected)

    def test_only_numerical_roundoff_is_tolerated(self):
        compare({'rate': .5+1e-14}, {'rate': .5})
        with self.assertRaises(ValueError):
            compare({'rate': .5001}, {'rate': .5})


if __name__ == '__main__':
    unittest.main()
