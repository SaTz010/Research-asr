"""Read the OpenAI credential from the project's Git-ignored .env file."""
import os
from pathlib import Path

PRIVATE_ENV_FILE = Path(__file__).resolve().parents[1] / '.env'


def read_api_key():
    if not PRIVATE_ENV_FILE.exists():
        key = os.environ.get('OPENAI_API_KEY', '').strip()
        return key, 'environment' if key else 'hidden_prompt'
    key = None
    # This is deliberately a one-setting file, never executable Python/shell code.
    for line in PRIVATE_ENV_FILE.read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        name, separator, value = line.partition('=')
        if name.strip() != 'OPENAI_API_KEY' or not separator or key is not None:
            raise ValueError('The private .env file must contain exactly one OPENAI_API_KEY assignment.')
        key = value.strip()
        if len(key) >= 2 and key[0] == key[-1] and key[0] in {'"', "'"}:
            key = key[1:-1].strip()
    if not key:
        raise ValueError(f'Paste your full key after OPENAI_API_KEY= in {PRIVATE_ENV_FILE} and save the file.')
    return key, 'local_env_file'
