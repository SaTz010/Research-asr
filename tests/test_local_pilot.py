"""Local pilot checks with synthetic WAVs and a fake decoder; no GPU/downloads."""
import ast
import contextlib
import copy
from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unicodedata
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from asr_common import normalize_text, prepare_clip
from local_whisper_pilot import load_state, run_clips, save_state, score_saved
from prepare_pilot_audio import load_baseline, recover_audio, verify_payload
from test_pilot_notebook import wav_row


@dataclass
class Segment:
    text: str


@dataclass
class Info:
    language: str = 'ne'


class Stream(list):
    def decode(self, enabled):
        assert enabled is False
        return self

    def select_columns(self, columns):
        return self


class LocalPilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'pilot.json'
        self.baseline = load_baseline()
        config = json.loads((ROOT / 'configs/local_whisper_pilot.json').read_text())
        self.spec = {'config': config, 'manifest': self.baseline['manifest']}
        self.clips = [{'identity': row, 'audio': np.zeros(160, dtype=np.float32)} for row in self.baseline['manifest']]
        self.state = load_state(self.path, self.spec)
        self.calls = []
        test = self

        class Model:
            def transcribe(self, audio, **options):
                index = len(test.calls)
                test.calls.append((audio, options))
                return iter([Segment(test.clips[index]['identity']['transcription'])]), Info()

        self.model = Model()

    def run_clips(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return run_clips(self.model, self.clips, self.state, self.path, synchronize=lambda: None, snapshot=lambda: {})

    def test_same_decoder_controls_pairing_saved_generation_and_resume(self):
        self.run_clips()
        self.assertEqual(len(self.calls), 5)
        for i, (audio, options) in enumerate(self.calls):
            self.assertIs(audio, self.clips[i]['audio'])
            self.assertEqual(options, self.spec['config']['transcribe'])
            self.assertIsNone(options['language'])
            self.assertEqual(options['task'], 'transcribe')
        self.state = load_state(self.path, self.spec)
        self.run_clips()
        self.assertEqual(len(self.calls), 5)
        metrics = score_saved(self.state, self.baseline)
        self.assertTrue(metrics['summary']['complete'])
        self.assertEqual(metrics['summary']['local_wer'], 0)
        self.assertEqual(metrics['summary']['api_wer'], 81 / 111)
        self.assertIn('segments', self.state['predictions'][0]['response'])

    def test_atomic_save_recovers_from_brief_windows_replace_lock(self):
        original_replace = Path.replace
        attempts = []

        def locked_twice(source, target):
            attempts.append(1)
            if len(attempts) < 3:
                raise PermissionError('synthetic Windows file lock')
            return original_replace(source, target)

        with patch.object(Path, 'replace', locked_twice), patch('local_whisper_pilot.time.sleep') as sleep:
            save_state(self.path, {'hypothesis': 'नेपाल'})
        self.assertEqual(len(attempts), 3)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(json.loads(self.path.read_text(encoding='utf-8')), {'hypothesis': 'नेपाल'})
        self.assertFalse(self.path.with_suffix('.tmp').exists())

    def test_persistent_replace_failure_preserves_old_checkpoint_and_complete_temp(self):
        save_state(self.path, {'status': 'pending'})
        before = self.path.read_bytes()
        with patch.object(Path, 'replace', side_effect=PermissionError('persistent lock')) as replace, \
                patch('local_whisper_pilot.time.sleep') as sleep:
            with self.assertRaises(PermissionError):
                save_state(self.path, {'status': 'received', 'hypothesis': 'नेपाल'})
        self.assertEqual(replace.call_count, 8)
        self.assertEqual(sleep.call_count, 7)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(json.loads(self.path.with_suffix('.tmp').read_text(encoding='utf-8')),
                         {'status': 'received', 'hypothesis': 'नेपाल'})

    def test_failed_local_attempt_remains_and_is_not_automatically_repeated(self):
        def fail(*args, **kwargs):
            self.calls.append(1)
            raise RuntimeError('synthetic GPU error')

        self.model.transcribe = fail
        with self.assertRaisesRegex(RuntimeError, 'synthetic GPU'):
            self.run_clips()
        self.state = load_state(self.path, self.spec)
        self.assertEqual(self.state['predictions'][0]['status'], 'local_error')
        self.run_clips()
        self.assertEqual(len(self.calls), 1)
        self.assertNotIn('local_wer', score_saved(self.state, self.baseline)['summary'])

    def test_changed_settings_or_duplicate_jobs_are_rejected(self):
        self.run_clips()
        altered = copy.deepcopy(self.spec)
        altered['config']['transcribe']['language'] = 'ne'
        with self.assertRaisesRegex(ValueError, 'settings/inputs differ'):
            load_state(self.path, altered)
        self.state['predictions'].append(self.state['predictions'][0])
        save_state(self.path, self.state)
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            load_state(self.path, self.spec)

    def test_corpus_error_rate_is_weighted_by_reference_length_and_empty_text_counts(self):
        self.run_clips()
        self.state['predictions'][0]['hypothesis'] = ''
        metrics = score_saved(self.state, self.baseline)
        self.assertEqual(metrics['per_clip'][0]['local_wer'], 1)
        self.assertAlmostEqual(metrics['summary']['local_wer'], 17 / 111)

    def test_normalizer_matches_historical_notebook(self):
        notebook = json.loads((ROOT / 'notebooks/03_whisper_api_comparison.ipynb').read_text(encoding='utf-8'))
        helpers = next(''.join(cell['source']) for cell in notebook['cells'] if cell['id'] == 'helpers')
        node = next(node for node in ast.parse(helpers).body if isinstance(node, ast.FunctionDef) and node.name == 'normalize_text')
        namespace = {'unicodedata': unicodedata}
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'historical-normalizer', 'exec'), namespace)
        for text in ['नेपालमा १२ SCHOOL छन्।', 'cafe\u0301', 'half-life: 25%', 'स्कुल school', '']:
            self.assertEqual(normalize_text(text), namespace['normalize_text'](text))

    def test_wav_and_waveform_hashes_checked_again_after_cache_reuse(self):
        row = wav_row()
        identity = prepare_clip(row, 'validation')['identity']
        content = row['audio']['bytes']
        payload = hashlib.sha256(content).hexdigest()
        clip = verify_payload(identity, content, payload, 'validation')
        self.assertEqual(clip['identity'], identity)
        with self.assertRaisesRegex(ValueError, 'WAV bytes differ'):
            verify_payload(identity, content + b'changed', payload, 'validation')
        with self.assertRaisesRegex(ValueError, 'Audio hash or metadata differs'):
            verify_payload({**identity, 'audio_sha256': '0' * 64}, content, payload, 'validation')

    def test_duplicate_source_identity_never_gets_a_completed_cache_marker(self):
        rows = [wav_row(i) for i in range(1, 6)]
        identities = [prepare_clip(row, 'validation')['identity'] for row in rows]
        baseline = {'dataset': {'id': 'test', 'config': 'default', 'split': 'validation', 'revision': 'test'},
                    'manifest': identities, 'run_spec': {'payload_sha256': {
                        identity['clip_id']: hashlib.sha256(row['audio']['bytes']).hexdigest()
                        for row, identity in zip(rows, identities)}}}
        cache = Path(self.temp.name) / 'audio'
        with patch('datasets.load_dataset', return_value=Stream(rows + [rows[0]])):
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(ValueError, 'duplicate provenance'):
                    recover_audio(baseline, cache)
        self.assertFalse((cache / 'verified.json').exists())


if __name__ == '__main__':
    unittest.main()
