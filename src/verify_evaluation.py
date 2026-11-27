"""Independently verify a completed manifest-based run; no inference/network calls."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

from asr_common import normalize_text
from check_local_environment import ROOT
from run_evaluation import read_manifest, verify_followup
from verify_local_pilot import distance


def verify(manifest_path, predictions_path, metrics_path):
    manifest, clips = read_manifest(manifest_path)
    data = json.loads(predictions_path.read_text(encoding='utf-8'))
    metrics = json.loads(metrics_path.read_text(encoding='utf-8'))
    spec = data['run_spec']
    condition = spec.get('condition', 'auto')
    if condition != manifest.get('condition', 'auto'):
        raise ValueError('Saved condition differs from the manifest.')
    if condition == 'forced_ne':
        verify_followup(manifest)
        if (spec['config'] != manifest['frozen_system_configs'][spec['system']]
                or spec['packages'] != manifest['frozen_packages'][spec['system']]
                or spec.get('protocol_config_sha256') != manifest['protocol_config_sha256']):
            raise ValueError('Forced-Nepali saved settings/packages/protocol differ.')
    assert spec == metrics['run_spec']
    assert spec['manifest_sha256'] == hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    assert spec['dataset'] == manifest['dataset']
    expected = {entry['identity']['clip_id']: entry for entry in manifest['clips']}
    predictions = {row['clip_id']: row for row in data['predictions']}
    scored = {row['clip_id']: row for row in metrics['per_clip']}
    assert set(predictions) == set(scored) == set(expected)
    assert len(predictions) == len(data['predictions']) == len(scored) == len(metrics['per_clip'])
    if not metrics['summary']['complete']:
        raise ValueError('This verifier requires complete coverage; partial outputs remain exported without a headline score.')
    totals = {name: 0 for name in ['word_errors', 'character_errors', 'reference_words', 'reference_characters',
                                  'raw_word_errors', 'raw_character_errors', 'raw_reference_words', 'raw_reference_characters']}
    times, languages, observed_memory, missing_memory_snapshots = [], Counter(), [], []
    for key, row in predictions.items():
        assert row['status'] == 'received'
        assert all(row[field] == value for field, value in expected[key]['identity'].items())
        assert spec['payload_sha256'][key] == expected[key]['payload_sha256']
        hypothesis = row['hypothesis']
        if spec['system'] == 'local':
            assert hypothesis == ' '.join(part['text'].strip() for part in row['response']['segments']).strip()
            options = row['response']['info']['transcription_options']
            assert options['initial_prompt'] is None and options['hotwords'] is None and options['prefix'] is None
            assert options['beam_size'] == spec['config']['transcribe']['beam_size']
            assert options['temperatures'] == [0.0] and not options['condition_on_previous_text']
            languages[row['response']['info']['language']] += 1
            if condition == 'forced_ne':
                assert row['response']['info']['language'] == 'ne'
            times.append(row['transcription_s'])
            snapshot = row.get('gpu_after_transcription')
            if isinstance(snapshot, dict) and snapshot.get('used_memory_mib') is not None:
                observed_memory.append(snapshot['used_memory_mib'])
            else:
                missing_memory_snapshots.append(key)
        else:
            assert hypothesis == row['response']['text']
            times.append(row['request_latency_s'])
        ref, hyp = normalize_text(row['transcription']), normalize_text(hypothesis)
        values = {
            'word_errors': distance(ref.split(), hyp.split()),
            'character_errors': distance(ref.replace(' ', ''), hyp.replace(' ', '')),
            'reference_words': len(ref.split()), 'reference_characters': len(ref.replace(' ', '')),
            'raw_word_errors': distance(row['transcription'].split(), hypothesis.split()),
            'raw_character_errors': distance(''.join(row['transcription'].split()), ''.join(hypothesis.split())),
            'raw_reference_words': len(row['transcription'].split()),
            'raw_reference_characters': len(''.join(row['transcription'].split())),
        }
        for field, value in values.items():
            totals[field] += value
        for name, numerator, denominator in [
            ('wer', 'word_errors', 'reference_words'), ('cer', 'character_errors', 'reference_characters'),
            ('raw_wer', 'raw_word_errors', 'raw_reference_words'), ('raw_cer', 'raw_character_errors', 'raw_reference_characters')]:
            assert math.isclose(scored[key][name], values[numerator] / values[denominator], abs_tol=1e-12)
    rates = {name: totals[numerator] / totals[denominator] for name, numerator, denominator in [
        ('wer', 'word_errors', 'reference_words'), ('cer', 'character_errors', 'reference_characters'),
        ('raw_wer', 'raw_word_errors', 'raw_reference_words'), ('raw_cer', 'raw_character_errors', 'raw_reference_characters')]}
    for name, value in rates.items():
        assert math.isclose(metrics['summary'][name], value, abs_tol=1e-12)
    assert all(math.isfinite(value) and value > 0 for value in times)
    report = {
        'predictions': predictions_path.resolve().relative_to(ROOT.resolve()).as_posix(),
        'predictions_sha256': hashlib.sha256(predictions_path.read_bytes()).hexdigest(),
        'manifest_sha256': spec['manifest_sha256'], 'system': spec['system'], 'purpose': manifest['purpose'],
        'coverage': {'expected': len(expected), 'received': len(predictions), 'complete': True},
        'independent_edit_counts': totals, 'independent_scores': rates,
        'checks': 'All WAV payloads/waveform hashes and identities rechecked. Raw hypotheses reconstructed from saved responses. Every per-clip and corpus normalized/raw WER/CER independently recomputed without jiwer.',
        'audio_s': sum(clip['identity']['decoded_duration_s'] for clip in clips),
        'completed_request_s': sum(times), 'reported_languages': dict(languages),
        'largest_observed_device_memory_mib': max(observed_memory) if observed_memory else None,
        'missing_gpu_snapshot_clip_ids': missing_memory_snapshots,
        'scope': ('Frozen held-out test evaluation.' if manifest['dataset']['split'] == 'test' else
                  'Validation-only runtime check.') + ' Verification uses saved predictions without inference/API calls. Memory is whole-device snapshots, not continuously measured model peak; missing observations are disclosed, not imputed.'
    }
    if condition == 'forced_ne':
        report['condition'] = condition
        report['comparison_scope'] = 'Reuse published automatic outputs; hosted conditions were run on different dates.'
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--predictions', type=Path, required=True)
    args = parser.parse_args()
    metrics_path = ROOT / 'results/metrics' / args.predictions.name
    report = verify(args.manifest, args.predictions, metrics_path)
    destination = metrics_path.with_name(metrics_path.stem + '_verified.json')
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
