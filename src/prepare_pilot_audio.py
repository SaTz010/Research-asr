"""Recover only the original five validation clips; never use test audio."""
import hashlib
import json
from pathlib import Path
import zipfile

from asr_common import COLUMNS, prepare_clip
from check_local_environment import ROOT, verify_saved_baseline


def load_baseline():
    receipt = verify_saved_baseline()
    with zipfile.ZipFile(ROOT / 'results/predictions' / receipt['archive']) as archive:
        return json.loads(archive.read('results.json'))


def verify_payload(row, content, expected_payload, split):
    if hashlib.sha256(content).hexdigest() != expected_payload:
        raise ValueError('Original submitted WAV bytes differ; do not compare different audio.')
    clip = prepare_clip({**row, 'audio': {'bytes': content}}, split)
    if clip['identity'] != row:
        raise ValueError('Audio hash or metadata differs from the saved manifest.')
    return clip


def recover_audio(baseline, cache=None):
    cache = cache or ROOT / '.cache/pilot_audio'
    cache.mkdir(parents=True, exist_ok=True)
    dataset, manifest = baseline['dataset'], baseline['manifest']
    if dataset['split'] != 'validation' or len(manifest) != 5:
        raise ValueError('This pilot accepts exactly the five original validation clips.')
    payloads = baseline['run_spec']['payload_sha256']
    marker = cache / 'verified.json'
    specification = {'dataset': dataset, 'manifest': manifest, 'payload_sha256': payloads}
    if marker.exists():
        if json.loads(marker.read_text(encoding='utf-8')) != specification:
            raise ValueError('Cached audio selection/settings differ; preserve rather than overwrite.')
    else:
        from datasets import load_dataset
        expected = {row['clip_id']: row for row in manifest}
        found = set()
        stream = load_dataset(dataset['id'], name=dataset['config'], split=dataset['split'],
                              revision=dataset['revision'], streaming=True, token=False,
                              cache_dir=str(ROOT / '.cache/datasets'))
        stream = stream.decode(False).select_columns(COLUMNS)
        print('Scanning pinned validation audio; checking all five identities and duplicates.', flush=True)
        for row in stream:
            key = f"{dataset['split']}/{row['video_id']}/{row['start_ms']}-{row['end_ms']}"
            if key not in expected:
                continue
            if key in found:
                raise ValueError(f'Ambiguous duplicate provenance: {key}.')
            clip = prepare_clip(row, dataset['split'])
            if clip['identity'] != expected[key]:
                raise ValueError(f'Audio/metadata differs for {key}.')
            content = row['audio']['bytes']
            verify_payload(expected[key], content, payloads[key], dataset['split'])
            (cache / (payloads[key] + '.wav')).write_bytes(content)
            found.add(key)
            print('Verified:', key, flush=True)
        if found != set(expected):
            raise ValueError(f'Missing original clips: {sorted(set(expected) - found)}.')
        # Mark complete only after the entire scan has ruled out duplicate identities.
        marker.write_text(json.dumps(specification, ensure_ascii=False, indent=2), encoding='utf-8')
    return [verify_payload(row, (cache / (payloads[row['clip_id']] + '.wav')).read_bytes(),
                           payloads[row['clip_id']], dataset['split']) for row in manifest]


if __name__ == '__main__':
    clips = recover_audio(load_baseline())
    print('READY:', len(clips), 'clips;', sum(row['identity']['decoded_duration_s'] for row in clips), 'seconds')
