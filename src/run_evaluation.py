"""One frozen audio manifest, local or hosted Whisper; validates inputs by default."""
import argparse
import copy
from contextlib import contextmanager
from datetime import datetime, timezone
from getpass import getpass
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import re
import time

from jiwer import cer, wer

from api_credentials import read_api_key
from asr_common import normalize_text
from check_local_environment import ROOT
from local_whisper_pilot import load_local_model, load_state, run_clips, save_state
from prepare_pilot_audio import verify_payload

API_SETTINGS = {'model': 'whisper-1', 'response_format': 'verbose_json', 'temperature': 0.0}
API_BASE_URL = 'https://api.openai.com/v1'


@contextmanager
def execution_lock(output):
    lock = output.with_suffix('.lock')
    try:
        handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError('Run lock exists. Another process or a prior crash needs investigation before execution.') from None
    try:
        with os.fdopen(handle, 'w') as stream:
            stream.write(str(os.getpid()))
        yield
    finally:
        lock.unlink()


def read_manifest(path, root=ROOT):
    manifest = json.loads(path.read_text(encoding='utf-8'))
    dataset = manifest['dataset']
    split = dataset['split']
    if split not in {'validation', 'test'} or not dataset.get('revision'):
        raise ValueError('A pinned validation/test manifest is required.')
    entries = manifest['clips']
    ids = [entry['identity']['clip_id'] for entry in entries]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError('Manifest must contain unique nonempty clip identities.')
    clips = []
    for entry in entries:
        relative = Path(entry['audio_path'])
        audio_path = (root / relative).resolve()
        if relative.is_absolute() or not audio_path.is_relative_to(root.resolve()) or audio_path.suffix.lower() != '.wav':
            raise ValueError('Audio path must be a WAV inside the project.')
        payload = entry['payload_sha256']
        if not isinstance(payload, str) or not re.fullmatch(r'[0-9a-f]{64}', payload):
            raise ValueError('Missing/invalid WAV payload checksum.')
        content = audio_path.read_bytes()
        clip = verify_payload(entry['identity'], content, payload, split)
        if not entry['identity']['clip_id'].startswith(split + '/'):
            raise ValueError('Clip identity and dataset split differ.')
        clip['upload_bytes'] = content
        clips.append(clip)
    return manifest, clips


def verify_followup(manifest):
    """Only a separately pinned follow-up can change the original language setting."""
    def pinned(receipt):
        path = (ROOT / receipt['path']).resolve()
        if not path.is_relative_to(ROOT.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != receipt['sha256']:
            raise ValueError('Follow-up source path/checksum differs; preserve and investigate.')
        return path.read_bytes()

    protocol = json.loads(pinned({'path': manifest['protocol_config'], 'sha256': manifest['protocol_config_sha256']}))
    if protocol.get('condition') != 'forced_ne' or protocol.get('automatic_results_policy') != 'reuse_only':
        raise ValueError('Expected the frozen forced-Nepali-only follow-up.')
    for receipt in protocol['sources'].values():
        pinned(receipt)
    pinned(protocol['protocol_document'])
    selection = protocol['input_sets'][manifest['dataset']['split']]
    content = json.dumps(manifest['clips'], ensure_ascii=False, sort_keys=True).encode('utf-8')
    if (hashlib.sha256(content).hexdigest() != selection['clips_sha256']
            or len(manifest['clips']) != selection['clips']
            or manifest['dataset'] != selection['dataset']
            or manifest['frozen_system_configs'] != protocol['frozen_system_configs']
            or manifest['frozen_packages'] != protocol['frozen_packages']):
        raise ValueError('Follow-up selection/settings/packages differ from the pinned protocol.')


def specification_for(manifest, path, system, condition='auto'):
    if condition not in {'auto', 'forced_ne'} or manifest.get('condition', 'auto') != condition:
        raise ValueError('The explicit condition must match its manifest. Automatic baselines cannot be repurposed.')
    if condition == 'forced_ne':
        verify_followup(manifest)
    packages = {name: version(name) for name in ['numpy', 'soundfile', 'jiwer']}
    if system == 'local':
        config = json.loads((ROOT / 'configs/local_whisper_pilot.json').read_text(encoding='utf-8'))
        if condition == 'forced_ne':
            config['transcribe']['language'] = 'ne'
        packages.update({name: version(name) for name in ['faster-whisper', 'ctranslate2', 'huggingface-hub']})
    elif system == 'whisper_api':
        config = {'request_settings': copy.deepcopy(API_SETTINGS), 'base_url': API_BASE_URL, 'timeout_s': 120, 'max_retries': 0}
        if condition == 'forced_ne':
            config['request_settings']['language'] = 'ne'
        packages['openai'] = version('openai')
    else:
        raise ValueError('Choose local or whisper_api.')
    if manifest.get('frozen_system_configs') is not None and manifest['frozen_system_configs'].get(system) != config:
        raise ValueError('Runtime settings differ from the frozen protocol. Preserve the protocol; investigate before inference.')
    if manifest.get('frozen_packages') is not None and manifest['frozen_packages'].get(system) != packages:
        raise ValueError('Package versions differ from the frozen protocol. Investigate before inference.')
    spec = {'system': system, 'dataset': manifest['dataset'],
            'purpose': manifest.get('purpose'), 'manifest_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'manifest': [entry['identity'] for entry in manifest['clips']],
            'payload_sha256': {entry['identity']['clip_id']: entry['payload_sha256'] for entry in manifest['clips']},
            'config': config, 'packages': packages}
    if condition == 'forced_ne':
        spec['condition'] = condition
        spec['protocol_config_sha256'] = manifest['protocol_config_sha256']
    return spec


def score_run(state):
    rows = []
    for saved in state['predictions']:
        row = {key: saved.get(key) for key in ['clip_id', 'cmi', 'duration_s', 'status', 'error_type', 'http_status', 'parse_error']}
        hypothesis = saved.get('hypothesis')
        if saved['status'] == 'received' and isinstance(hypothesis, str):
            ref, hyp = normalize_text(saved['transcription']), normalize_text(hypothesis)
            if not ref:
                raise ValueError('Empty normalized reference cannot be scored.')
            row.update(reference=saved['transcription'], hypothesis=hypothesis,
                       normalized_reference=ref, normalized_hypothesis=hyp,
                       wer=wer(ref, hyp), cer=cer(ref.replace(' ', ''), hyp.replace(' ', '')),
                       raw_wer=wer(' '.join(saved['transcription'].split()), ' '.join(hypothesis.split())),
                       raw_cer=cer(''.join(saved['transcription'].split()), ''.join(hypothesis.split())))
        rows.append(row)
    scored = [row for row in rows if 'wer' in row]
    expected = {row['clip_id'] for row in state['run_spec']['manifest']}
    complete = len(scored) == len(expected) and {row['clip_id'] for row in scored} == expected
    summary = {'successful_clips': len(scored), 'expected_clips': len(expected), 'complete': complete,
               'unattempted_clips': len(expected) - len(rows),
               'unresolved_attempts': sum('wer' not in row for row in rows)}
    if complete:
        refs = [row['normalized_reference'] for row in scored]
        hyps = [row['normalized_hypothesis'] for row in scored]
        summary.update(wer=wer(refs, hyps), cer=cer([r.replace(' ', '') for r in refs], [h.replace(' ', '') for h in hyps]),
                       raw_wer=wer([' '.join(row['reference'].split()) for row in scored],
                                   [' '.join(row['hypothesis'].split()) for row in scored]),
                       raw_cer=cer([''.join(row['reference'].split()) for row in scored],
                                   [''.join(row['hypothesis'].split()) for row in scored]))
    return {'run_spec': state['run_spec'], 'summary': summary, 'per_clip': rows,
            'note': 'Validation manifests are runtime diagnostics, not held-out benchmark findings. Failures are coverage events, not invented ASR scores.'}


def run_api(clips, state, output, client, max_requests):
    from openai import OpenAIError
    if isinstance(max_requests, bool) or not isinstance(max_requests, int) or max_requests < 1:
        raise ValueError('Set a positive explicit maximum of new API requests.')
    state.pop('paid_api_calls', None)
    saved = {row['clip_id']: row for row in state['predictions']}
    made = 0
    for number, clip in enumerate(clips, 1):
        identity = clip['identity']
        if identity['clip_id'] in saved:
            previous = saved[identity['clip_id']]
            if previous['status'] != 'received' or not isinstance(previous.get('hypothesis'), str):
                print('STOP: failed, pending or unparsed response. Preserve/export and investigate before any retry.')
                break
            continue
        if made >= max_requests:
            print('Stopped at the explicit maximum of new API requests.')
            break
        record = {**identity, 'status': 'pending', 'requested_at_utc': datetime.now(timezone.utc).isoformat()}
        state['predictions'].append(record)
        state['api_request_attempts'] = state.get('api_request_attempts', 0) + 1
        save_state(output, state)
        made += 1
        started = time.perf_counter()
        try:
            response = client.audio.transcriptions.create(
                file=(f'clip_{number:05d}.wav', clip['upload_bytes'], 'audio/wav'),
                **state['run_spec']['config']['request_settings'])
        except OpenAIError as error:
            record.update(status='api_error', error_type=type(error).__name__,
                          http_status=getattr(error, 'status_code', None), request_id=getattr(error, 'request_id', None),
                          request_latency_s=time.perf_counter() - started)
            save_state(output, state)
            print('API stopped:', record['error_type'], '| HTTP:', record['http_status'], '| no automatic retry.')
            break
        record.update(status='received', response=response.model_dump(mode='json'),
                      request_id=getattr(response, '_request_id', None), request_latency_s=time.perf_counter() - started)
        save_state(output, state)
        hypothesis = record['response'].get('text') if isinstance(record['response'], dict) else None
        if not isinstance(hypothesis, str):
            record['parse_error'] = 'API response text is not a string.'
            save_state(output, state)
            print('STOP: raw paid response preserved; parsing needs investigation.')
            break
        record['hypothesis'] = hypothesis
        save_state(output, state)
        print('Saved API response:', identity['clip_id'])
    return state


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--system', choices=['local', 'whisper_api'], required=True)
    parser.add_argument('--condition', choices=['auto', 'forced_ne'], default='auto',
                        help='Must match the manifest; default preserves the published automatic condition.')
    parser.add_argument('--execute', action='store_true', help='Run inference; omitted means input validation only.')
    parser.add_argument('--max-requests', type=int, help='Required for paid API execution; maximum new calls this invocation.')
    args = parser.parse_args(argv)
    manifest, clips = read_manifest(args.manifest)
    if not re.fullmatch(r'[A-Za-z0-9_-]+', args.manifest.stem):
        raise ValueError('Use a simple manifest filename with letters, digits, hyphens and underscores.')
    spec = specification_for(manifest, args.manifest, args.system, args.condition)
    name = args.manifest.stem + '_' + args.system
    output = ROOT / 'results/predictions' / (name + '.json')
    metrics_path = ROOT / 'results/metrics' / (name + '.json')
    state = load_state(output, spec)
    summary = score_run(state)['summary']
    print(json.dumps({'system': args.system, 'condition': args.condition,
                      'input_clips_verified': len(clips),
                      'audio_s': sum(row['identity']['decoded_duration_s'] for row in clips),
                      'coverage': summary, 'execute_requested': args.execute}, indent=2))
    if not args.execute:
        print('DRY RUN: no model inference, API authentication or transcription requests.')
        return 0
    if manifest['dataset']['split'] == 'test' and manifest.get('frozen_for_inference') is not True:
        raise ValueError('Held-out execution requires a reviewed manifest marked frozen_for_inference after the reference audit.')
    if args.system == 'whisper_api' and (args.max_requests is None or args.max_requests < 1):
        raise ValueError('Paid execution requires --max-requests with a positive limit.')
    with execution_lock(output):
        state = load_state(output, spec)
        current = score_run(state)['summary']
        if current['unresolved_attempts']:
            save_state(metrics_path, score_run(state))
            print('STOP: saved unresolved attempt; no new calls. Metrics exported for investigation.')
            return 1
        if not current['complete']:
            if args.system == 'local':
                model = load_local_model(spec['config'], state, output)
                run_clips(model, clips, state, output)
            else:
                from openai import OpenAI
                key, _ = read_api_key()
                key = key or getpass('OpenAI API key (hidden): ').strip()
                if not key:
                    raise ValueError('No API key supplied. Do not put credentials in source or chat.')
                client = OpenAI(api_key=key, base_url=API_BASE_URL, timeout=120, max_retries=0)
                del key
                try:
                    run_api(clips, state, output, client, args.max_requests)
                finally:
                    client.close()
        metrics = score_run(state)
        save_state(metrics_path, metrics)
        print(json.dumps(metrics['summary'], indent=2))
        return 0 if metrics['summary']['complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
