"""Generic runner and paid-request protections, using WAV fixtures and fake responses."""
from collections import Counter
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from openai import OpenAIError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from asr_common import prepare_clip
from budget import cmi_band
from local_whisper_pilot import load_state, save_state
from prepare_validation_check import BANDS, clip_key, select_rows
from run_evaluation import API_SETTINGS, execution_lock, main, read_manifest, run_api, score_run, specification_for
from verify_evaluation import verify
from test_pilot_notebook import wav_row


class RateError(OpenAIError):
    status_code = 429
    request_id = 'request-test'


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        credentials_patch = patch('api_credentials.PRIVATE_ENV_FILE', self.root / 'private.env')
        credentials_patch.start()
        self.addCleanup(credentials_patch.stop)
        for directory in ['.cache/wavs', 'results/predictions', 'results/metrics']:
            (self.root / directory).mkdir(parents=True)
        entries = []
        for i in range(1, 4):
            row = wav_row(i)
            identity = prepare_clip(row, 'validation')['identity']
            content = row['audio']['bytes']
            payload = hashlib.sha256(content).hexdigest()
            name = '.cache/wavs/' + payload + '.wav'
            (self.root / name).write_bytes(content)
            entries.append({'identity': identity, 'audio_path': name, 'payload_sha256': payload})
        self.manifest = {'dataset': {'id': 'test', 'revision': 'pinned', 'config': 'default', 'split': 'validation'},
                         'purpose': 'validation_runtime', 'clips': entries}
        self.manifest_path = self.root / 'validation_fixture.json'
        self.manifest_path.write_text(json.dumps(self.manifest), encoding='utf-8')
        _, self.clips = read_manifest(self.manifest_path, self.root)
        self.spec = specification_for(self.manifest, self.manifest_path, 'whisper_api')
        self.output = self.root / 'results/predictions/validation_fixture_whisper_api.json'
        self.state = load_state(self.output, self.spec)
        self.calls = []
        self.stdout = io.StringIO()
        test = self

        def create(**kwargs):
            index = len(test.calls)
            test.calls.append(kwargs)
            text = test.clips[index]['identity']['transcription']
            return types.SimpleNamespace(model_dump=lambda **options: {'text': text}, _request_id=f'request-{index}')

        self.client = types.SimpleNamespace(audio=types.SimpleNamespace(transcriptions=types.SimpleNamespace(create=create)), close=lambda: None)

    def api(self, limit=3):
        with contextlib.redirect_stdout(self.stdout):
            return run_api(self.clips, self.state, self.output, self.client, limit)

    def command(self, *options):
        with patch('run_evaluation.ROOT', self.root), patch('run_evaluation.read_manifest', return_value=(self.manifest, self.clips)):
            with contextlib.redirect_stdout(self.stdout):
                return main(['--manifest', str(self.manifest_path), '--system', 'whisper_api', *options])

    def test_manifest_rejects_path_escape_changed_audio_and_duplicate_identity(self):
        original = copy.deepcopy(self.manifest)
        for change in ['escape', 'checksum', 'duplicate']:
            self.manifest = copy.deepcopy(original)
            if change == 'escape':
                self.manifest['clips'][0]['audio_path'] = '../outside.wav'
            elif change == 'checksum':
                self.manifest['clips'][0]['payload_sha256'] = '0' * 64
            else:
                self.manifest['clips'][1] = self.manifest['clips'][0]
            self.manifest_path.write_text(json.dumps(self.manifest))
            with self.assertRaises(ValueError):
                read_manifest(self.manifest_path, self.root)

    def test_dry_run_never_authenticates_writes_or_calls_api(self):
        with patch('run_evaluation.getpass', side_effect=AssertionError('must not request key')):
            with patch('openai.OpenAI') as factory:
                self.assertEqual(self.command(), 0)
                factory.assert_not_called()
        self.assertFalse(self.output.exists())
        self.assertIn('DRY RUN', self.stdout.getvalue())

    def test_api_execution_without_explicit_positive_limit_stops_before_key(self):
        with patch('run_evaluation.getpass', side_effect=AssertionError('must not request key')):
            for args in [('--execute',), ('--execute', '--max-requests', '0')]:
                with self.assertRaisesRegex(ValueError, 'positive limit'):
                    self.command(*args)
        self.assertFalse(self.output.exists())

    def test_test_split_execution_is_blocked_until_manifest_is_marked_ready(self):
        self.manifest['dataset']['split'] = 'test'
        with patch('openai.OpenAI', side_effect=AssertionError('test data must stay held out')):
            with self.assertRaisesRegex(ValueError, 'after the reference audit'):
                self.command('--execute', '--max-requests', '3')
        self.assertFalse(self.output.exists())

    def test_payload_settings_partial_limit_and_resumption(self):
        self.api(1)
        self.assertEqual(len(self.calls), 1)
        self.assertNotIn('wer', score_run(self.state)['summary'])
        self.state = load_state(self.output, self.spec)
        self.api(3)
        self.assertEqual(len(self.calls), 3)
        for index, call in enumerate(self.calls):
            self.assertEqual(set(call), set(API_SETTINGS) | {'file'})
            self.assertEqual(call['file'][1], self.clips[index]['upload_bytes'])
            self.assertEqual(call['model'], 'whisper-1')
            self.assertEqual(call['temperature'], 0)
        self.state = load_state(self.output, self.spec)
        self.api(3)
        self.assertEqual(len(self.calls), 3)
        metrics = score_run(self.state)
        self.assertTrue(metrics['summary']['complete'])
        self.assertEqual(metrics['summary']['wer'], 0)
        self.assertEqual(self.state['api_request_attempts'], 3)
        self.assertNotIn('paid_api_calls', self.state)

    def test_error_does_not_export_secret_retry_or_get_asr_score(self):
        secret = 'api-secret-must-not-export'

        def fail(**kwargs):
            self.calls.append(kwargs)
            raise RateError(secret)

        self.client.audio.transcriptions.create = fail
        self.api()
        self.assertEqual(self.state['predictions'][0]['http_status'], 429)
        self.state = load_state(self.output, self.spec)
        self.api()
        self.assertEqual(len(self.calls), 1)
        self.assertNotIn(secret, self.output.read_text(encoding='utf-8'))
        self.assertNotIn(secret, self.stdout.getvalue())
        self.assertNotIn('wer', score_run(self.state)['summary'])

    def test_keyboard_interrupt_remains_pending_and_is_not_resent(self):
        def interrupt(**kwargs):
            self.calls.append(kwargs)
            raise KeyboardInterrupt()

        self.client.audio.transcriptions.create = interrupt
        with self.assertRaises(KeyboardInterrupt):
            self.api()
        self.state = load_state(self.output, self.spec)
        self.assertEqual(self.state['predictions'][0]['status'], 'pending')
        self.api()
        self.assertEqual(len(self.calls), 1)

    def test_malformed_success_body_is_saved_but_not_scored_or_resent(self):
        self.client.audio.transcriptions.create = lambda **kwargs: types.SimpleNamespace(
            model_dump=lambda **options: {'text': None}, _request_id='request-malformed')
        self.api()
        self.assertEqual(self.state['predictions'][0]['status'], 'received')
        self.assertIn('parse_error', self.state['predictions'][0])
        self.state = load_state(self.output, self.spec)
        self.client.audio.transcriptions.create = lambda **kwargs: self.fail('must not resend')
        self.api()
        self.assertNotIn('wer', score_run(self.state)['summary'])

    def test_empty_success_is_deletions_and_partial_coverage_has_no_headline(self):
        self.client.audio.transcriptions.create = lambda **kwargs: types.SimpleNamespace(
            model_dump=lambda **options: {'text': ''}, _request_id='request-empty')
        self.api()
        metrics = score_run(self.state)
        self.assertEqual(metrics['summary']['wer'], 1)
        self.assertEqual(metrics['summary']['cer'], 1)
        self.state['predictions'].pop()
        self.assertNotIn('wer', score_run(self.state)['summary'])

    def test_duplicate_execution_is_locked_and_lock_is_released(self):
        with execution_lock(self.output):
            with self.assertRaisesRegex(ValueError, 'Run lock exists'):
                with execution_lock(self.output):
                    self.fail('second run must not start')
        self.assertFalse(self.output.with_suffix('.lock').exists())

    def test_frozen_settings_and_package_versions_cannot_drift_before_first_run(self):
        manifest = copy.deepcopy(self.manifest)
        manifest['frozen_system_configs'] = {'whisper_api': copy.deepcopy(self.spec['config'])}
        manifest['frozen_packages'] = {'whisper_api': copy.deepcopy(self.spec['packages'])}
        self.assertEqual(specification_for(manifest, self.manifest_path, 'whisper_api')['config'], self.spec['config'])
        manifest['frozen_system_configs']['whisper_api']['request_settings']['temperature'] = 0.5
        with self.assertRaisesRegex(ValueError, 'Runtime settings differ'):
            specification_for(manifest, self.manifest_path, 'whisper_api')
        manifest['frozen_system_configs']['whisper_api'] = copy.deepcopy(self.spec['config'])
        manifest['frozen_packages']['whisper_api']['openai'] = 'different-version'
        with self.assertRaisesRegex(ValueError, 'Package versions differ'):
            specification_for(manifest, self.manifest_path, 'whisper_api')

    def test_cli_key_is_private_client_has_no_retries_and_export_is_reproducible(self):
        secret = 'private-test-key'
        with patch.dict('os.environ', {'OPENAI_API_KEY': secret}):
            with patch('openai.OpenAI', return_value=self.client) as factory:
                self.assertEqual(self.command('--execute', '--max-requests', '3'), 0)
                factory.assert_called_once_with(api_key=secret, base_url='https://api.openai.com/v1', timeout=120, max_retries=0)
        self.assertNotIn(secret, self.output.read_text(encoding='utf-8'))
        saved_metrics = json.loads((self.root / 'results/metrics/validation_fixture_whisper_api.json').read_text(encoding='utf-8'))
        self.assertEqual(saved_metrics, score_run(json.loads(self.output.read_text(encoding='utf-8'))))
        with patch('openai.OpenAI', side_effect=AssertionError('complete run must not authenticate')):
            self.assertEqual(self.command('--execute', '--max-requests', '3'), 0)

    def test_cli_loads_private_file_before_stale_environment_without_exporting_key(self):
        secret = 'private-file-test-key'
        (self.root / 'private.env').write_text('OPENAI_API_KEY=' + secret, encoding='utf-8')
        with patch.dict('os.environ', {'OPENAI_API_KEY': '\x16'}), \
                patch('run_evaluation.getpass', side_effect=AssertionError('file should avoid hidden prompt')), \
                patch('openai.OpenAI', return_value=self.client) as factory:
            self.assertEqual(self.command('--execute', '--max-requests', '3'), 0)
            self.assertEqual(factory.call_args.kwargs['api_key'], secret)
        self.assertNotIn(secret, self.output.read_text(encoding='utf-8'))

    def test_independent_verifier_accepts_relative_command_line_paths(self):
        self.api()
        metrics_path = self.root / 'results/metrics/validation_fixture_whisper_api.json'
        save_state(metrics_path, score_run(self.state))
        with patch('verify_evaluation.ROOT', self.root), patch('verify_evaluation.read_manifest', return_value=(self.manifest, self.clips)):
            with contextlib.chdir(self.root):
                report = verify(Path('validation_fixture.json'), self.output.relative_to(self.root), metrics_path)
        self.assertEqual(report['independent_scores']['wer'], 0)
        self.assertTrue(report['coverage']['complete'])

    def test_independent_verifier_rejects_changed_headline_score(self):
        self.api()
        metrics = score_run(self.state)
        metrics['summary']['wer'] = 0.9
        metrics_path = self.root / 'results/metrics/validation_fixture_whisper_api.json'
        save_state(metrics_path, metrics)
        with patch('verify_evaluation.read_manifest', return_value=(self.manifest, self.clips)):
            with self.assertRaises(AssertionError):
                verify(self.manifest_path, self.output, metrics_path)

    def test_verifier_keeps_complete_raw_result_when_gpu_snapshot_was_not_saved(self):
        self.api()
        self.state['run_spec']['system'] = 'local'
        self.state['run_spec']['config'] = {'transcribe': {'beam_size': 5}}
        for row in self.state['predictions']:
            row['response'] = {'segments': [{'text': row['hypothesis']}], 'info': {
                'language': 'ne', 'transcription_options': {'initial_prompt': None, 'hotwords': None,
                'prefix': None, 'beam_size': 5, 'temperatures': [0.0], 'condition_on_previous_text': False}}}
            row['transcription_s'] = 0.1
            row['gpu_after_transcription'] = {'used_memory_mib': 4000}
        missing = self.state['predictions'][-1]
        missing.pop('gpu_after_transcription')
        save_state(self.output, self.state)
        metrics_path = self.root / 'results/metrics/validation_fixture_whisper_api.json'
        save_state(metrics_path, score_run(self.state))
        with patch('verify_evaluation.ROOT', self.root), patch('verify_evaluation.read_manifest', return_value=(self.manifest, self.clips)):
            report = verify(self.manifest_path, self.output, metrics_path)
        self.assertTrue(report['coverage']['complete'])
        self.assertEqual(report['independent_scores']['wer'], 0)
        self.assertEqual(report['largest_observed_device_memory_mib'], 4000)
        self.assertEqual(report['missing_gpu_snapshot_clip_ids'], [missing['clip_id']])

    def test_real_pinned_sdk_serializes_request_with_offline_transport(self):
        import httpx
        from openai import OpenAI
        requests = []

        def respond(request):
            requests.append(request)
            self.assertEqual(str(request.url), 'https://api.openai.com/v1/audio/transcriptions')
            self.assertIn('multipart/form-data', request.headers['content-type'])
            self.assertIn(self.clips[0]['upload_bytes'], request.content)
            return httpx.Response(200, headers={'x-request-id': 'request-offline-sdk'}, json={
                'text': self.clips[0]['identity']['transcription'], 'task': 'transcribe', 'language': 'nepali',
                'duration': 0.1, 'segments': [], 'usage': {'type': 'duration', 'seconds': 1}})

        with OpenAI(api_key='offline-test-key', base_url='https://api.openai.com/v1', max_retries=0,
                    http_client=httpx.Client(transport=httpx.MockTransport(respond))) as client:
            with contextlib.redirect_stdout(self.stdout):
                run_api(self.clips, self.state, self.output, client, 1)
        self.assertEqual(len(requests), 1)
        self.assertEqual(self.state['predictions'][0]['request_id'], 'request-offline-sdk')
        self.assertEqual(self.state['predictions'][0]['status'], 'received')
        self.assertNotIn('offline-test-key', self.output.read_text(encoding='utf-8'))


class SelectionTests(unittest.TestCase):
    def inventory(self):
        rows = []
        for band, cmi in enumerate([5, 15, 25, 35, 45]):
            for i, duration in enumerate([3, 5, 8, 12, 14]):
                rows.append({'split': 'validation', 'speech_type': 'cs', 'video_id': f'v{band}_{i}',
                             'start_ms': 0, 'end_ms': duration * 1000, 'duration_s': duration,
                             'speaker_id': f'channel{i % 3}', 'cmi': cmi, 'reference_words': 3})
        return {'shards': [{'rows': rows}]}

    def test_selection_is_deterministic_balanced_and_keeps_length_extremes(self):
        inventory = self.inventory()
        selected = select_rows(inventory, set())
        self.assertEqual(selected, select_rows(inventory, set()))
        self.assertEqual(Counter(cmi_band(row['cmi']) for row in selected), {band: 3 for band in BANDS})
        for band in BANDS:
            lengths = [row['duration_s'] for row in selected if cmi_band(row['cmi']) == band]
            self.assertIn(3, lengths)
            self.assertIn(14, lengths)

    def test_selection_excludes_original_ambiguous_and_nonvalidation_rows(self):
        inventory = self.inventory()
        rows = inventory['shards'][0]['rows']
        excluded = {clip_key(rows[0])}
        duplicate = copy.deepcopy(rows[1])
        rows.extend([duplicate, dict(rows[2], split='test', video_id='test-only')])
        selected = select_rows(inventory, excluded)
        self.assertEqual(len(selected), 15)
        self.assertTrue(all(row['split'] == 'validation' for row in selected))
        self.assertFalse({clip_key(row) for row in selected} & (excluded | {clip_key(duplicate)}))


if __name__ == '__main__':
    unittest.main()
