"""Offline setup check. Does not download models/audio or call transcription APIs."""
import ctypes
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import sys
import sysconfig
import zipfile

ROOT = Path(__file__).resolve().parents[1]
_CUDA_HANDLES = []


def configure_cuda():
    """Keep Windows CUDA library search handles alive for this process."""
    if os.name != 'nt' or _CUDA_HANDLES:
        return
    packages = Path(sysconfig.get_paths()['purelib']) / 'nvidia'
    for name in ['cuda_runtime', 'cuda_nvrtc', 'cublas', 'cudnn']:
        directory = packages / name / 'bin'
        if directory.is_dir():
            _CUDA_HANDLES.append(os.add_dll_directory(str(directory)))
    for library in ['cudart64_12.dll', 'cublasLt64_12.dll', 'cublas64_12.dll', 'cudnn64_9.dll']:
        _CUDA_HANDLES.append(ctypes.WinDLL(library))


def verify_saved_baseline(root=ROOT):
    verification = json.loads((root / 'results/metrics/whisper_api_pilot_20261022_verified.json').read_text(encoding='utf-8'))
    archive_path = root / 'results/predictions/whisper_api_pilot_20261022T105623043636Z.zip'
    checksum = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    if checksum != verification['source_sha256']:
        raise ValueError('Saved Whisper API archive checksum differs from its verification record.')
    with zipfile.ZipFile(archive_path) as archive:
        data = json.loads(archive.read('results.json'))
    manifest = {row['clip_id'] for row in data['manifest']}
    rows = [row for row in data['predictions'] if row['mode'] == 'auto']
    if len(manifest) != 5 or len(rows) != 5 or {row['clip_id'] for row in rows} != manifest:
        raise ValueError('Expected the same five saved automatic-language API predictions.')
    return {'archive': archive_path.name, 'sha256': checksum, 'clips': 5,
            'wer': data['summary']['auto']['wer'], 'cer': data['summary']['auto']['cer']}


def main():
    report = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'python': sys.version.split()[0],
              'software_checks_passed': False, 'model_inference_performed_by_this_check': False,
              'model_or_audio_downloaded_by_this_check': False, 'paid_api_calls': 0}
    try:
        configure_cuda()
        import ctranslate2
        import datasets
        import faster_whisper
        import soundfile
        import jiwer

        report['packages'] = {name: version(name) for name in [
            'faster-whisper', 'ctranslate2', 'datasets', 'huggingface-hub', 'numpy', 'soundfile', 'jiwer',
            'nvidia-cuda-runtime-cu12', 'nvidia-cublas-cu12', 'nvidia-cudnn-cu12']}
        report['cuda_devices'] = ctranslate2.get_cuda_device_count()
        report['cuda_compute_types'] = sorted(ctranslate2.get_supported_compute_types('cuda')) if report['cuda_devices'] else []
        report['saved_api_baseline'] = verify_saved_baseline()
        report['software_checks_passed'] = report['cuda_devices'] > 0 and 'float16' in report['cuda_compute_types']
    except (ImportError, OSError, ValueError, KeyError, RuntimeError) as error:
        report['error'] = {'type': type(error).__name__, 'message': str(error)}
    destination = ROOT / '.cache/local_environment.json'
    destination.parent.mkdir(exist_ok=True)
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    destination.write_text(encoded + '\n', encoding='utf-8')
    print(encoded)
    return 0 if report['software_checks_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
