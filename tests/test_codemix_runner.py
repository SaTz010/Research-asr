"""Exploratory runs must validate inputs, preserve checkpoints and avoid API calls."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import run_codemix_experiment as runner
from asr_common import prepare_clip
from local_whisper_pilot import load_state, save_state
from run_evaluation import read_manifest
from test_pilot_notebook import wav_row


class CodemixRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for folder in ['wavs', 'model', 'results/predictions', 'results/metrics']:
            (self.root / folder).mkdir(parents=True)
        row = wav_row(1)
        data = row['audio']['bytes']
        (self.root / 'wavs/one.wav').write_bytes(data)
        self.manifest = {'dataset': {'id': 'fixture', 'revision': 'pinned', 'split': 'validation'},
                         'clips': [{'identity': prepare_clip(row, 'validation')['identity'],
                                    'audio_path': 'wavs/one.wav', 'payload_sha256': hashlib.sha256(data).hexdigest()}]}
        self.path = self.root / 'manifest.json'
        save_state(self.path, self.manifest)
        (self.root / 'model/model.bin').write_bytes(b'fixture-conversion')
        self.config = {'purpose': 'exploratory fixture', 'runtime_packages': {'numpy': 'fixture'},
                       'converted_directory': 'model', 'transcribe': {'language': 'ne'},
                       'converted_files_sha256': {'model.bin': runner.checksum(self.root / 'model/model.bin')},
                       'sources': {'validation_manifest': {'path': 'manifest.json', 'sha256': runner.checksum(self.path)}}}
        self.config_path = self.root / 'config.json'
        save_state(self.config_path, self.config)
        for name, value in [('ROOT', self.root), ('CONFIG', self.config_path)]:
            p = patch.object(runner, name, value); p.start(); self.addCleanup(p.stop)
        p = patch.object(runner, 'version', return_value='fixture'); p.start(); self.addCleanup(p.stop)
        p = patch.object(runner, 'read_manifest', side_effect=lambda path: read_manifest(path, self.root))
        p.start(); self.addCleanup(p.stop)
        p = patch.object(runner, 'keep_awake', side_effect=contextlib.nullcontext)
        p.start(); self.addCleanup(p.stop)

    def command(self, *args):
        with contextlib.redirect_stdout(io.StringIO()):
            return runner.main(['--split', 'validation', *args])

    def test_dry_run_has_no_outputs_or_gpu_or_credential_access(self):
        with patch.object(runner, 'configure_cuda', side_effect=AssertionError('GPU must not load')):
            with patch('api_credentials.read_api_key', side_effect=AssertionError('No credentials')):
                self.assertEqual(self.command(), 0)
        self.assertFalse(list((self.root / 'results/predictions').iterdir()))

    def test_manifest_model_and_package_drift_stop_execution(self):
        for change in ['manifest', 'model', 'packages']:
            with self.subTest(change=change):
                if change == 'manifest':
                    self.path.write_text('{}')
                elif change == 'model':
                    (self.root / 'model/model.bin').write_bytes(b'changed')
                with patch.object(runner, 'version', return_value='changed' if change == 'packages' else 'fixture'):
                    with self.assertRaises(ValueError):
                        runner.specification('validation')
                save_state(self.path, self.manifest)
                (self.root / 'model/model.bin').write_bytes(b'fixture-conversion')

    def test_completed_checkpoint_rescores_without_loading_a_model(self):
        spec, clips, _ = runner.specification('validation')
        path = self.root / 'results/predictions/validation_codemix_turbo_20261127.json'
        state = load_state(path, spec)
        state['predictions'] = [{**clips[0]['identity'], 'status': 'received',
                                 'hypothesis': clips[0]['identity']['transcription']}]
        save_state(path, state)
        before = path.read_bytes()
        with patch.object(runner, 'configure_cuda', side_effect=AssertionError('Must reuse saved output')):
            self.assertEqual(self.command('--execute'), 0)
        self.assertEqual(path.read_bytes(), before)
        metrics = json.loads((self.root / 'results/metrics' / path.name).read_bytes())
        self.assertTrue(metrics['summary']['complete'])
        self.assertEqual(metrics['summary']['wer'], 0)

    def test_test_set_cannot_be_silently_limited(self):
        with self.assertRaisesRegex(ValueError, 'validation pilot'):
            runner.main(['--split', 'test', '--max-clips', '5'])


if __name__ == '__main__':
    unittest.main()
