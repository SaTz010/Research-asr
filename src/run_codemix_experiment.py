"""Run the new specialist on existing inputs; separate checkpoints, no API calls."""
import argparse
from contextlib import contextmanager
import ctypes
from importlib.metadata import version
import json
import os
import platform
import sys
import time

from check_local_environment import ROOT, configure_cuda
from local_whisper_pilot import gpu_snapshot, load_state, run_clips, save_state, synchronize_cuda
from prepare_codemix_model import CONFIG, checksum
from run_evaluation import execution_lock, read_manifest, score_run


@contextmanager
def keep_awake():
    if os.name == 'nt' and not ctypes.windll.kernel32.SetThreadExecutionState(0x80000001):
        raise OSError('Cannot keep the computer awake for inference.')
    try:
        yield
    finally:
        if os.name == 'nt':
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


def specification(split):
    config = json.loads(CONFIG.read_bytes())
    for receipt in config['sources'].values():
        if checksum(ROOT / receipt['path']) != receipt['sha256']:
            raise ValueError('Frozen source changed. Preserve and investigate.')
    path = ROOT / config['sources'][split + '_manifest']['path']
    manifest, clips = read_manifest(path)
    if manifest['dataset']['split'] != split:
        raise ValueError('Wrong input split.')
    packages = {name: version(name) for name in config['runtime_packages']}
    if packages != config['runtime_packages']:
        raise ValueError('Use the pinned original inference environment.')
    directory = (ROOT / config['converted_directory']).resolve()
    if not directory.is_relative_to(ROOT.resolve()):
        raise ValueError('Converted model must remain inside the project.')
    for name, digest in config['converted_files_sha256'].items():
        if checksum(directory / name) != digest:
            raise ValueError('Converted model checksum changed.')
    spec = {'system': 'codemix_turbo', 'condition': 'forced_ne_specialist',
            'purpose': config['purpose'], 'dataset': manifest['dataset'],
            'manifest_sha256': checksum(path), 'experiment_config_sha256': checksum(CONFIG),
            'manifest': [e['identity'] for e in manifest['clips']],
            'payload_sha256': {e['identity']['clip_id']: e['payload_sha256'] for e in manifest['clips']},
            'config': config, 'packages': packages}
    return spec, clips, directory


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--split', choices=['validation', 'test'], required=True)
    parser.add_argument('--max-clips', type=int, help='Pilot prefix only; omit for the complete fixed split.')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args(argv)
    if args.max_clips is not None and (args.max_clips < 1 or args.split != 'validation'):
        raise ValueError('A prefix limit is allowed only for the validation pilot.')
    spec, clips, directory = specification(args.split)
    output = ROOT / f'results/predictions/{args.split}_codemix_turbo_20261127.json'
    metrics_path = ROOT / f'results/metrics/{output.name}'
    state = load_state(output, spec)
    print(json.dumps({'system': 'codemix_turbo', 'split': args.split, 'verified_clips': len(clips),
                      'coverage': score_run(state)['summary'], 'execute': args.execute}, indent=2), flush=True)
    if not args.execute:
        return 0
    with execution_lock(output), keep_awake():
        state = load_state(output, spec)
        coverage = score_run(state)['summary']
        if coverage['unresolved_attempts']:
            save_state(metrics_path, score_run(state))
            raise ValueError('An unresolved local checkpoint requires investigation before resuming.')
        selected = clips[:args.max_clips] if args.max_clips else clips
        if not all(any(r['clip_id'] == c['identity']['clip_id'] for r in state['predictions']) for c in selected):
            configure_cuda()
            from faster_whisper import WhisperModel
            state['runtime'] = {'python': sys.version, 'platform': platform.platform(),
                                'gpu_before_load': gpu_snapshot(), 'keep_awake': True}
            save_state(output, state)
            started = time.perf_counter()
            model = WhisperModel(str(directory), device='cuda', device_index=0, compute_type='float16',
                                 cpu_threads=4, num_workers=1, local_files_only=True)
            synchronize_cuda()
            state.update(model_load_s=time.perf_counter() - started, gpu_after_load=gpu_snapshot(),
                         actual_device=model.model.device, actual_compute_type=model.model.compute_type)
            if state['actual_device'] != 'cuda' or state['actual_compute_type'] != 'float16':
                raise ValueError('Unexpected inference device or compute type.')
            save_state(output, state)
            try:
                run_clips(model, selected, state, output)
            finally:
                save_state(metrics_path, score_run(state))
        metrics = score_run(state)
        save_state(metrics_path, metrics)
        print(json.dumps(metrics['summary'], indent=2), flush=True)
        return 0 if metrics['summary']['complete'] or args.max_clips else 1


if __name__ == '__main__':
    raise SystemExit(main())
