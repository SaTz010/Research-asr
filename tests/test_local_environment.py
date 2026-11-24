"""Check preservation of the real saved API baseline without CUDA or network."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from check_local_environment import verify_saved_baseline


class LocalSetupTests(unittest.TestCase):
    def test_real_baseline_is_preserved(self):
        baseline = verify_saved_baseline()
        self.assertEqual(baseline['clips'], 5)
        self.assertAlmostEqual(baseline['wer'], 81 / 111)
        self.assertAlmostEqual(baseline['cer'], 256 / 525)

    def test_altered_archive_is_rejected_before_parsing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'results/metrics').mkdir(parents=True)
            (root / 'results/predictions').mkdir()
            (root / 'results/metrics/whisper_api_pilot_20261022_verified.json').write_text(json.dumps({'source_sha256': '0' * 64}))
            (root / 'results/predictions/whisper_api_pilot_20261022T105623043636Z.zip').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'checksum differs'):
                verify_saved_baseline(root)

    def test_duplicate_prediction_cannot_replace_a_missing_clip(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'results/metrics').mkdir(parents=True)
            (root / 'results/predictions').mkdir()
            archive_path = root / 'results/predictions/whisper_api_pilot_20261022T105623043636Z.zip'
            with zipfile.ZipFile(ROOT / 'results/predictions' / archive_path.name) as archive:
                data = json.loads(archive.read('results.json'))
            rows = [row for row in data['predictions'] if row['mode'] == 'auto']
            data['predictions'] = rows[:4] + [rows[0]]
            with zipfile.ZipFile(archive_path, 'w') as archive:
                archive.writestr('results.json', json.dumps(data))
            (root / 'results/metrics/whisper_api_pilot_20261022_verified.json').write_text(
                json.dumps({'source_sha256': hashlib.sha256(archive_path.read_bytes()).hexdigest()}))
            with self.assertRaisesRegex(ValueError, 'same five'):
                verify_saved_baseline(root)


if __name__ == '__main__':
    unittest.main()
