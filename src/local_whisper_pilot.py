"""Five validation clips on this GPU, compared with existing API outputs; no API calls."""
from dataclasses import asdict
from datetime import datetime, timezone
import ctypes
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

from jiwer import cer, wer

from asr_common import normalize_text
from check_local_environment import ROOT, configure_cuda, verify_saved_baseline
from prepare_pilot_audio import load_baseline, recover_audio

OUTPUT = ROOT / 'results/predictions/local_whisper_large_v2_pilot.json'
METRICS = ROOT / 'results/metrics/local_whisper_large_v2_pilot.json'
MODEL_DIRECTORY = ROOT / '.cache/models/whisper-large-v2'


def save_state(path, state):
    temporary = path.with_suffix('.tmp')
    payload = json.dumps(state, ensure_ascii=False, indent=2, allow_nan=False)
    for attempt in range(8):
        try:
            temporary.write_text(payload, encoding='utf-8')
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 7:
                raise
            # Windows sync/indexing can briefly hold either file; preserve atomic saves.
            time.sleep(min(0.1 * 2 ** attempt, 1.0))


def load_state(path, specification):
    if not path.exists():
        return {'created_at_utc': datetime.now(timezone.utc).isoformat(), 'run_spec': specification,
                'predictions': [], 'paid_api_calls': 0}
    state = json.loads(path.read_text(encoding='utf-8'))
    if state['run_spec'] != specification:
        raise ValueError('Existing pilot settings/inputs differ; preserve it separately, do not overwrite.')
    identities = {row['clip_id']: row for row in specification['manifest']}
    keys = [row['clip_id'] for row in state['predictions']]
    if len(keys) != len(set(keys)) or not set(keys) <= set(identities):
        raise ValueError('Duplicate or unknown saved clip.')
    for row in state['predictions']:
        if row['status'] not in {'received', 'pending', 'local_error', 'api_error'}:
            raise ValueError('Unknown local checkpoint status.')
        if any(row[key] != value for key, value in identities[row['clip_id']].items()):
            raise ValueError('Saved reference/audio identity differs.')
    return state


def gpu_snapshot():
    result = subprocess.run(['nvidia-smi', '-i', '0', '--query-gpu=name,memory.total,memory.used,driver_version',
                             '--format=csv,noheader,nounits'], check=True, capture_output=True, text=True, timeout=15,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    name, total, used, driver = [part.strip() for part in result.stdout.strip().split(',')]
    return {'name': name, 'total_memory_mib': int(total), 'used_memory_mib': int(used), 'driver': driver}


def synchronize_cuda():
    code = ctypes.WinDLL('cudart64_12.dll').cudaDeviceSynchronize()
    if code:
        raise RuntimeError(f'CUDA synchronization failed with status {code}.')


def run_clips(model, clips, state, path, synchronize=synchronize_cuda, snapshot=gpu_snapshot):
    saved = {row['clip_id']: row for row in state['predictions']}
    for clip in clips:
        identity = clip['identity']
        if identity['clip_id'] in saved:
            if saved[identity['clip_id']]['status'] != 'received':
                print('STOP: an earlier local attempt is incomplete/failed; preserve it and investigate.', flush=True)
                break
            print('Reused saved local response:', identity['clip_id'], flush=True)
            continue
        row = {**identity, 'status': 'pending', 'requested_at_utc': datetime.now(timezone.utc).isoformat()}
        state['predictions'].append(row)
        save_state(path, state)
        try:
            synchronize()
            started = time.perf_counter()
            segments, info = model.transcribe(clip['audio'], **state['run_spec']['config']['transcribe'])
            segments = list(segments)
            synchronize()
            elapsed = time.perf_counter() - started
            row.update(status='received', transcription_s=elapsed, response={
                'segments': [asdict(segment) for segment in segments], 'info': asdict(info)},
                hypothesis=' '.join(segment.text.strip() for segment in segments).strip())
            # Save raw generation before metrics or hardware queries can fail.
            save_state(path, state)
        except (RuntimeError, ValueError, OSError, MemoryError) as error:
            if row['status'] == 'pending':
                row.update(status='local_error', error_type=type(error).__name__, error_message=str(error))
                save_state(path, state)
            raise
        row['gpu_after_transcription'] = snapshot()
        save_state(path, state)
        print('LOCAL:', identity['clip_id'], '|', row['hypothesis'], flush=True)
    return state


def score_saved(state, baseline):
    old = {row['clip_id']: row for row in baseline['predictions'] if row['mode'] == 'auto'}
    comparisons = []
    for row in state['predictions']:
        if row['status'] != 'received':
            continue
        ref, hyp = normalize_text(row['transcription']), normalize_text(row['hypothesis'])
        if not ref:
            raise ValueError('Empty normalized reference cannot be scored.')
        if old[row['clip_id']]['normalized_reference'] != ref:
            raise ValueError('Local and API scoring references differ.')
        comparisons.append({'clip_id': row['clip_id'], 'cmi': row['cmi'],
                            'normalized_reference': ref, 'normalized_hypothesis': hyp,
                            'local_wer': wer(ref, hyp), 'local_cer': cer(ref.replace(' ', ''), hyp.replace(' ', '')),
                            'api_wer': old[row['clip_id']]['wer'], 'api_cer': old[row['clip_id']]['cer'],
                            'local_language': row['response']['info']['language']})
    complete = len(comparisons) == len(baseline['manifest']) and {row['clip_id'] for row in comparisons} == set(old)
    summary = {'successful_clips': len(comparisons), 'expected_clips': len(old), 'complete': complete}
    if complete:
        refs, hyps = [row['normalized_reference'] for row in comparisons], [row['normalized_hypothesis'] for row in comparisons]
        summary.update(local_wer=wer(refs, hyps),
                       local_cer=cer([ref.replace(' ', '') for ref in refs], [hyp.replace(' ', '') for hyp in hyps]),
                       api_wer=baseline['summary']['auto']['wer'], api_cer=baseline['summary']['auto']['cer'],
                       transcription_s=sum(row['transcription_s'] for row in state['predictions']),
                       audio_s=sum(row['decoded_duration_s'] for row in baseline['manifest']))
    return {'summary': summary, 'per_clip': comparisons,
            'limitations': ['Five validation clips, not a final CMI analysis or broad system ranking.',
                            'API and local implementations/decoding may differ; hosting is not isolated.',
                            'GPU memory snapshots are whole-device observations, not exact per-model peaks.',
                            'Local elapsed time includes materialized generation; API turnaround includes networking.',
                            'Model-load timing is process startup with uncontrolled operating-system file cache.']}


def load_local_model(config, state, output):
    configure_cuda()
    if not (MODEL_DIRECTORY / 'model.bin').exists():
        from huggingface_hub import snapshot_download
        print('Downloading pinned Large V2 model...', flush=True)
        snapshot_download(config['model_id'], revision=config['model_revision'], local_dir=MODEL_DIRECTORY,
                          allow_patterns=['model.bin', 'config.json', 'tokenizer.json', 'vocabulary.txt', 'README.md'], token=False)
    model_hashes = {}
    for name in ['model.bin', 'config.json', 'tokenizer.json', 'vocabulary.txt']:
        with (MODEL_DIRECTORY / name).open('rb') as source:
            model_hashes[name] = hashlib.file_digest(source, 'sha256').hexdigest()
    if model_hashes['model.bin'] != config['model_sha256']:
        raise ValueError('Model weight checksum differs from the pinned download receipt.')
    state['model_files_sha256'] = model_hashes
    state['runtime'] = {'python': sys.version, 'platform': platform.platform(), 'gpu_before_load': gpu_snapshot()}
    save_state(output, state)
    from faster_whisper import WhisperModel
    started = time.perf_counter()
    try:
        model = WhisperModel(str(MODEL_DIRECTORY), device=config['device'], device_index=0,
                             compute_type=config['compute_type'], cpu_threads=4, num_workers=1, local_files_only=True)
        synchronize_cuda()
    except (RuntimeError, ValueError, OSError, MemoryError) as error:
        state['model_load_error'] = {'type': type(error).__name__, 'message': str(error)}
        save_state(output, state)
        raise
    state.update(model_load_s=time.perf_counter() - started, gpu_after_load=gpu_snapshot(),
                 actual_device=model.model.device, actual_compute_type=model.model.compute_type)
    save_state(output, state)
    return model


def main():
    configure_cuda()
    baseline = load_baseline()
    config = json.loads((ROOT / 'configs/local_whisper_pilot.json').read_text(encoding='utf-8'))
    packages = {name: version(name) for name in ['faster-whisper', 'ctranslate2', 'datasets', 'huggingface-hub', 'numpy', 'soundfile', 'jiwer']}
    specification = {'config': config, 'dataset': baseline['dataset'], 'manifest': baseline['manifest'],
                     'payload_sha256': baseline['run_spec']['payload_sha256'],
                     'saved_api_baseline': verify_saved_baseline(), 'packages': packages}
    state = load_state(OUTPUT, specification)
    if len(state['predictions']) == 5 and all(row['status'] == 'received' for row in state['predictions']):
        save_state(METRICS, score_saved(state, baseline))
        print('All five local responses already saved; rescored without inference or API requests.')
        return
    clips = recover_audio(baseline)
    model = load_local_model(config, state, OUTPUT)
    run_clips(model, clips, state, OUTPUT)
    metrics = score_saved(state, baseline)
    save_state(METRICS, metrics)
    print(json.dumps(metrics['summary'], indent=2), flush=True)
    print('Saved:', OUTPUT, '\nMetrics:', METRICS)


if __name__ == '__main__':
    main()
