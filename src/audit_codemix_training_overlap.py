"""Audit available split evidence; missing training membership stays unknown."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math

from asr_common import normalize_text
from check_local_environment import ROOT
from local_whisper_pilot import save_state
from prepare_codemix_model import CONFIG, checksum

CACHE = ROOT / '.cache/codemix_overlap_20261127'


def match_public_test(entries, public_rows, tolerance_s=.001001):
    ids = [e['identity']['clip_id'] for e in entries]
    public_ids = [r['id'] for r in public_rows]
    if len(set(ids)) != len(ids) or len(set(public_ids)) != len(public_ids):
        raise ValueError('Duplicate clip identifiers prevent a unique evidence match.')
    by_text = defaultdict(list)
    for row in public_rows:
        d = row['duration_s']
        if isinstance(d, bool) or not isinstance(d, (float, int)) or not math.isfinite(d) or d <= 0:
            raise ValueError('Invalid public duration.')
        by_text[normalize_text(row['reference'])].append(row)
    records = []
    for entry in entries:
        identity = entry['identity']
        reference = normalize_text(identity['transcription'])
        candidates = [r for r in by_text[reference]
                      if abs(r['duration_s'] - identity['decoded_duration_s']) <= tolerance_s]
        records.append({'clip_id': identity['clip_id'], 'source_file': entry.get('source_file'),
                        'row_in_file': entry.get('row_in_file'),
                        'evidence': ('unique_public_test_candidate' if len(candidates) == 1 else
                                     'ambiguous_public_test_candidates' if candidates else 'no_exact_public_test_candidate'),
                        'public_test_ids': [r['id'] for r in candidates],
                        'normalized_reference_sha256': hashlib.sha256(reference.encode('utf-8')).hexdigest(),
                        'reference_words': len(reference.split()),
                        'original_reference_contains_digits': any(c.isdigit() for c in identity['transcription']),
                        'duration_s': identity['decoded_duration_s'],
                        'duration_differences_s': [r['duration_s'] - identity['decoded_duration_s'] for r in candidates],
                        'training_membership': 'unverified; no training manifest available'})
    return records


def source_split_overlap(manifest, metadata):
    if metadata['revision'] != manifest['dataset']['revision']:
        raise ValueError('Source metadata revision differs from the evaluation dataset.')
    identities = [e['identity'] for e in manifest['clips']]
    keys = {(r['video_id'], r['start_ms'], r['end_ms']) for r in identities}
    videos, channels = {r['video_id'] for r in identities}, {r['speaker_id'] for r in identities}
    result = {}
    for split in ['train', 'validation', 'test']:
        rows = [r for shard in metadata['shards'] if shard['split'] == split for r in shard['rows']]
        result[split] = {'source_rows': len(rows),
                         'exact_clip_key_overlap': sum((r['video_id'], r['start_ms'], r['end_ms']) in keys for r in rows),
                         'shared_video_ids': sorted(videos & {r['video_id'] for r in rows}),
                         'shared_channel_ids': sorted(channels & {r['speaker_id'] for r in rows})}
    return result


def main():
    import pyarrow.parquet as pq

    config = json.loads(CONFIG.read_bytes())
    manifest_path = ROOT / config['sources']['test_manifest']['path']
    if checksum(manifest_path) != config['sources']['test_manifest']['sha256']:
        raise ValueError('Benchmark manifest changed.')
    manifest = json.loads(manifest_path.read_bytes())
    metadata_path = ROOT / 'data/manifests/budget_metadata_20261022.json'
    if checksum(metadata_path) != manifest['metadata_sha256']:
        raise ValueError('Source split metadata changed.')
    split_check = source_split_overlap(manifest, json.loads(metadata_path.read_bytes()))
    rows = pq.read_table(CACHE / 'outputs_test.parquet').to_pylist()
    public_lectures = [r for r in rows if r['domain'] == 'Lectures']
    matches = match_public_test(manifest['clips'], public_lectures)
    tally = dict(Counter(r['evidence'] for r in matches))
    github = json.loads((CACHE / 'github_tree.json').read_bytes())
    model = json.loads((CACHE / 'hf_model_current.json').read_bytes())
    output = json.loads((CACHE / 'hf_outputs_current.json').read_bytes())
    if github.get('truncated'):
        raise ValueError('Repository listing incomplete.')
    result = {
        'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'status': 'not_cleared_for_independent_full_benchmark_inclusion',
        'conclusion': 'No exact training membership decision is possible for all 1198 clips from the inspected public resources. Supporting held-out evidence exists; leakage is neither demonstrated nor ruled out.',
        'evaluated_model_revision': config['model_revision'], 'current_model_revision': model['sha'],
        'model_revision_matches': model['sha'] == config['model_revision'],
        'benchmark_clips': len(manifest['clips']), 'benchmark_manifest_sha256': checksum(manifest_path),
        'source_metadata_sha256': checksum(metadata_path), 'source_dataset_split_check': split_check,
        'authors_github_commit': github['sha'], 'authors_output_dataset_revision': output['sha'],
        'authors_public_test_rows': len(rows), 'authors_public_lecture_test_rows': len(public_lectures),
        'public_test_matching': {'counts': tally, 'method': 'Unique exact project-normalized reference plus duration within 0.001001 seconds. No hypotheses, fuzzy matching or inferred numeric rewriting used.',
                                 'audio_hash_or_original_video_timestamp_identity_verified': False,
                                 'interpretation': 'Supporting candidates in the authors\' test output table, not verified training exclusions. Absence of a candidate is not training membership.'},
        'training_manifest_available_in_inspected_public_resources': False,
        'direct_training_membership_check_performed': False,
        'number_of_our_clips_in_author_training': None,
        'independently_cleared_training_exclusion_count': None,
        'authors_statements': {'paper_url': 'https://arxiv.org/html/2611.13512v1',
                               'section_3_3': 'Existing train/validation/test assignments kept; duplicate audio and duplicate held-out sentences checked, according to the authors.',
                               'section_5_1': 'Whisper fine-tuned on the same training split as the other adapted models.',
                               'limitations': 'Inherited splits not guaranteed speaker-disjoint; not evidence by itself of exact clip leakage.'},
        'missing_for_clearance': ['Exact source dataset revision/configuration and inclusion/filter rules used for this checkpoint',
                                 'Training and validation identities, or a curator-confirmed intersection against our canonical clip list',
                                 'Mapping from sbc_test aliases to source video/time identities; checks for duplicate/overlapping or augmented training recordings'],
        'per_clip_evidence': matches,
        'network_audio_uploads': 0, 'model_inference_requests': 0, 'authors_contacted': False,
        'main_report_modified': False,
        'evidence_files_sha256': {p.relative_to(CACHE).as_posix(): checksum(p) for p in CACHE.rglob('*') if p.is_file()},
    }
    packet = {'purpose': 'Request to verify training/validation exclusion; not an inference manifest. Prepared locally and not sent.',
              'model_id': config['model_id'], 'model_revision': config['model_revision'],
              'dataset': manifest['dataset'], 'benchmark_manifest_sha256': checksum(manifest_path),
              'dataset_attribution': 'Sailesh Dahal, saileshbro/nepali-cs-asr, CC BY-NC 4.0',
              'requested_check': 'For each item, confirm whether audio or overlapping/augmented derivatives appeared in gradient training or validation/checkpoint selection. Include a mapping for any different aliases or revised boundaries.',
              'video_ids': sorted({e['identity']['video_id'] for e in manifest['clips']}),
              'channel_ids': sorted({e['identity']['speaker_id'] for e in manifest['clips']}),
              'evaluation_clips': [{k: e['identity'][k] for k in ['clip_id', 'video_id', 'start_ms', 'end_ms', 'speaker_id', 'decoded_duration_s', 'audio_sha256']}
                                   | {'source_file': e['source_file'], 'row_in_file': e['row_in_file']} for e in manifest['clips']]}
    save_state(ROOT / 'data/manifests/codemix_overlap_request_20261127.json', packet)
    save_state(ROOT / 'results/metrics/codemix_training_overlap_audit_20261127.json', result)
    unique = tally.get('unique_public_test_candidate', 0)
    absent = tally.get('no_exact_public_test_candidate', 0)
    lines = ['# Training overlap audit for the code mix specialist', '',
             '**November 27, 2026 · No change to the published research**', '',
             '**Decision: the complete 1,198-clip result is not yet cleared as an independently held-out evaluation.** '
             'The public evidence supports held-out use for matching records, but the authors\' training identities are unavailable. '
             'This audit does not demonstrate that the model trained on any of our test clips, and it does not certify their exclusion.', '',
             '## What was checked', '',
             'The evaluated checkpoint revision is unchanged on the Hub. The inspection covered its pinned model card/files, '
             'the authors\' [November 10 preprint](https://arxiv.org/html/2611.13512v1), '
             '[official code repository](https://github.com/AI-Lab-Pvt-Ltd/nepali-codemixed-asr), both public commit trees, '
             'the available release and issues, model discussions, experiment notes and '
             '[text-only test-output dataset](https://huggingface.co/datasets/ailabpvtltd/nepali-english-codemix-asr-test-outputs). '
             'No training clip list was found in these resources. The release manifest hashes software files; '
             'the experiment notes give a dataset-manifest hash, not its underlying membership list.', '',
             '## Our source dataset splits are clean for these clip identities', '',
             'The cached source metadata matches the checksum frozen into our benchmark and the exact evaluated dataset revision. '
             'For our 1,198 clips, comparison against the full source splits gives:', '',
             '| Source split | Rows | Exact clip overlap | Shared videos | Shared channels |',
             '|---|---:|---:|---:|---:|']
    for split, s in split_check.items():
        lines.append(f"| {split} | {s['source_rows']} | {s['exact_clip_key_overlap']} | {len(s['shared_video_ids'])} | {len(s['shared_channel_ids'])} |")
    lines += ['', 'This verifies our own dataset selection. It does **not** establish which revision, split or extra collected recordings '
              'the checkpoint actually saw. If the authors used exactly this revision and only its disjoint train split, '
              'the benchmark would be excluded from that source training split. That condition still needs confirmation.', '',
              '## Matching against the authors\' published held-out outputs', '',
              f"Their public table contains {len(rows):,} test rows, including {len(public_lectures):,} lecture rows. "
              f"Across our benchmark, **{unique} clips have one unique exact normalized-reference and duration candidate** "
              f"in that lecture test table; **{absent} have no such exact candidate**. "
              f"There are {tally.get('ambiguous_public_test_candidates',0)} ambiguous candidates under this rule.", '',
              'The matching uses the existing project text normalization and a 0.001001-second duration tolerance. '
              'It uses no ASR hypotheses or fuzzy text similarity. The author IDs are aliases such as `sbc_test_000001`; '
              'the table does not supply source-video timestamps or waveform hashes. Matching text/duration is supporting evidence, '
              'not independent audio identity or proof that training contained no duplicates.', '',
              'Unmatched clips are not labelled as training examples. The authors verbalized numbers and changed transcript conventions, '
              'and preparation may filter clips, so nonmatching reference text can have several explanations. '
              'The audit retains one evidence record for every one of the 1,198 clips.', '',
              '## What the paper adds', '',
              'Sections 3.3 and 5.1 say the inherited split assignments were kept and Whisper used the same training split. '
              'The authors also report cross-split duplicate checks. These are useful disclosures, not an independently reproduced '
              'intersection with our clip IDs. Their speaker-disjointness limitation concerns shared speakers and must not be '
              'misreported as confirmed reuse of the same audio clip. [Paper](https://arxiv.org/html/2611.13512v1).', '',
              '## What would settle the question', '',
              'Request the source revision/configuration, training and validation clip identities, and a mapping for changed aliases '
              'or boundaries. Check duplicate audio, overlapping portions of the same source video and augmented derivatives. '
              'Validation/checkpoint-selection exposure should be checked alongside gradient training exposure.', '',
              'The [prepared identity packet](../data/manifests/codemix_overlap_request_20261127.json) contains all 1,198 canonical '
              'clip IDs, video IDs, timestamps, channel IDs, durations and waveform hashes, without audio or transcript text. '
              'It has not been sent to anyone. The packet can support an author-confirmed intersection or a local check if a '
              'training manifest is released.', '',
              'Keep the 25.94% WER result as a separate exploratory result for now. Do not describe it as contaminated or '
              'as independently confirmed unseen-data performance. The main report, PDF and publication remain unchanged.', '',
              'The [machine-readable audit](../results/metrics/codemix_training_overlap_audit_20261127.json) records all matches, '
              'source hashes and unresolved questions. Replay locally, without any new network/model calls:', '',
              '```powershell', '.\\.venv\\Scripts\\python.exe src/audit_codemix_training_overlap.py', '```', '']
    (ROOT / 'reports/codemix_training_overlap_audit_20261127.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({'status': result['status'], 'source_dataset_split_check': split_check,
                      'public_test_candidate_counts': tally, 'training_membership_count': None,
                      'authors_contacted': False}, indent=2))


if __name__ == '__main__':
    main()
