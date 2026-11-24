"""Exercise API requests, checkpointing, scoring, and secret handling without network access."""

import ast
import contextlib
import copy
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time
import types
import unicodedata
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = json.loads((ROOT / 'notebooks/03_whisper_api_comparison.ipynb').read_text(encoding='utf-8'))
CELLS = {cell['id']: ''.join(cell['source']) for cell in NOTEBOOK['cells']}


def error_rate(references, hypotheses):
    if isinstance(references, str):
        references, hypotheses = [references], [hypotheses]
    errors = count = 0
    for reference, hypothesis in zip(references, hypotheses):
        previous = list(range(len(hypothesis) + 1))
        for i, a in enumerate(reference, 1):
            current = [i]
            for j, b in enumerate(hypothesis, 1):
                current.append(min(previous[j] + 1, current[-1] + 1, previous[j - 1] + (a != b)))
            previous = current
        errors += previous[-1]
        count += len(reference)
    return errors / count


def word_error_rate(references, hypotheses):
    if isinstance(references, str):
        references, hypotheses = [references], [hypotheses]
    return error_rate([r.split() for r in references], [h.split() for h in hypotheses])


class APIError(Exception):
    status_code = 429
    request_id = 'req_test'


class APINotebookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = io.StringIO()
        self.ns = dict(json=json, hashlib=hashlib, Path=Path, datetime=datetime, timezone=timezone,
                       time=time, unicodedata=unicodedata, wer=word_error_rate, cer=error_rate, zipfile=zipfile,
                       openai=types.SimpleNamespace(OpenAIError=APIError))
        self.execute('baseline')
        normalizer = next(node for node in ast.parse(CELLS['helpers']).body
                          if isinstance(node, ast.FunctionDef) and node.name == 'normalize_text')
        exec(compile(ast.Module(body=[normalizer], type_ignores=[]), 'normalizer', 'exec'), self.ns)
        self.ns['clips'] = [{'identity': copy.deepcopy(row), 'upload_bytes': b'test-wav-' + bytes([i])}
                            for i, row in enumerate(self.ns['baseline']['manifest'])]
        self.execute('api-helpers')
        self.ns['CHECKPOINT_PATH'] = Path(self.temp.name) / 'checkpoint.json'
        self.calls = []

        def create(**kwargs):
            number = len(self.calls)
            self.calls.append(kwargs)
            text = self.ns['clips'][number % 5]['identity']['transcription']
            return types.SimpleNamespace(model_dump=lambda **options: {'text': text, 'language': 'nepali'},
                                         _request_id=f'req_{number}')

        self.ns['client'] = types.SimpleNamespace(audio=types.SimpleNamespace(transcriptions=types.SimpleNamespace(create=create)))

    def execute(self, label):
        with contextlib.redirect_stdout(self.output):
            exec(compile(CELLS[label], label, 'exec'), self.ns)

    def run_pilot(self):
        with contextlib.redirect_stdout(self.output):
            return self.ns['run_api_pilot']()

    def test_notebook_is_clean_and_embedded_baseline_is_authentic(self):
        self.assertEqual(len(CELLS), len(NOTEBOOK['cells']))
        for index, cell in enumerate(NOTEBOOK['cells']):
            if cell['cell_type'] == 'code':
                self.assertEqual(cell['outputs'], [])
                self.assertIsNone(cell['execution_count'])
                self.assertTrue(''.join(NOTEBOOK['cells'][index - 1]['source']).startswith('### '))
                compile('\n'.join(line for line in ''.join(cell['source']).splitlines() if not line.startswith('%pip ')), cell['id'], 'exec')
        baseline = self.ns['baseline']
        archive_path = ROOT / 'results/predictions' / baseline['source_archive']
        self.assertEqual(hashlib.sha256(archive_path.read_bytes()).hexdigest(), baseline['source_sha256'])
        with zipfile.ZipFile(archive_path) as archive:
            original = json.loads(archive.read('results.json'))
        self.assertEqual(original['manifest'], baseline['manifest'])
        self.assertEqual(original['summary'], baseline['summary'])
        for row, original_row in zip(baseline['predictions'], original['predictions']):
            self.assertEqual(row, {key: original_row[key] for key in row})

    def test_requests_match_modes_and_audio_and_rerun_does_not_charge_again(self):
        state = self.run_pilot()
        self.assertEqual(len(self.calls), 10)
        for i, call in enumerate(self.calls):
            self.assertEqual(set(call), {'file', 'model', 'response_format', 'temperature'} | ({'language'} if i >= 5 else set()))
            self.assertEqual(call['model'], 'whisper-1')
            self.assertEqual(call['response_format'], 'verbose_json')
            self.assertEqual(call['temperature'], 0)
            self.assertEqual(call['file'][1], self.ns['clips'][i % 5]['upload_bytes'])
            if i >= 5:
                self.assertEqual(call['language'], 'ne')
        self.assertTrue(all(row['status'] == 'ok' for row in state['predictions']))
        self.execute('api-helpers')
        self.ns['CHECKPOINT_PATH'] = Path(self.temp.name) / 'checkpoint.json'
        self.run_pilot()
        self.assertEqual(len(self.calls), 10)
        self.execute('summary')
        self.assertTrue(all(row['complete'] and row['wer'] == row['cer'] == 0 for row in self.ns['summary'].values()))

    def test_api_error_stops_without_logging_secret_or_silently_retrying(self):
        secret = 'test-secret-do-not-save'

        def fail(**kwargs):
            self.calls.append(kwargs)
            raise APIError(secret)

        self.ns['client'].audio.transcriptions.create = fail
        state = self.run_pilot()
        self.assertEqual(state['predictions'][0]['status'], 'api_error')
        self.assertEqual(state['predictions'][0]['http_status'], 429)
        self.assertNotIn(secret, self.output.getvalue())
        self.assertNotIn(secret, self.ns['CHECKPOINT_PATH'].read_text(encoding='utf-8'))
        self.run_pilot()
        self.assertEqual(len(self.calls), 1)
        self.execute('summary')
        self.assertFalse(self.ns['summary']['auto']['complete'])
        self.assertNotIn('wer', self.ns['summary']['auto'])

    def test_interrupted_request_is_saved_as_pending_and_not_resent(self):
        def interrupt(**kwargs):
            self.calls.append(kwargs)
            raise KeyboardInterrupt()

        self.ns['client'].audio.transcriptions.create = interrupt
        with self.assertRaises(KeyboardInterrupt):
            self.run_pilot()
        state = json.loads(self.ns['CHECKPOINT_PATH'].read_text(encoding='utf-8'))
        self.assertEqual(state['predictions'][0]['status'], 'pending')
        self.run_pilot()
        self.assertEqual(len(self.calls), 1)

    def test_changed_inputs_and_duplicate_jobs_are_rejected_before_requests(self):
        self.run_pilot()
        path = self.ns['CHECKPOINT_PATH']
        state = json.loads(path.read_text(encoding='utf-8'))
        original = copy.deepcopy(state)
        state['run_spec']['request_settings']['model'] = 'different-model'
        path.write_text(json.dumps(state), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'settings differ'):
            self.run_pilot()
        original['predictions'].append(original['predictions'][0])
        path.write_text(json.dumps(original), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.run_pilot()
        self.assertEqual(len(self.calls), 10)

    def test_empty_transcripts_are_deletions_and_export_excludes_credentials(self):
        self.assertEqual(self.ns['score_text']('two words', '')['wer'], 1)
        self.assertEqual(self.ns['score_text']('two words', '')['cer'], 1)
        with self.assertRaises(ValueError):
            self.ns['score_text']('reference', None)
        self.run_pilot()
        self.ns.update(sys=sys, platform=types.SimpleNamespace(platform=lambda: 'test-platform'),
                       package_versions={'openai': '2.54.0'}, api_key='test-secret-do-not-save')
        downloads = []
        google = types.ModuleType('google')
        colab = types.ModuleType('google.colab')
        colab.files = types.SimpleNamespace(download=downloads.append)
        google.colab = colab
        with patch.dict(sys.modules, {'google': google, 'google.colab': colab}):
            # Archive creation stays inside this test's disposable directory.
            self.ns['Path'] = lambda value: Path(self.temp.name) / value
            self.execute('export')
        self.assertEqual(len(downloads), 1)
        with zipfile.ZipFile(downloads[0]) as archive:
            self.assertEqual(set(archive.namelist()), {'results.json', 'checkpoint.json'})
            output = archive.read('results.json').decode()
            self.assertNotIn(self.ns['api_key'], output)
            bundle = json.loads(output)
        self.assertEqual(len(bundle['predictions']), 10)
        self.assertTrue(all(row['complete'] for row in bundle['summary'].values()))

    def test_key_is_private_and_client_has_no_automatic_retry(self):
        created = []
        secret = 'test-secret-do-not-print'
        self.ns.update(os=types.SimpleNamespace(environ={'OPENAI_API_KEY': secret}),
                       OpenAI=lambda **kwargs: created.append(kwargs) or object())
        self.execute('api-key')
        self.assertNotIn('api_key', self.ns)
        self.assertNotIn(secret, self.output.getvalue())
        self.assertEqual(created, [dict(api_key=secret, base_url='https://api.openai.com/v1', max_retries=0, timeout=120.0)])


if __name__ == '__main__':
    unittest.main()
