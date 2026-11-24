"""Recompute pilot edit counts without jiwer, inference, downloads or API calls."""
import hashlib
import json
import math
from pathlib import Path
import zipfile

from asr_common import normalize_text
from check_local_environment import ROOT, verify_saved_baseline
from prepare_pilot_audio import verify_payload


def distance(reference, hypothesis):
    previous = list(range(len(hypothesis) + 1))
    for i, a in enumerate(reference, 1):
        current = [i]
        for j, b in enumerate(hypothesis, 1):
            current.append(min(previous[j] + 1, current[-1] + 1, previous[j - 1] + (a != b)))
        previous = current
    return previous[-1]


def main():
    assert distance('kitten', 'sitting') == 3
    assert distance([], []) == 0 and distance(['a'], []) == 1
    source = ROOT / 'results/predictions/local_whisper_large_v2_pilot.json'
    data = json.loads(source.read_text(encoding='utf-8'))
    metrics = json.loads((ROOT / 'results/metrics/local_whisper_large_v2_pilot.json').read_text(encoding='utf-8'))
    receipt = verify_saved_baseline()
    with zipfile.ZipFile(ROOT / 'results/predictions' / receipt['archive']) as archive:
        baseline = json.loads(archive.read('results.json'))
    assert data['run_spec']['saved_api_baseline'] == receipt
    for key in ['dataset', 'manifest', 'payload_sha256']:
        expected = baseline['run_spec']['payload_sha256'] if key == 'payload_sha256' else baseline[key]
        assert data['run_spec'][key] == expected
    config = json.loads((ROOT / 'configs/local_whisper_pilot.json').read_text(encoding='utf-8'))
    assert data['run_spec']['config'] == config
    assert data['model_files_sha256']['model.bin'] == config['model_sha256']
    assert data['actual_device'] == 'cuda' and data['actual_compute_type'] == 'float16'
    assert data['paid_api_calls'] == 0 and data['model_load_s'] > 0
    manifest = {row['clip_id']: row for row in baseline['manifest']}
    assert len(data['predictions']) == len({row['clip_id'] for row in data['predictions']}) == len(manifest) == 5
    old = {row['clip_id']: row for row in baseline['predictions'] if row['mode'] == 'auto'}
    reported = {row['clip_id']: row for row in metrics['per_clip']}
    totals = {name: {'word_errors': 0, 'character_errors': 0, 'reference_words': 0, 'reference_characters': 0}
              for name in ['local', 'api']}
    per_clip = []
    for row in data['predictions']:
        key = row['clip_id']
        assert row['status'] == 'received'
        assert all(row[field] == value for field, value in manifest[key].items())
        payload = data['run_spec']['payload_sha256'][key]
        # These five WAVs are already cached; this check never fetches missing files.
        verify_payload(manifest[key], (ROOT / '.cache/pilot_audio' / (payload + '.wav')).read_bytes(), payload, 'validation')
        assert row['hypothesis'] == ' '.join(part['text'].strip() for part in row['response']['segments']).strip()
        assert math.isfinite(row['transcription_s']) and row['transcription_s'] > 0
        assert row['response']['info']['duration'] == row['decoded_duration_s']
        options = row['response']['info']['transcription_options']
        assert options['beam_size'] == config['transcribe']['beam_size']
        assert options['temperatures'] == [0.0] and not options['condition_on_previous_text']
        assert options['initial_prompt'] is None and options['prefix'] is None and options['hotwords'] is None
        scores = {}
        for name, hypothesis in [('local', row['hypothesis']), ('api', old[key]['hypothesis'])]:
            ref, hyp = normalize_text(row['transcription']), normalize_text(hypothesis)
            words, chars = len(ref.split()), len(ref.replace(' ', ''))
            edits = distance(ref.split(), hyp.split()), distance(ref.replace(' ', ''), hyp.replace(' ', ''))
            scores[name] = {'wer': edits[0] / words, 'cer': edits[1] / chars}
            for field, value in dict(word_errors=edits[0], character_errors=edits[1], reference_words=words,
                                     reference_characters=chars).items():
                totals[name][field] += value
            assert math.isclose(reported[key][name + '_wer'], scores[name]['wer'], abs_tol=1e-12)
            assert math.isclose(reported[key][name + '_cer'], scores[name]['cer'], abs_tol=1e-12)
        per_clip.append({'clip_id': key, 'cmi': row['cmi'], 'local': scores['local'], 'api': scores['api'],
                         'local_reported_language': row['response']['info']['language']})
    for name, counts in totals.items():
        counts.update(wer=counts['word_errors'] / counts['reference_words'],
                      cer=counts['character_errors'] / counts['reference_characters'])
        assert math.isclose(metrics['summary'][name + '_wer'], counts['wer'], abs_tol=1e-12)
        assert math.isclose(metrics['summary'][name + '_cer'], counts['cer'], abs_tol=1e-12)
    assert metrics['summary']['complete']
    gpu_used = [data['gpu_after_load']['used_memory_mib']] + [row['gpu_after_transcription']['used_memory_mib'] for row in data['predictions']]
    report = {
        'source': str(source.relative_to(ROOT)), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'checks': 'All five local/API word and character edit counts independently recomputed without jiwer. Saved baseline checksum, exact five cached WAV payloads and waveform hashes, references, revisions/settings and materialized raw responses agree.',
        'coverage': {'expected': 5, 'received': 5, 'complete': True}, 'scores': totals, 'per_clip': per_clip,
        'model_load_s': data['model_load_s'], 'local_transcription_s': metrics['summary']['transcription_s'],
        'audio_s': metrics['summary']['audio_s'],
        'request_time_per_audio_time': metrics['summary']['transcription_s'] / metrics['summary']['audio_s'],
        'gpu': data['runtime']['gpu_before_load'], 'largest_observed_device_memory_mib': max(gpu_used),
        'memory_limit': 'Whole-device snapshots at model load/clip completion, not continuous peak or isolated model allocation.',
        'new_paid_api_calls': 0, 'api_baseline': receipt,
        'scope': 'Five validation clips. This process observed real local GPU execution and independently checked cached inputs/scores. Historical API execution and current invoices were not observed.',
        'interpretation': 'For these five clips/configurations, hosted Whisper has lower corpus WER/CER. Different implementations and unavailable API internals prevent attributing the difference solely to hosting. No CMI association or population-wide model ranking is established.'
    }
    destination = ROOT / 'results/metrics/local_whisper_large_v2_pilot_verified.json'
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in ['coverage', 'scores', 'model_load_s', 'local_transcription_s',
                                               'audio_s', 'largest_observed_device_memory_mib', 'new_paid_api_calls']}, indent=2))


if __name__ == '__main__':
    main()
