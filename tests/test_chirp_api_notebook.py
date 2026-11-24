"""Check Chirp request pairing, checkpoint safety and scoring without cloud calls."""

import ast
import base64
import contextlib
import copy
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import platform
import re
import sys
import tempfile
import time
import types
import unicodedata
import unittest
from unittest.mock import patch
import zipfile

from test_whisper_api_notebook import error_rate, word_error_rate

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = json.loads((ROOT / 'notebooks/04_chirp3_api_pilot.ipynb').read_text(encoding='utf-8'))
CELLS = {cell['id']: ''.join(cell['source']) for cell in NOTEBOOK['cells']}


class NetworkError(Exception):
    pass


class ChirpNotebookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = io.StringIO()
        self.ns = dict(json=json, hashlib=hashlib, Path=Path, datetime=datetime, timezone=timezone,
                       time=time, unicodedata=unicodedata, re=re, base64=base64, wer=word_error_rate,
                       cer=error_rate, zipfile=zipfile, sys=sys, platform=platform,
                       package_versions={'requests': '2.32.4'},
                       requests=types.SimpleNamespace(RequestException=NetworkError))
        self.execute('baseline')
        normalizer = next(node for node in ast.parse(CELLS['helpers']).body
                          if isinstance(node, ast.FunctionDef) and node.name == 'normalize_text')
        exec(compile(ast.Module(body=[normalizer], type_ignores=[]), 'normalize', 'exec'), self.ns)
        self.ns['clips'] = [{'identity': copy.deepcopy(row), 'upload_bytes': b'test-wav-' + bytes([i])}
                            for i, row in enumerate(self.ns['baseline']['manifest'])]
        self.execute('api-helpers')
        self.ns['CHECKPOINT_PATH'] = Path(self.temp.name) / 'checkpoint.json'
        self.calls = []
        self.secret = 'test-oauth-token-must-not-export'

        def before_request(request, method, endpoint, headers):
            headers['Authorization'] = 'Bearer ' + self.secret

        def post(endpoint, **kwargs):
            audio = base64.b64decode(kwargs['json']['content'])
            index = next(i for i, clip in enumerate(self.ns['clips']) if clip['upload_bytes'] == audio)
            self.calls.append((endpoint, kwargs))
            text = self.ns['clips'][index]['identity']['transcription']
            body = {'results': [{'alternatives': [{'transcript': text}], 'languageCode': 'ne-NP'}],
                    'metadata': {'requestId': f'request-{index}', 'totalBilledDuration': '9s'}}
            return types.SimpleNamespace(status_code=200, text=json.dumps(body))

        self.ns.update(credentials=types.SimpleNamespace(before_request=before_request), auth_request=object(),
                       session=types.SimpleNamespace(post=post))

    def execute(self, label):
        with contextlib.redirect_stdout(self.output):
            exec(compile(CELLS[label], label, 'exec'), self.ns)

    def run_pilot(self):
        with contextlib.redirect_stdout(self.output):
            return self.ns['run_api_pilot']()

    def export(self):
        downloads = []
        colab = types.ModuleType('google.colab')
        colab.files = types.SimpleNamespace(download=downloads.append)
        google = types.ModuleType('google')
        google.colab = colab
        with patch.dict(sys.modules, {'google': google, 'google.colab': colab}):
            self.ns['Path'] = lambda value: Path(self.temp.name) / value
            self.execute('export')
        self.assertEqual(len(downloads), 1)
        with zipfile.ZipFile(downloads[0]) as archive:
            raw = archive.read('results.json').decode('utf-8')
            self.assertNotIn(self.secret, raw)
            self.assertNotIn('Authorization', raw)
            self.assertNotIn('test-wav-', raw)
            self.assertNotIn(self.secret, archive.read('checkpoint.json').decode('utf-8'))
            return json.loads(raw)

    def test_clean_notebook_and_authentic_baseline(self):
        self.assertEqual(len(CELLS), len(NOTEBOOK['cells']))
        for index, cell in enumerate(NOTEBOOK['cells']):
            if cell['cell_type'] == 'code':
                self.assertEqual(cell['outputs'], [])
                self.assertIsNone(cell['execution_count'])
                self.assertTrue(''.join(NOTEBOOK['cells'][index - 1]['source']).startswith('### '))
                compile('\n'.join(line for line in ''.join(cell['source']).splitlines() if not line.startswith('%pip ')), cell['id'], 'exec')
        baseline = self.ns['baseline']
        path = ROOT / 'results/predictions' / baseline['source_archive']
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), baseline['source_sha256'])
        with zipfile.ZipFile(path) as archive:
            source = json.loads(archive.read('results.json'))
        for key in ['manifest', 'dataset', 'run_spec', 'summary']:
            self.assertEqual(baseline[key], source[key])
        original = [row for row in source['predictions'] if row['mode'] == 'auto']
        self.assertEqual(baseline['predictions'], [{key: row[key] for key in baseline['predictions'][0]} for row in original])

    def test_exact_requests_then_rerun_without_resubmission(self):
        self.run_pilot()
        self.assertEqual(len(self.calls), 5)
        for index, (endpoint, call) in enumerate(self.calls):
            self.assertEqual(endpoint, 'https://us-speech.googleapis.com/v2/projects/research-asr/locations/us/recognizers/_:recognize')
            self.assertEqual(set(call['json']), {'config', 'content'})
            self.assertEqual(call['json']['config'], {'autoDecodingConfig': {}, 'languageCodes': ['auto'], 'model': 'chirp_3'})
            self.assertEqual(base64.b64decode(call['json']['content']), self.ns['clips'][index]['upload_bytes'])
            self.assertEqual(call['headers']['x-goog-user-project'], 'research-asr')
            self.assertFalse(call['allow_redirects'])
            self.assertEqual(call['timeout'], (15, 300))
        self.run_pilot()
        self.assertEqual(len(self.calls), 5)
        self.execute('summary')
        self.assertEqual(self.ns['summary']['wer'], 0)
        self.assertEqual(self.ns['summary']['cer'], 0)
        bundle = self.export()
        self.assertTrue(bundle['summary']['auto']['complete'])
        self.assertEqual(bundle['predictions'][0]['response']['metadata']['requestId'], 'request-0')

    def test_transcript_joining_empty_results_and_malformed_shapes(self):
        parse = self.ns['response_text']
        self.assertEqual(parse({'results': [{'alternatives': [{'transcript': 'one'}, {'transcript': 'wrong'}]},
                                            {'alternatives': [{'transcript': ' two '}]}]}), 'one two')
        for body in [{}, {'results': []}]:
            self.assertEqual(parse(body), '')
        for body in [None, {'error': {}}, {'results': None}, {'results': [{}]},
                     {'results': [None]}, {'results': [{'alternatives': [{'transcript': None}]}]}]:
            with self.assertRaises(ValueError):
                parse(body)
        self.ns['session'].post = lambda *args, **kwargs: types.SimpleNamespace(status_code=200, text='{}')
        self.run_pilot()
        self.execute('summary')
        self.assertEqual(self.ns['summary']['wer'], 1)
        self.assertEqual(self.ns['summary']['cer'], 1)

    def test_http_failure_and_network_exception_are_not_resent(self):
        for kind in ['http', 'network']:
            with self.subTest(kind=kind):
                self.ns['CHECKPOINT_PATH'] = Path(self.temp.name) / (kind + '.json')
                attempts = []

                def fail(*args, **kwargs):
                    attempts.append(1)
                    if kind == 'network':
                        raise NetworkError(self.secret)
                    return types.SimpleNamespace(status_code=403, text=self.secret)

                self.ns['session'].post = fail
                state = self.run_pilot()
                self.assertEqual(state['predictions'][0]['status'], 'api_error')
                self.run_pilot()
                self.assertEqual(len(attempts), 1)
                bundle = self.export()
                self.assertFalse(bundle['summary']['auto']['complete'])
                self.assertNotIn('wer', bundle['summary']['auto'])
                self.assertNotIn(self.secret, self.output.getvalue())

    def test_interrupt_retains_pending_and_auth_failure_does_not_start_attempt(self):
        def interrupt(*args, **kwargs):
            self.calls.append(1)
            raise KeyboardInterrupt()

        self.ns['session'].post = interrupt
        with self.assertRaises(KeyboardInterrupt):
            self.run_pilot()
        self.run_pilot()
        self.assertEqual(len(self.calls), 1)
        bundle = self.export()
        self.assertEqual(bundle['predictions'][0]['status'], 'pending')

        def no_auth(*args):
            raise ValueError('sign in first')

        self.ns['CHECKPOINT_PATH'] = Path(self.temp.name) / 'auth-failure.json'
        self.ns['credentials'].before_request = no_auth
        with self.assertRaisesRegex(ValueError, 'sign in first'):
            self.run_pilot()
        self.assertFalse(self.ns['CHECKPOINT_PATH'].exists())

    def test_bad_paid_response_still_exports_and_cannot_be_resent(self):
        for body in ['not-json', '{"results": [{}]}']:
            with self.subTest(body=body):
                self.ns['CHECKPOINT_PATH'] = Path(self.temp.name) / hashlib.sha256(body.encode()).hexdigest()
                calls = []

                def malformed(*args, **kwargs):
                    calls.append(1)
                    return types.SimpleNamespace(status_code=200, text=body)

                self.ns['session'].post = malformed
                self.run_pilot()
                try:
                    self.run_pilot()
                except ValueError:
                    pass
                self.assertEqual(len(calls), 1)
                bundle = self.export()
                self.assertFalse(bundle['summary']['auto']['complete'])
                self.assertIn('parse_error', bundle['predictions'][0])

    def test_checkpoint_changes_and_duplicate_rows_rejected(self):
        self.run_pilot()
        path = self.ns['CHECKPOINT_PATH']
        state = json.loads(path.read_text(encoding='utf-8'))
        original = copy.deepcopy(state)
        state['run_spec']['request_config']['languageCodes'] = ['ne-NP']
        path.write_text(json.dumps(state), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'settings differ'):
            self.run_pilot()
        original['predictions'].append(original['predictions'][0])
        path.write_text(json.dumps(original), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.run_pilot()
        self.assertEqual(len(self.calls), 5)

    def restore_actual_checkpoint(self, latest=False):
        filename = ('chirp3_api_pilot_20261023T090553705776Z.zip' if latest
                    else 'chirp3_api_pilot_20261023T080349973576Z.zip')
        path = ROOT / 'results/predictions' / filename
        with zipfile.ZipFile(path) as archive:
            original = json.loads(archive.read('checkpoint.json'))
        # Mock audio is used for transport tests; the historical fixture retains its real payload hashes.
        self.ns['run_spec'] = copy.deepcopy(original['run_spec'])
        if latest:
            self.execute('restore-checkpoint')
            self.assertEqual(self.ns['saved_checkpoint'], original)
        else:
            self.ns['save_checkpoint'](original)
        return original

    def test_restores_authentic_partial_checkpoint_without_overwriting_progress(self):
        original = self.restore_actual_checkpoint(latest=True)
        self.assertEqual(self.ns['load_checkpoint'](), original)
        self.assertEqual(len(self.calls), 0)
        self.run_pilot()
        self.assertEqual(len(self.calls), 0)
        with contextlib.redirect_stdout(self.output):
            self.ns['run_api_pilot'](skip_saved_service_errors=True)
        progressed = self.ns['load_checkpoint']()
        self.execute('restore-checkpoint')
        self.assertEqual(self.ns['load_checkpoint'](), progressed)
        self.assertEqual(len(self.calls), 1)

    def test_explicit_retry_reuses_three_results_and_preserves_failed_attempt(self):
        original = self.restore_actual_checkpoint()
        with contextlib.redirect_stdout(self.output):
            state = self.ns['retry_single_read_timeout']()
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(state['predictions'][:3], original['predictions'][:3])
        self.assertEqual([row['clip_id'] for row in state['predictions']], list(self.ns['expected_clips']))
        self.assertEqual(len(state['previous_attempts']), 1)
        self.assertTrue(all(state['previous_attempts'][0][key] == value for key, value in original['predictions'][3].items()))
        self.run_pilot()
        self.assertEqual(len(self.calls), 2)
        bundle = self.export()
        self.assertTrue(bundle['summary']['auto']['complete'])
        self.assertEqual(bundle['previous_attempts'], state['previous_attempts'])

    def test_recovery_refuses_second_retry_and_uncertain_pending_requests(self):
        self.restore_actual_checkpoint()

        class ReadTimeout(NetworkError):
            pass

        def fail(*args, **kwargs):
            self.calls.append(1)
            raise ReadTimeout(self.secret)

        self.ns['session'].post = fail
        with contextlib.redirect_stdout(self.output):
            self.ns['retry_single_read_timeout']()
        with self.assertRaisesRegex(ValueError, 'already used'):
            self.ns['retry_single_read_timeout']()
        self.assertEqual(len(self.calls), 1)
        state = self.ns['load_checkpoint']()
        state['predictions'][-1]['status'] = 'pending'
        self.ns['save_checkpoint'](state)
        with self.assertRaisesRegex(ValueError, 'not pending'):
            self.ns['retry_single_read_timeout']()
        self.assertEqual(len(self.calls), 1)

    def test_latest_recovery_submits_only_fifth_clip_without_retrying_503(self):
        original = self.restore_actual_checkpoint(latest=True)
        self.execute('retry-timeout')
        self.assertEqual(len(self.calls), 0)
        self.execute('run-unattempted')
        state = self.ns['load_checkpoint']()
        self.assertEqual(state['predictions'][:4], original['predictions'])
        self.assertEqual(state['previous_attempts'], original['previous_attempts'])
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(base64.b64decode(self.calls[0][1]['json']['content']), self.ns['clips'][4]['upload_bytes'])
        self.execute('run-unattempted')
        self.assertEqual(len(self.calls), 1)
        bundle = self.export()
        self.assertEqual(bundle['summary']['auto']['successful_clips'], 4)
        self.assertFalse(bundle['summary']['auto']['complete'])
        self.assertNotIn('wer', bundle['summary']['auto'])
        self.assertEqual(bundle['predictions'][3]['http_status'], 503)

    def test_continue_past_503_does_not_bypass_pending_or_access_errors(self):
        original = self.restore_actual_checkpoint(latest=True)
        for status, http in [('pending', 503), ('api_error', 403), ('api_error', 429)]:
            state = copy.deepcopy(original)
            state['predictions'][3].update(status=status, http_status=http)
            self.ns['save_checkpoint'](state)
            self.execute('run-unattempted')
            self.assertEqual(len(self.calls), 0)
    def test_colab_signin_uses_project_quota_and_disables_transcription_retries(self):
        calls = []
        colab = types.ModuleType('google.colab')
        colab.auth = types.SimpleNamespace(authenticate_user=lambda **kwargs: calls.append(kwargs))
        session = types.SimpleNamespace(mount=lambda *args: calls.append(args))
        self.ns.update(google=types.SimpleNamespace(auth=types.SimpleNamespace(default=lambda **kwargs: (calls.append(kwargs), None))),
                       Request=lambda: 'auth-request',
                       requests=types.SimpleNamespace(Session=lambda: session,
                                                      adapters=types.SimpleNamespace(HTTPAdapter=lambda **kwargs: kwargs)))
        with patch.dict(sys.modules, {'google.colab': colab}):
            self.execute('authenticate')
        self.assertEqual(calls, [{'project_id': 'research-asr'},
                                 {'scopes': ['https://www.googleapis.com/auth/cloud-platform'], 'quota_project_id': 'research-asr'},
                                 ('https://', {'max_retries': 0})])


if __name__ == '__main__':
    unittest.main()
