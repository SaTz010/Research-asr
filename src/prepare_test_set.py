"""Audit the pinned CS test pool and prepare inputs, without loading an ASR model."""
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import random

from asr_common import prepare_clip
from budget import cmi_band, estimate_budget
from check_local_environment import ROOT
from local_whisper_pilot import save_state
from prepare_validation_check import BANDS, clip_key

INVENTORY = ROOT / 'data/manifests/budget_metadata_20261022.json'
INVENTORY_SHA = '2ed67804fb11e2920795569288975b79f6adc9178ac53ac57c7ff8ad041d6eb2'
MANIFEST = ROOT / 'data/manifests/test_cs_20261105.json'
AUDIT = ROOT / 'results/metrics/test_eligibility_20261105.json'
SELECTION = ROOT / 'data/manifests/reference_audit_20261105_selection.json'
ANNOTATIONS = ROOT / 'data/annotations/reference_audit_20261105.json'


def provenance(row):
    video, start, end = (row.get(name) for name in ['video_id', 'start_ms', 'end_ms'])
    if (not isinstance(video, str) or not video.strip()
            or any(not isinstance(v, int) or isinstance(v, bool) for v in [start, end])
            or not 0 <= start < end):
        return None
    return video, start, end


def metadata_audit(rows):
    """Exclude ambiguous identities/intervals; report text/channel overlap separately."""
    test = [r for r in rows if r['split'] == 'test']
    candidates = [r for r in test if r['speech_type'] == 'cs']
    keys = Counter(provenance(r) for r in test if provenance(r))
    others = [r for r in rows if r['split'] != 'test']
    other_intervals, test_intervals = defaultdict(list), defaultdict(list)
    for r in others:
        if provenance(r):
            other_intervals[r['video_id']].append(r)
    for r in test:
        if provenance(r):
            test_intervals[r['video_id']].append(r)
    other_refs = {r['reference_sha256'] for r in others}
    other_channels = {r['speaker_id'] for r in others}
    eligible, excluded, flags = [], [], []
    for row in candidates:
        reasons = []
        key = provenance(row)
        if key is None:
            reasons.append('missing_or_invalid_provenance')
        else:
            if keys[key] != 1:
                reasons.append('duplicate_test_identity')
            for label, pool in [('cross_split_interval_overlap', other_intervals), ('within_test_interval_overlap', test_intervals)]:
                hits = [r for r in pool.get(row['video_id'], []) if r is not row
                        and max(row['start_ms'], r['start_ms']) < min(row['end_ms'], r['end_ms'])]
                if hits:
                    reasons.append(label)
        duration, cmi = row.get('duration_s'), row.get('cmi')
        if (isinstance(duration, bool) or not isinstance(duration, (int, float))
                or not math.isfinite(duration) or not 0 < duration <= 30
                or (key and abs(duration - (key[2] - key[1]) / 1000) > .02)):
            reasons.append('invalid_duration')
        if (isinstance(cmi, bool) or not isinstance(cmi, (int, float))
                or not math.isfinite(cmi) or not 0 <= cmi <= 50):
            reasons.append('invalid_cmi')
        if not isinstance(row.get('speaker_id'), str) or not row['speaker_id'].strip():
            reasons.append('missing_channel')
        if not isinstance(row.get('reference_words'), int) or row['reference_words'] < 1:
            reasons.append('empty_reference')
        if reasons:
            excluded.append({'source_file': row['source_file'], 'row_in_file': row['row_in_file'],
                             'provenance': list(key) if key else None, 'reasons': reasons})
        else:
            eligible.append(row)
            warnings = []
            if row['video_id'] in other_intervals:
                warnings.append('shared_video_without_interval_overlap')
            if row['speaker_id'] in other_channels:
                warnings.append('shared_source_channel')
            if row['reference_sha256'] in other_refs:
                warnings.append('identical_reference_in_other_split_not_proof_of_audio_duplicate')
            if warnings:
                flags.append({'clip_id': clip_key(row), 'flags': warnings})
    return eligible, excluded, flags


def exclude_audio_duplicates(entries):
    groups = defaultdict(list)
    for entry in entries:
        groups[entry['identity']['audio_sha256']].append(entry)
    retained, excluded = [], []
    for entry in entries:
        group = groups[entry['identity']['audio_sha256']]
        if len(group) > 1:
            excluded.append({'clip_id': entry['identity']['clip_id'], 'reasons': ['duplicate_decoded_cs_test_audio'],
                             'matching_clip_ids': sorted(e['identity']['clip_id'] for e in group)})
        else:
            retained.append(entry)
    return retained, excluded


def select_audit(entries, per_band=10, seed=42):
    """Seeded ties; greedily balance channels then videos within each fixed band."""
    rng = random.Random(seed)
    selected = []
    for band in BANDS:
        pool = sorted([e for e in entries if cmi_band(e['identity']['cmi']) == band],
                      key=lambda e: e['identity']['clip_id'])
        if len(pool) < per_band:
            raise ValueError(f'Not enough eligible audit clips in {band}.')
        rng.shuffle(pool)
        channels, videos = Counter(), Counter()
        for _ in range(per_band):
            choice = min(pool, key=lambda e: (channels[e['identity']['speaker_id']], videos[e['identity']['video_id']]))
            pool.remove(choice)
            selected.append(choice)
            channels[choice['identity']['speaker_id']] += 1
            videos[choice['identity']['video_id']] += 1
    # Interleave bands, so each 25-clip session reviews five examples per band.
    return [selected[b * per_band + i] for i in range(per_band) for b in range(len(BANDS))]


def frozen_write(path, value):
    if path.exists():
        if json.loads(path.read_text(encoding='utf-8')) != value:
            raise ValueError(f'Frozen artifact differs; preserve it and investigate: {path.name}.')
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        save_state(path, value)


def digest(path):
    checksum = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def build_review_notebook(selection, assisted=False):
    cells = []

    def cell(kind, source):
        value = {'id': f'review-{len(cells):03d}', 'cell_type': kind, 'metadata': {}, 'source': source.splitlines(keepends=True)}
        if kind == 'code':
            value.update(execution_count=None, outputs=[])
        cells.append(value)

    if assisted:
        cell('markdown', '# Assisted reference and CMI review — 50 clips\n\n'
             'Listen and correct the reference, generate script-based tag suggestions, then check and save. '
             'Suggestions are not verified language labels. No ASR predictions or API calls are used. '
             'Read `reports/reference_annotation_guide.md`. Items 1–25: November 11; 26–50: November 12. '
             'Existing reviews use the same annotation file; no review is saved automatically.\n')
    else:
        cell('markdown', '# Test reference review — 50 clips\n\nRun locally in VS Code with the project interpreter. '
         'No ASR predictions are loaded. Read `reports/reference_annotation_guide.md` first. '
         'Items 1–25 are for November 6; 26–50 for November 13. '
         'Keep all answers pending until you listen; copying a reference is not a review.\n')
    cell('markdown', '## 1. Setup and saved progress\n')
    cell('code', "from pathlib import Path\nimport json, sys\nfrom IPython.display import Audio, display\n"
         "ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / 'src/reference_audit.py').is_file())\n"
         "sys.path.insert(0, str(ROOT / 'src'))\nfrom reference_audit import save_review\n"
         "selection = json.loads((ROOT / 'data/manifests/reference_audit_20261105_selection.json').read_text(encoding='utf-8'))\n"
         "progress_path = ROOT / 'data/annotations/reference_audit_20261105.json'\n"
         "progress = json.loads(progress_path.read_text(encoding='utf-8'))\n"
         "print('Reviewed:', sum(r['verdict'] != 'pending' for r in progress['reviews']), '/ 50')\n")
    if assisted:
        cells[-1]['source'] += ["from reference_audit import suggest_language_tags\n",
                               "from asr_common import normalize_text\n", "drafts = {}\n"]
    for number, entry in enumerate(selection['clips'], 1):
        if number in {1, 26}:
            day = (11 if number == 1 else 12) if assisted else (6 if number == 1 else 13)
            cell('markdown', f'## {2 if number == 1 else 3}. November {day}: items {number}–{number+24}\n')
        cell('markdown', f'### Review {number:02d} — audio, published reference and language tags\n'
             + ('1. Play the audio. 2. Correct the quoted text in the draft cell and run it. '
                '3. Check every suggested word/tag, add word-number overrides, set `tags_reviewed = True` '
                'and a verdict, then run the save cell. If you change the transcript, rerun the draft and recheck overrides.\n'
                if assisted else 'Listen, edit the answer cell, then run it to save. Use one language tag per normalized corrected word.\n'))
        cell('code', f"entry = selection['clips'][{number - 1}]\n"
             "identity = entry['identity']\nprint(identity['clip_id'])\n"
             "print('Published reference:', identity['transcription'])\n"
             "print('Published CMI:', identity['cmi'], '| channel:', identity['speaker_id'])\n"
             "display(Audio(filename=str(ROOT / entry['audio_path'])))\n"
             f"print('Saved review:', json.loads(progress_path.read_text(encoding='utf-8'))['reviews'][{number-1}])\n")
        if assisted:
            reference_literal = json.dumps(entry['identity']['transcription'], ensure_ascii=False)
            cell('code', '# Edit the quoted text after listening. Keep quotes around the entire transcript.\n'
                 f'corrected_reference = {reference_literal}\n'
                 f'drafts[{number}] = (corrected_reference, suggest_language_tags(corrected_reference))\n'
                 f'for word_number, (word, tag) in enumerate(zip(normalize_text(corrected_reference).split(), drafts[{number}][1]), 1):\n'
                 "    print(f'{word_number:2d}  {word}  -> {tag}')\n"
                 '# Check Latin-script Nepali, transliterated English, names and mixed words carefully.\n')
            cell('code', f'reference, suggested = drafts[{number}]\n'
                 'token_languages = list(suggested)\n'
                 "tag_overrides = {}  # Only wrong tags: e.g. {19: 'en'} changes word 19 to English.\n"
                 'for word_number, tag in tag_overrides.items():\n'
                 '    if isinstance(word_number, bool) or not isinstance(word_number, int) or not 1 <= word_number <= len(token_languages):\n'
                 "        raise ValueError('Override word numbers must be in the displayed 1-based range.')\n"
                 '    token_languages[word_number - 1] = tag\n'
                 'tags_reviewed = False  # Change to True only after checking every word/tag.\n'
                 "verdict = 'pending'  # match if unchanged, corrected if edited, unsure if unresolved.\n"
                 "notes = ''\n"
                 "if verdict != 'pending':\n"
                 '    if tags_reviewed is not True:\n'
                 "        raise ValueError('Check all tag suggestions and set tags_reviewed = True before saving.')\n"
                 f"    print(save_review(progress_path, {number}, reference, token_languages, verdict, notes, tagging_method='script_suggestions_human_checked'))\n")
            continue
        cell('code', "corrected_reference = None  # Copy unchanged only after listening, or correct what you hear.\n"
             "token_languages = []  # Example: ['ne', 'en', 'ne']; see the guide for 'other' and 'ambiguous'.\n"
             "verdict = 'pending'  # Replace with match, corrected, or unsure.\nnotes = ''\n"
             "if verdict != 'pending':\n"
             f"    print(save_review(progress_path, {number}, corrected_reference, token_languages, verdict, notes))\n")
    return {'cells': cells, 'metadata': {'kernelspec': {'display_name': 'Python 3 (.venv)', 'language': 'python', 'name': 'python3'},
                                       'language_info': {'name': 'python'}}, 'nbformat': 4, 'nbformat_minor': 5}


def main():
    if digest(INVENTORY) != INVENTORY_SHA:
        raise ValueError('Metadata inventory checksum changed.')
    inventory = json.loads(INVENTORY.read_text(encoding='utf-8'))
    rows = [r for shard in inventory['shards'] for r in shard['rows']]
    eligible, exclusions, flags = metadata_audit(rows)
    expected = {(r['source_file'], r['row_in_file']): r for r in eligible}
    dataset = {'id': inventory['dataset_id'], 'revision': inventory['revision'], 'config': inventory['config'], 'split': 'test'}
    from huggingface_hub import hf_hub_download
    import pyarrow.parquet as pq
    from asr_common import COLUMNS

    entries, audio_exclusions = [], []
    sources = []
    cache = ROOT / '.cache/test_cs_20261105'
    cache.mkdir(parents=True, exist_ok=True)
    for shard in inventory['shards']:
        if shard['split'] != 'test':
            continue
        print('Checking pinned source shard:', shard['path'], flush=True)
        path = Path(hf_hub_download(repo_id=dataset['id'], repo_type='dataset', filename=shard['path'],
                                   revision=dataset['revision'], token=False, cache_dir=str(ROOT / '.cache/test_sources')))
        if path.stat().st_size != shard['source_size'] or digest(path) != shard['source_lfs_sha256']:
            raise ValueError('Pinned Parquet source checksum mismatch.')
        parquet = pq.ParquetFile(path)
        if parquet.metadata.num_rows != len(shard['rows']):
            raise ValueError('Parquet row count differs from the pinned inventory.')
        sources.append({'path': shard['path'], 'sha256': shard['source_lfs_sha256'], 'rows': parquet.metadata.num_rows})
        offset = 0
        # Project away large embedded video payloads; only audio and reference metadata are read.
        for batch in parquet.iter_batches(batch_size=32, columns=COLUMNS):
            for index, row in enumerate(batch.to_pylist(), offset):
                meta = expected.get((shard['path'], index))
                if meta is None:
                    continue
                for field in ['speech_type', 'duration_s', 'cmi', 'video_id', 'start_ms', 'end_ms', 'speaker_id']:
                    if row[field] != meta[field]:
                        raise ValueError(f'Pinned metadata differs: {shard["path"]}:{index} {field}.')
                if (hashlib.sha256(row['transcription'].encode('utf-8')).hexdigest() != meta['reference_sha256']
                        or len(row['transcription'].split()) != meta['reference_words']):
                    raise ValueError('Published reference differs from the pinned inventory.')
                try:
                    clip = prepare_clip(row, 'test')
                except (ValueError, RuntimeError) as error:
                    audio_exclusions.append({'clip_id': clip_key(meta), 'reasons': ['invalid_audio_or_reference'], 'detail': str(error)})
                    continue
                content = row['audio']['bytes']
                payload = hashlib.sha256(content).hexdigest()
                audio_path = cache / (payload + '.wav')
                if not audio_path.exists():
                    audio_path.write_bytes(content)
                elif digest(audio_path) != payload:
                    raise ValueError('Cached WAV checksum mismatch; do not overwrite evidence.')
                entries.append({'identity': clip['identity'], 'payload_sha256': payload,
                                'audio_path': audio_path.relative_to(ROOT).as_posix(),
                                'source_file': shard['path'], 'row_in_file': index})
            offset += batch.num_rows
        print('Verified eligible audio so far:', len(entries), flush=True)
    if len(entries) + len(audio_exclusions) != len(expected):
        raise ValueError('Not every metadata-eligible clip was checked.')
    entries, duplicates = exclude_audio_duplicates(entries)
    entries.sort(key=lambda e: e['identity']['clip_id'])
    manifest = {'purpose': 'held_out_cs_benchmark', 'dataset': dataset, 'metadata_sha256': INVENTORY_SHA,
                'pool_frozen_on': '2026-11-05', 'frozen_for_inference': False,
                'inference_block_reason': 'Complete and freeze 50 human reference/CMI reviews and the final protocol first.',
                'clips': entries}
    frozen_write(MANIFEST, manifest)
    manifest_sha = digest(MANIFEST)
    selected = select_audit(entries)
    selection = {'dataset': dataset, 'evaluation_manifest_sha256': manifest_sha, 'seed': 42,
                 'selection_rule': '10 per fixed published CMI band; seeded ties, balance channels then videos within each band; interleave bands.',
                 'selection_is_representative_of_full_test_distribution': False, 'clips': selected}
    frozen_write(SELECTION, selection)
    if ANNOTATIONS.exists():
        annotations = json.loads(ANNOTATIONS.read_text(encoding='utf-8'))
        if annotations['selection_sha256'] != digest(SELECTION):
            raise ValueError('Existing human annotations belong to a different selection.')
    else:
        ANNOTATIONS.parent.mkdir(parents=True, exist_ok=True)
        save_state(ANNOTATIONS, {'selection_sha256': digest(SELECTION), 'reviewer': None, 'frozen': False,
                   'reviews': [{'number': i, 'clip_id': e['identity']['clip_id'], 'verdict': 'pending',
                                'corrected_reference': None, 'token_languages': [], 'notes': ''}
                               for i, e in enumerate(selected, 1)]})
    frozen_write(ROOT / 'notebooks/05_reference_cmi_audit.ipynb', build_review_notebook(selection))
    frozen_write(ROOT / 'notebooks/06_reference_cmi_audit_assisted.ipynb', build_review_notebook(selection, assisted=True))
    budget = estimate_budget([e['identity']['duration_s'] for e in entries], {'whisper-1': '.006'})
    report = {'dataset': dataset, 'metadata_sha256': INVENTORY_SHA, 'manifest_sha256': manifest_sha,
              'candidate_cs_clips': sum(r['speech_type'] == 'cs' and r['split'] == 'test' for r in rows),
              'metadata_eligible_clips': len(eligible), 'audio_checked_clips': len(eligible), 'included_clips': len(entries),
              'exclusions': exclusions + audio_exclusions + duplicates, 'metadata_overlap_flags': flags,
              'source_shards_verified': sources,
              'included_cmi_bands': dict(Counter(cmi_band(e['identity']['cmi']) for e in entries)),
              'included_channels': dict(Counter(e['identity']['speaker_id'] for e in entries)),
              'included_videos': len({e['identity']['video_id'] for e in entries}),
              'audit_cmi_bands': dict(Counter(cmi_band(e['identity']['cmi']) for e in selected)),
              'audit_channels': dict(Counter(e['identity']['speaker_id'] for e in selected)),
              'audit_videos': len({e['identity']['video_id'] for e in selected}),
              'budget_at_historical_20261022_rate_not_current_price_verification': budget,
              'limitations': ['Audio duplicates checked among metadata-eligible CS test clips using exact decoded waveform hashes, not perceptual similarity.',
                             'Cross-split overlap checked by source video, intervals, channel and exact reference text; full other-split waveform hashes not scanned.',
                             'No access to provider model-training data; no claim of freedom from pretraining contamination.',
                             'Two source channels are not verified speaker identities; 50-clip audit requires human listening and is still pending.'],
              'asr_inference_performed': False, 'paid_api_requests': 0}
    frozen_write(AUDIT, report)
    print(json.dumps({k: report[k] for k in ['candidate_cs_clips', 'included_clips', 'included_cmi_bands', 'audit_videos']}, indent=2))


if __name__ == '__main__':
    main()
