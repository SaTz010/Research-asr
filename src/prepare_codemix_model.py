"""Convert the pinned public checkpoint without changing the benchmark environment."""
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / '.cache/models/codemix-turbo-8eff5c48'
TARGET = ROOT / '.cache/models/codemix-turbo-8eff5c48-ct2-fp16'
CONFIG = ROOT / 'configs/codemix_turbo_experiment_20261127.json'
MODEL_ID = 'ailabpvtltd/whisper-large-v3-turbo-nepali-english-codemix-asr'
REVISION = '8eff5c489628694a9f3ff2a02f3225ccfd6c6046'
WEIGHTS_SHA256 = '4c0a8779438f23ac518d6e4379c0f6edfacb8a470320fceb43081f9936eef549'


def checksum(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    if checksum(SOURCE / 'model.safetensors') != WEIGHTS_SHA256:
        raise ValueError('Original safetensors checksum differs from the pinned public checkpoint.')
    if CONFIG.exists():
        saved = json.loads(CONFIG.read_bytes())
        if any(checksum(TARGET / name) != digest for name, digest in saved['converted_files_sha256'].items()):
            raise ValueError('Existing converted files differ. Preserve and investigate.')
        print('Reused the existing checked conversion and frozen configuration.')
        return
    from ctranslate2.converters import TransformersConverter
    converter = TransformersConverter(str(SOURCE), copy_files=['tokenizer.json', 'preprocessor_config.json'],
                                      load_as_float16=True, trust_remote_code=False)
    converter.convert(str(TARGET), quantization='float16', force=False)
    source_paths = {
        'test_manifest': 'data/manifests/test_cs_benchmark_20261112.json',
        'validation_manifest': 'data/manifests/validation_forced_ne_20261124.json',
        'automatic_local': 'results/predictions/test_cs_benchmark_20261112_local.json',
        'automatic_api': 'results/predictions/test_cs_benchmark_20261112_whisper_api.json',
        'forced_local': 'results/predictions/test_cs_forced_ne_20261124_local.json',
        'forced_api': 'results/predictions/test_cs_forced_ne_20261124_whisper_api.json',
        'reference_audit': 'data/annotations/reference_audit_20261112_frozen.json',
    }
    original = json.loads((ROOT / source_paths['test_manifest']).read_bytes())
    config = {
        'prepared_at_utc': datetime.now(timezone.utc).isoformat(),
        'purpose': 'Separate exploratory code-mix-specialist comparison; training overlap unresolved.',
        'system': 'codemix_turbo', 'model_id': MODEL_ID, 'model_revision': REVISION,
        'source_weights_sha256': WEIGHTS_SHA256, 'source_weights_format': 'BF16 safetensors',
        'converted_directory': TARGET.relative_to(ROOT).as_posix(), 'conversion_quantization': 'float16',
        'converted_files_sha256': {p.name: checksum(p) for p in TARGET.iterdir() if p.is_file()},
        'source_files_sha256': {p.name: checksum(p) for p in SOURCE.iterdir() if p.is_file()},
        'conversion_packages': {p: version(p) for p in ['torch', 'transformers', 'ctranslate2', 'numpy', 'huggingface-hub']},
        'runtime_packages': original['frozen_packages']['local'],
        'device': 'cuda', 'compute_type': 'float16', 'batch_size': 1,
        'transcribe': {'task': 'transcribe', 'language': 'ne', 'beam_size': 1, 'best_of': 1,
                       'temperature': 0.0, 'condition_on_previous_text': False,
                       'vad_filter': False, 'word_timestamps': False, 'without_timestamps': True},
        'sources': {k: {'path': p, 'sha256': checksum(ROOT / p)} for k, p in source_paths.items()},
        'training_evaluation_overlap': 'unknown; no independent held-out generalization claim',
        'comparison_limit': 'Different base model and training history from Large V2/whisper-1; not an isolated fine-tuning or hosting effect.',
        'primary_scoring': 'Reuse existing normalization, references and CMI; no reference edits or outcome-based exclusions.',
        'bootstrap': {'replicates': 2000, 'seed': 42, 'percentiles': [2.5, 97.5], 'minimum_videos_for_interval': 10},
        'published_research_update_authorized': False,
    }
    CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Verified source checksum; converted FP16 model and frozen exploratory configuration saved.')


if __name__ == '__main__':
    main()
