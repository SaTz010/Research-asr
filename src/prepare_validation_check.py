"""Freeze 15 additional validation clips by metadata, then recover their WAVs."""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import random

from asr_common import COLUMNS, prepare_clip
from budget import cmi_band
from check_local_environment import ROOT
from prepare_pilot_audio import load_baseline, verify_payload

SELECTION = ROOT / 'data/manifests/validation_check_20261104_selection.json'
MANIFEST = ROOT / 'data/manifests/validation_check_20261104.json'
BANDS = ['[0,10]', '(10,20]', '(20,30]', '(30,40]', '(40,50]']


def clip_key(row):
    return f"{row['split']}/{row['video_id']}/{row['start_ms']}-{row['end_ms']}"


def select_rows(inventory, excluded, seed=42):
    rows = [row for shard in inventory['shards'] for row in shard['rows'] if row['split'] == 'validation']
    counts = Counter(clip_key(row) for row in rows)
    eligible = [row for row in rows if row['speech_type'] == 'cs' and counts[clip_key(row)] == 1
                and clip_key(row) not in excluded and isinstance(row['video_id'], str) and row['video_id'].strip()
                and isinstance(row['speaker_id'], str) and row['speaker_id'].strip()
                and isinstance(row['start_ms'], int) and not isinstance(row['start_ms'], bool)
                and isinstance(row['end_ms'], int) and not isinstance(row['end_ms'], bool)
                and isinstance(row['duration_s'], (int, float)) and not isinstance(row['duration_s'], bool)
                and 0 <= row['start_ms'] < row['end_ms'] and 0 < row['duration_s'] <= 30
                and math.isfinite(row['duration_s']) and row['reference_words'] > 0
                and cmi_band(row['cmi']) in BANDS]
    rng = random.Random(seed)
    selected = []
    for band in BANDS:
        pool = sorted([row for row in eligible if cmi_band(row['cmi']) == band],
                      key=lambda row: (row['duration_s'], clip_key(row)))
        if len(pool) < 3:
            raise ValueError(f'Need at least three validation examples in {band}.')
        shortest, longest = pool[0], pool[-1]
        selected.extend([dict(shortest, selection_role='shortest_in_band'), dict(longest, selection_role='longest_in_band')])
        remaining = [row for row in pool if clip_key(row) not in {clip_key(shortest), clip_key(longest)}]
        channels = {row['speaker_id'] for row in selected}
        unseen = [row for row in remaining if row['speaker_id'] not in channels]
        selected.append(dict(rng.choice(unseen or remaining), selection_role='seeded_extra_prefer_new_channel'))
    return selected


def main():
    metadata_path = ROOT / 'data/manifests/budget_metadata_20261022.json'
    inventory = json.loads(metadata_path.read_text(encoding='utf-8'))
    baseline = load_baseline()
    excluded = {row['clip_id'] for row in baseline['manifest']}
    selection = {
        'purpose': 'additional validation-only runtime check; not held-out evaluation',
        'dataset': baseline['dataset'], 'seed': 42,
        'metadata_sha256': hashlib.sha256(metadata_path.read_bytes()).hexdigest(),
        'rule': 'Per CMI band: shortest, longest, seeded extra preferring a new channel. Exclude original five and ambiguous identities.',
        'excluded_original_clip_ids': sorted(excluded), 'rows': select_rows(inventory, excluded),
    }
    if SELECTION.exists() and json.loads(SELECTION.read_text(encoding='utf-8')) != selection:
        raise ValueError('Selection differs from saved metadata decision; preserve the earlier selection.')
    SELECTION.write_text(json.dumps(selection, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    selection_sha = hashlib.sha256(SELECTION.read_bytes()).hexdigest()
    if MANIFEST.exists():
        saved = json.loads(MANIFEST.read_text(encoding='utf-8'))
        if saved['selection_sha256'] != selection_sha:
            raise ValueError('Saved audio manifest comes from a different selection.')
        if len(saved['clips']) != 15 or {row['identity']['clip_id'] for row in saved['clips']} != {clip_key(row) for row in selection['rows']}:
            raise ValueError('Saved audio manifest does not contain the frozen 15-clip selection.')
        for row in saved['clips']:
            verify_payload(row['identity'], (ROOT / row['audio_path']).read_bytes(), row['payload_sha256'], 'validation')
        print('Reused verified 15-clip audio manifest:', MANIFEST)
        return
    from datasets import load_dataset
    dataset = selection['dataset']
    stream = load_dataset(dataset['id'], name=dataset['config'], split='validation', revision=dataset['revision'],
                          streaming=True, token=False, cache_dir=str(ROOT / '.cache/datasets'))
    stream = stream.decode(False).select_columns(COLUMNS)
    expected = {clip_key(row): row for row in selection['rows']}
    found = {}
    cache = ROOT / '.cache/validation_check_20261104'
    cache.mkdir(parents=True, exist_ok=True)
    print('Recovering frozen 15-clip validation selection...', flush=True)
    for row in stream:
        key = f"validation/{row['video_id']}/{row['start_ms']}-{row['end_ms']}"
        if key not in expected:
            continue
        if key in found:
            raise ValueError(f'Duplicate selected source identity: {key}.')
        meta = expected[key]
        for name in ['speech_type', 'duration_s', 'cmi', 'video_id', 'start_ms', 'end_ms', 'speaker_id']:
            if row[name] != meta[name]:
                raise ValueError(f'Pinned metadata differs for {key}: {name}.')
        if hashlib.sha256(row['transcription'].encode('utf-8')).hexdigest() != meta['reference_sha256']:
            raise ValueError(f'Reference text differs from the metadata snapshot: {key}.')
        clip = prepare_clip(row, 'validation')
        content = row['audio']['bytes']
        payload = hashlib.sha256(content).hexdigest()
        audio_path = cache / (payload + '.wav')
        audio_path.write_bytes(content)
        found[key] = {'identity': clip['identity'], 'payload_sha256': payload,
                      'audio_path': audio_path.relative_to(ROOT).as_posix(),
                      'source_file': meta['source_file'], 'row_in_file': meta['row_in_file'],
                      'selection_role': meta['selection_role']}
        print('Verified:', key, flush=True)
    if set(found) != set(expected):
        raise ValueError(f'Missing selected clips: {sorted(set(expected) - set(found))}.')
    manifest = {'purpose': 'validation_runtime', 'dataset': dataset, 'selection_sha256': selection_sha,
                'clips': [found[clip_key(row)] for row in selection['rows']]}
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Saved verified 15-clip manifest:', MANIFEST)


if __name__ == '__main__':
    main()
