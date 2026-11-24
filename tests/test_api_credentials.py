"""Private credential loading is data-only, explicit, and isolated from real keys."""
import contextlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from api_credentials import read_api_key


class CredentialsTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / '.env'
        location = patch('api_credentials.PRIVATE_ENV_FILE', self.path)
        location.start()
        self.addCleanup(location.stop)

    def test_private_file_wins_over_bad_environment_and_supports_bom_comments_quotes(self):
        secret = 'sk-proj-private-file-fixture'
        self.path.write_text('# local only\n\nOPENAI_API_KEY="' + secret + '"\n', encoding='utf-8-sig')
        output = io.StringIO()
        with patch.dict(os.environ, {'OPENAI_API_KEY': '\x16'}), contextlib.redirect_stdout(output):
            self.assertEqual(read_api_key(), (secret, 'local_env_file'))
        self.assertEqual(output.getvalue(), '')

    def test_missing_file_retains_environment_and_hidden_prompt_fallback(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': '  test-key  '}):
            self.assertEqual(read_api_key(), ('test-key', 'environment'))
        with patch.dict(os.environ, {'OPENAI_API_KEY': ''}):
            self.assertEqual(read_api_key(), ('', 'hidden_prompt'))

    def test_empty_ambiguous_or_executable_content_fails_without_running_or_echoing_it(self):
        secret = 'sk-proj-not-to-be-printed'
        marker = self.path.parent / 'should-not-exist'
        for content in ['', 'OPENAI_API_KEY=', 'OTHER=' + secret,
                        'OPENAI_API_KEY=' + secret + '\nOPENAI_API_KEY=duplicate',
                        'OPENAI_API_KEY=' + secret + '\n' + f'__import__("pathlib").Path({str(marker)!r}).touch()']:
            self.path.write_text(content, encoding='utf-8')
            with self.assertRaises(ValueError) as caught:
                read_api_key()
            self.assertNotIn(secret, str(caught.exception))
            self.assertFalse(marker.exists())


if __name__ == '__main__':
    unittest.main()
