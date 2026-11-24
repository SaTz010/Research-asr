"""Authentication troubleshooting does not generate speech or expose credentials."""
import json
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import httpx
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from check_api_auth import diagnose, main


class ApiAuthTests(unittest.TestCase):
    def test_cli_uses_environment_or_prompt_without_writing_the_secret(self):
        secret = 'sk-proj-environment-secret'
        for env_value, expected_source in [(secret, 'environment'), (' ', 'hidden_prompt'), ('\x16', 'local_env_file')]:
            with self.subTest(source=expected_source), tempfile.TemporaryDirectory() as folder:
                output = io.StringIO()
                private_file = Path(folder) / 'private.env'
                if expected_source == 'local_env_file':
                    private_file.write_text('OPENAI_API_KEY=' + secret, encoding='utf-8')
                with patch.dict('os.environ', {'OPENAI_API_KEY': env_value}), patch('check_api_auth.ROOT', Path(folder)), \
                        patch('api_credentials.PRIVATE_ENV_FILE', private_file), \
                        patch('check_api_auth.getpass', return_value=secret) as prompt, \
                        patch('check_api_auth.diagnose', return_value={'status': 'model_metadata_access_succeeded'}) as check, \
                        contextlib.redirect_stdout(output):
                    self.assertEqual(main(), 0)
                check.assert_called_once_with(secret)
                if expected_source != 'hidden_prompt':
                    prompt.assert_not_called()
                else:
                    prompt.assert_called_once()
                saved = (Path(folder) / '.cache/api_auth_diagnostic.json').read_text(encoding='utf-8')
                self.assertNotIn(secret, saved + output.getvalue())
                self.assertEqual(json.loads(saved)['credential_source'], expected_source)

    def test_bad_paste_is_reported_without_network_or_secret(self):
        for key in ['', 'not-an-api-key', 'sk-proj-masked...key', '"sk-proj-quoted"', 'sk-proj-a b', 'sk-proj-a\x16', 'sk-proj-é']:
            with self.subTest(key_type=len(key)), patch('check_api_auth.OpenAI') as factory:
                result = diagnose(key)
                self.assertFalse(result['network_request_made'])
                self.assertEqual(result['status'], 'input_format_problem_recopy_complete_secret_key')
                factory.assert_not_called()
                if len(key) > 3:
                    self.assertNotIn(key, json.dumps(result))

    def run_mock(self, status, body):
        secret = 'sk-proj-private-test-secret'
        requests = []

        def respond(request):
            requests.append(request)
            self.assertEqual(request.method, 'GET')
            self.assertEqual(str(request.url), 'https://api.openai.com/v1/models/whisper-1')
            self.assertEqual(request.content, b'')
            return httpx.Response(status, headers={'x-request-id': 'req_auth_test'}, json=body)

        def factory(**kwargs):
            self.assertEqual(kwargs['api_key'], secret)
            self.assertEqual(kwargs['max_retries'], 0)
            self.assertEqual(kwargs['timeout'], 30)
            self.assertEqual(kwargs['base_url'], 'https://api.openai.com/v1')
            return OpenAI(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(respond)))

        with patch('check_api_auth.OpenAI', side_effect=factory):
            result = diagnose('  ' + secret + '  ')
        self.assertEqual(len(requests), 1)
        self.assertFalse(result['audio_uploaded'])
        self.assertFalse(result['transcription_requested'])
        self.assertNotIn(secret, json.dumps(result))
        return result

    def test_success_only_confirms_metadata_access(self):
        result = self.run_mock(200, {'id': 'whisper-1', 'object': 'model', 'created': 0, 'owned_by': 'openai'})
        self.assertEqual(result['status'], 'model_metadata_access_succeeded')
        self.assertIn('not verified', result['note'])

    def test_401_reports_code_but_never_secret_echoed_in_provider_message(self):
        result = self.run_mock(401, {'error': {'message': 'Incorrect API key: sk-proj-private-test-secret', 'type': 'invalid_request_error', 'code': 'invalid_api_key'}})
        self.assertEqual(result['http_status'], 401)
        self.assertEqual(result['error_code'], 'invalid_api_key')
        self.assertEqual(result['request_id'], 'req_auth_test')
        self.assertNotIn('message', result)

    def test_unknown_error_code_cannot_leak_provider_data(self):
        result = self.run_mock(401, {'error': {'message': 'hidden', 'type': 'invalid_request_error', 'code': 'sk-proj-private-test-secret'}})
        self.assertIsNone(result['error_code'])


if __name__ == '__main__':
    unittest.main()
