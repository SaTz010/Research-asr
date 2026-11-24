"""Check pasted-key formatting and model metadata access; never uploads audio."""
from getpass import getpass
import json
import os
import re

from openai import OpenAI, OpenAIError

from api_credentials import read_api_key
from check_local_environment import ROOT
from local_whisper_pilot import save_state

SAFE_ERROR_CODES = {'invalid_api_key', 'ip_not_authorized', 'insufficient_permissions',
                    'permission_denied', 'model_not_found', 'organization_not_found',
                    'project_not_found', 'account_deactivated', 'rate_limit_exceeded', 'insufficient_quota'}


def diagnose(raw_key):
    key = raw_key.strip()
    checks = {'characters_pasted': len(key), 'starts_with_sk': key.startswith('sk-'),
              'contains_whitespace': any(c.isspace() for c in key),
              'contains_non_ascii': not key.isascii(),
              'contains_control_characters': any(not c.isprintable() for c in key),
              'contains_masked_ellipsis': '...' in key or '…' in key,
              'contains_quotes': any(c in key for c in ['"', "'"])}
    report = {'key_input_checks': checks, 'network_request_made': False, 'audio_uploaded': False,
              'transcription_requested': False,
              'organization_override_present': bool(os.environ.get('OPENAI_ORG_ID')),
              'project_override_present': bool(os.environ.get('OPENAI_PROJECT_ID'))}
    if (not checks['starts_with_sk'] or any(checks[name] for name in
            ['contains_whitespace', 'contains_non_ascii', 'contains_control_characters', 'contains_masked_ellipsis', 'contains_quotes'])):
        report['status'] = 'input_format_problem_recopy_complete_secret_key'
        return report
    client = OpenAI(api_key=key, base_url='https://api.openai.com/v1', timeout=30, max_retries=0)
    try:
        report['network_request_made'] = True
        client.models.retrieve('whisper-1')
        report['status'] = 'model_metadata_access_succeeded'
        report['note'] = 'Authentication/model metadata access works; transcription permissions, billing and audio access are not verified by this GET.'
    except OpenAIError as error:
        code = getattr(error, 'code', None)
        request_id = getattr(error, 'request_id', None)
        report.update(status='model_metadata_access_failed', error_type=type(error).__name__,
                      http_status=getattr(error, 'status_code', None),
                      error_code=code if isinstance(code, str) and code in SAFE_ERROR_CODES else None,
                      request_id=request_id if isinstance(request_id, str) and re.fullmatch(r'req_[A-Za-z0-9_-]{1,128}', request_id) else None)
        # Provider exception messages can echo credentials; export only approved metadata.
    finally:
        client.close()
    return report


def main():
    key, source = read_api_key()
    if not key:
        key = getpass('Paste the complete OpenAI API key (hidden; input is not echoed): ')
    report = diagnose(key)
    report['credential_source'] = source
    del key
    path = ROOT / '.cache/api_auth_diagnostic.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    save_state(path, report)
    print(json.dumps(report, indent=2))
    return 0 if report['status'] == 'model_metadata_access_succeeded' else 1


if __name__ == '__main__':
    raise SystemExit(main())
