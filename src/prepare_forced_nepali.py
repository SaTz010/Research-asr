"""Freeze forced-Nepali manifests while preserving the published automatic runs."""
import copy
import hashlib
import json

from check_local_environment import ROOT
from compare_audited_references import load_verified_inputs
from prepare_pilot_audio import load_baseline
from prepare_test_set import frozen_write

PROTOCOL = 'configs/forced_ne_protocol_20261124.json'
DOCUMENT = 'reports/protocol_forced_ne_20261124.md'
MAIN = 'data/manifests/test_cs_forced_ne_20261124.json'
PILOT = 'data/manifests/validation_forced_ne_20261124.json'


def clips_digest(entries):
    return hashlib.sha256(json.dumps(entries, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


def forced_configs(configs):
    result = copy.deepcopy(configs)
    if result['local']['transcribe']['language'] is not None or 'language' in result['whisper_api']['request_settings']:
        raise ValueError('Expected the original automatic baseline settings.')
    result['local']['transcribe']['language'] = 'ne'
    result['whisper_api']['request_settings']['language'] = 'ne'
    return result


def main():
    _, _, original, _, _ = load_verified_inputs()
    baseline = load_baseline()
    extra = json.loads((ROOT / 'data/manifests/validation_check_20261104.json').read_bytes())
    for dataset in [baseline['dataset'], extra['dataset']]:
        if any(dataset[k] != original['dataset'][k] for k in ['id', 'revision', 'config']):
            raise ValueError('Validation sources differ from the pinned dataset.')
    entries = []
    for identity in baseline['manifest']:
        payload = baseline['run_spec']['payload_sha256'][identity['clip_id']]
        entries.append({'identity': identity, 'payload_sha256': payload,
                        'audio_path': f'.cache/pilot_audio/{payload}.wav'})
    entries += copy.deepcopy(extra['clips'])
    entries.sort(key=lambda entry: entry['identity']['clip_id'])
    if len(entries) != 20 or len({e['identity']['clip_id'] for e in entries}) != 20:
        raise ValueError('Expected twenty distinct validation clips.')
    if len(original['clips']) != 1198 or {e['identity']['clip_id'] for e in entries} & {
            e['identity']['clip_id'] for e in original['clips']}:
        raise ValueError('Expected disjoint validation and frozen test selections.')
    paths = {
        'automatic_manifest': 'data/manifests/test_cs_benchmark_20261112.json',
        'automatic_protocol': 'configs/evaluation_protocol_20261112.json',
        'automatic_protocol_document': 'reports/protocol_20261112.md',
        'reference_audit': original['reference_audit'],
        'automatic_local': 'results/predictions/test_cs_benchmark_20261112_local.json',
        'automatic_api': 'results/predictions/test_cs_benchmark_20261112_whisper_api.json',
        'automatic_local_verified': 'results/metrics/test_cs_benchmark_20261112_local_verified.json',
        'automatic_api_verified': 'results/metrics/test_cs_benchmark_20261112_whisper_api_verified.json',
        'original_api_pilot': 'results/predictions/whisper_api_pilot_20261022T105623043636Z.zip',
        'additional_validation': 'data/manifests/validation_check_20261104.json',
    }
    receipt = lambda path: {'path': path, 'sha256': hashlib.sha256((ROOT / path).read_bytes()).hexdigest()}
    datasets = {split: {**original['dataset'], 'split': split} for split in ['validation', 'test']}
    sets = {'validation': entries, 'test': original['clips']}
    protocol = {'prepared_on': '2026-11-24', 'condition': 'forced_ne',
                'automatic_results_policy': 'reuse_only', 'status': 'frozen_before_forced_ne_inference',
                'protocol_document': receipt(DOCUMENT), 'sources': {k: receipt(v) for k, v in paths.items()},
                'frozen_system_configs': forced_configs(original['frozen_system_configs']),
                'frozen_packages': original['frozen_packages'],
                'input_sets': {split: {'dataset': datasets[split], 'clips': len(rows),
                                      'clips_sha256': clips_digest(rows)} for split, rows in sets.items()},
                'analysis': original_protocol_analysis(original),
                'budget': {'price_usd_per_minute_checked_20261124': '0.006',
                           'main_api_max_new_requests': 1198, 'validation_api_max_new_requests': 20,
                           'automatic_api_requests_planned': 0, 'automatic_retries': 0,
                           'user_reported_balance_usd': '2.29', 'balance_independently_verified': False,
                           'main_estimate_usd': '1.2556', 'validation_estimate_usd': '0.0190',
                           'total_with_20_percent_reserve_usd': '1.53'},
                'limitations': ['Exploratory follow-up after inspection of the published automatic outputs.',
                                'Hosted automatic and forced conditions have different execution dates.',
                                'No causal isolation of language-setting effects from service variability.',
                                'No independently verified detection confidence in a forced-language label.']}
    frozen_write(ROOT / PROTOCOL, protocol)
    protocol_sha = receipt(PROTOCOL)['sha256']
    for split, name in [('validation', PILOT), ('test', MAIN)]:
        manifest = {'purpose': f'{split}_forced_ne_language_setting_followup', 'condition': 'forced_ne',
                    'dataset': datasets[split], 'clips': sets[split], 'frozen_for_inference': True,
                    'protocol_config': PROTOCOL, 'protocol_config_sha256': protocol_sha,
                    'reference_audit': original['reference_audit'],
                    'reference_audit_sha256': original['reference_audit_sha256'],
                    'frozen_system_configs': protocol['frozen_system_configs'],
                    'frozen_packages': protocol['frozen_packages']}
        frozen_write(ROOT / name, manifest)
    print(json.dumps({'protocol': PROTOCOL, 'main_manifest': MAIN, 'main_clips': 1198,
                      'validation_manifest': PILOT, 'validation_clips': 20,
                      'automatic_outputs': 'reuse unchanged', 'inference_performed': False, 'paid_requests': 0}, indent=2))


def original_protocol_analysis(manifest):
    return json.loads((ROOT / manifest['protocol_config']).read_bytes())['analysis']


if __name__ == '__main__':
    main()
