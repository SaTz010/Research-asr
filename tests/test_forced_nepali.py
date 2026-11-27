"""Language setting must reach inference without changing/overwriting automatic runs."""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import httpx
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import run_evaluation as runner
from local_whisper_pilot import load_state, save_state
from prepare_forced_nepali import clips_digest, forced_configs


class ForcedNepaliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.root_patch = patch.object(runner, 'ROOT', self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.configs = {'local': {'model_id': 'pinned-model', 'transcribe': {'language': None, 'beam_size': 5}},
                        'whisper_api': {'request_settings': copy.deepcopy(runner.API_SETTINGS),
                                        'base_url': runner.API_BASE_URL, 'timeout_s': 120, 'max_retries': 0}}
        (self.root / 'configs').mkdir()
        save_state(self.root / 'configs/local_whisper_pilot.json', self.configs['local'])
        self.manifest = {'condition': 'forced_ne', 'dataset': {'id': 'test', 'revision': 'fixed', 'config': 'default', 'split': 'test'},
                         'purpose': 'forced-followup', 'clips': [{'identity': {'clip_id': 'test/one'}, 'payload_sha256': 'a'*64}],
                         'protocol_config': 'configs/followup.json',
                         'frozen_system_configs': forced_configs(self.configs),
                         'frozen_packages': {s: {name: 'fixture' for name in names} for s, names in {
                             'local': ['numpy', 'soundfile', 'jiwer', 'faster-whisper', 'ctranslate2', 'huggingface-hub'],
                             'whisper_api': ['numpy', 'soundfile', 'jiwer', 'openai']}.items()}}
        (self.root / 'baseline.json').write_text('{"mode":"auto"}', encoding='utf-8')
        (self.root / 'protocol.md').write_text('fixed protocol', encoding='utf-8')
        receipt = lambda path: {'path': path, 'sha256': hashlib.sha256((self.root / path).read_bytes()).hexdigest()}
        self.protocol = {'condition': 'forced_ne', 'automatic_results_policy': 'reuse_only',
                         'sources': {'baseline': receipt('baseline.json')}, 'protocol_document': receipt('protocol.md'),
                         'input_sets': {'test': {'dataset': self.manifest['dataset'], 'clips': 1,
                                                'clips_sha256': clips_digest(self.manifest['clips'])}},
                         'frozen_system_configs': self.manifest['frozen_system_configs'],
                         'frozen_packages': self.manifest['frozen_packages']}
        save_state(self.root / 'configs/followup.json', self.protocol)
        self.manifest['protocol_config_sha256'] = receipt('configs/followup.json')['sha256']
        self.path = self.root / 'test_forced_ne.json'
        save_state(self.path, self.manifest)

    def spec(self, system):
        with patch.object(runner, 'version', return_value='fixture'):
            return runner.specification_for(self.manifest, self.path, system, 'forced_ne')

    def test_only_language_changes_and_automatic_settings_are_not_mutated(self):
        original = copy.deepcopy(self.configs)
        changed = forced_configs(self.configs)
        self.assertEqual(self.configs, original)
        self.assertEqual(changed['local']['transcribe']['language'], 'ne')
        self.assertEqual(changed['whisper_api']['request_settings']['language'], 'ne')
        changed['local']['transcribe']['language'] = None
        changed['whisper_api']['request_settings'].pop('language')
        self.assertEqual(changed, original)
        self.assertNotIn('language', runner.API_SETTINGS)
        self.assertEqual(self.spec('local')['config']['transcribe']['language'], 'ne')
        self.assertEqual(self.spec('whisper_api')['config']['request_settings']['language'], 'ne')

    def test_condition_must_be_explicit_and_cannot_repurpose_the_auto_manifest(self):
        with self.assertRaisesRegex(ValueError, 'explicit condition'):
            runner.specification_for(self.manifest, self.path, 'whisper_api')
        automatic = {k: v for k, v in self.manifest.items() if k != 'condition'}
        with self.assertRaisesRegex(ValueError, 'explicit condition'):
            runner.specification_for(automatic, self.path, 'whisper_api', 'forced_ne')

    def test_source_drift_selection_drift_and_protocol_drift_stop_before_execution(self):
        self.spec('whisper_api')
        (self.root / 'baseline.json').write_text('changed', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            self.spec('whisper_api')
        (self.root / 'baseline.json').write_text('{"mode":"auto"}', encoding='utf-8')
        self.manifest['clips'][0]['identity']['clip_id'] = 'test/changed'
        with self.assertRaisesRegex(ValueError, 'selection'):
            self.spec('whisper_api')
        self.manifest['clips'][0]['identity']['clip_id'] = 'test/one'
        (self.root / 'protocol.md').write_text('changed protocol', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            self.spec('whisper_api')

    def test_automatic_checkpoints_cannot_be_overwritten_by_forced_specs(self):
        spec = self.spec('whisper_api')
        path = self.root / 'automatic.json'
        automatic = copy.deepcopy(spec)
        automatic.pop('condition')
        automatic['config']['request_settings'].pop('language')
        save_state(path, load_state(path, automatic))
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'settings/inputs differ'):
            load_state(path, spec)
        self.assertEqual(path.read_bytes(), before)

    def test_real_sdk_sends_ne_and_resume_does_not_resubmit(self):
        spec = self.spec('whisper_api')
        state = load_state(self.root / 'forced.json', spec)
        clip = {'identity': {'clip_id': 'test/one'}, 'upload_bytes': b'offline-fixture-wav'}
        requests = []

        def respond(request):
            requests.append(request)
            self.assertIn(b'name="language"\r\n\r\nne', request.content)
            self.assertIn(b'name="model"\r\n\r\nwhisper-1', request.content)
            return httpx.Response(200, json={'text': 'saved', 'language': 'nepali'}, headers={'x-request-id': 'offline-forced'})

        with OpenAI(api_key='offline-fixture-key', max_retries=0,
                    http_client=httpx.Client(transport=httpx.MockTransport(respond))) as client:
            with contextlib.redirect_stdout(io.StringIO()):
                runner.run_api([clip], state, self.root / 'forced.json', client, 1)
                runner.run_api([clip], state, self.root / 'forced.json', client, 1)
        self.assertEqual(len(requests), 1)
        self.assertEqual(state['api_request_attempts'], 1)
        self.assertNotIn('offline-fixture-key', (self.root / 'forced.json').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
