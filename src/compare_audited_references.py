"""Compare frozen published/human references and rescore the same 50 saved outputs."""
from collections import Counter
import hashlib
import html
import json
import math

from jiwer import cer, wer

from asr_common import normalize_text
from budget import cmi_band
from check_local_environment import ROOT
from local_whisper_pilot import save_state
from reference_audit import validate_reviews
from verify_local_pilot import distance

COUNTS = ['word_errors', 'reference_words', 'character_errors', 'reference_characters',
          'raw_word_errors', 'raw_reference_words', 'raw_character_errors', 'raw_reference_characters']
RATES = [('wer', 'word_errors', 'reference_words'), ('cer', 'character_errors', 'reference_characters'),
         ('raw_wer', 'raw_word_errors', 'raw_reference_words'), ('raw_cer', 'raw_character_errors', 'raw_reference_characters')]
ROUNDING_TOLERANCE = 0.0050001


def add_rates(counts):
    return {**counts, **{name: counts[errors] / counts[units] for name, errors, units in RATES}}


def text_scores(reference, hypothesis):
    ref, hyp = normalize_text(reference), normalize_text(hypothesis)
    if not ref:
        raise ValueError('A nonempty normalized reference is required.')
    raw_ref, raw_hyp = ' '.join(reference.split()), ' '.join(hypothesis.split())
    return add_rates({
        'word_errors': distance(ref.split(), hyp.split()), 'reference_words': len(ref.split()),
        'character_errors': distance(ref.replace(' ', ''), hyp.replace(' ', '')),
        'reference_characters': len(ref.replace(' ', '')),
        'raw_word_errors': distance(raw_ref.split(), raw_hyp.split()), 'raw_reference_words': len(raw_ref.split()),
        'raw_character_errors': distance(raw_ref.replace(' ', ''), raw_hyp.replace(' ', '')),
        'raw_reference_characters': len(raw_ref.replace(' ', ''))})


def aggregate(scores):
    if not scores:
        raise ValueError('Cannot score an empty selection.')
    return add_rates({name: sum(row[name] for row in scores) for name in COUNTS})


def compare_subset(entries, reviews, predictions):
    ids = [e['identity']['clip_id'] for e in entries]
    if not ids or len(ids) != len(set(ids)) or len(reviews) != len(ids):
        raise ValueError('Selection/reviews must contain unique, paired clips.')
    if {r['clip_id'] for r in reviews} != set(ids) or len({r['clip_id'] for r in reviews}) != len(reviews):
        raise ValueError('Review clip identities differ from selection.')
    if set(predictions) != {'local', 'whisper_api'}:
        raise ValueError('Both local and hosted saved predictions are required.')
    by_review = {r['clip_id']: r for r in reviews}
    rows = []
    for entry in entries:
        identity = entry['identity']
        key = identity['clip_id']
        review = by_review[key]
        published, corrected = identity['transcription'], review['corrected_reference']
        if review['verdict'] not in {'match', 'corrected'}:
            raise ValueError('Resolve every selected human reference before comparison.')
        scores = {}
        for system, saved in predictions.items():
            prediction = saved.get(key)
            if prediction is None or prediction.get('status') != 'received' or not isinstance(prediction.get('hypothesis'), str):
                raise ValueError(f'Missing successful prediction for {system}: {key}.')
            if prediction.get('transcription') != published:
                raise ValueError('Saved prediction and published reference differ.')
            scores[system] = {version: text_scores(reference, prediction['hypothesis'])
                              for version, reference in [('published', published), ('corrected', corrected)]}
        difference = review['audited_cmi'] - identity['cmi']
        rows.append({'number': review['number'], 'clip_id': key, 'verdict': review['verdict'],
                     'published_reference': published, 'corrected_reference': corrected, 'notes': review['notes'],
                     'exact_text_changed': published != corrected,
                     'normalized_text_changed': normalize_text(published) != normalize_text(corrected),
                     'reference_disagreement': text_scores(corrected, published),
                     'published_cmi': identity['cmi'], 'audited_cmi': review['audited_cmi'], 'cmi_delta': difference,
                     'cmi_changed_beyond_rounding': abs(difference) > ROUNDING_TOLERANCE,
                     'published_band': cmi_band(identity['cmi']), 'audited_band': cmi_band(review['audited_cmi']),
                     'systems': scores})
    systems = {}
    for system in predictions:
        published = aggregate([r['systems'][system]['published'] for r in rows])
        corrected = aggregate([r['systems'][system]['corrected'] for r in rows])
        systems[system] = {'published': published, 'corrected': corrected,
                           'corrected_minus_published_percentage_points': {name: 100 * (corrected[name] - published[name])
                                                                           for name, _, _ in RATES}}
        # Check independent edit counts against the installed metric library at corpus level.
        hyps = [predictions[system][key]['hypothesis'] for key in ids]
        for version, totals in [('published', published), ('corrected', corrected)]:
            refs = [r[version + '_reference'] for r in rows]
            normalized_refs, normalized_hyps = [normalize_text(t) for t in refs], [normalize_text(t) for t in hyps]
            checks = {'wer': wer(normalized_refs, normalized_hyps),
                      'cer': cer([t.replace(' ', '') for t in normalized_refs], [t.replace(' ', '') for t in normalized_hyps]),
                      'raw_wer': wer([' '.join(t.split()) for t in refs], [' '.join(t.split()) for t in hyps]),
                      'raw_cer': cer([''.join(t.split()) for t in refs], [''.join(t.split()) for t in hyps])}
            if any(not math.isclose(totals[name], value, abs_tol=1e-12) for name, value in checks.items()):
                raise ValueError('Independent counts and jiwer corpus scores differ.')
    return {'selected_clips': len(rows), 'exact_text_changed_clips': sum(r['exact_text_changed'] for r in rows),
            'normalized_text_changed_clips': sum(r['normalized_text_changed'] for r in rows),
            'reference_disagreement_orientation': 'Human-corrected transcript is the reference; published transcript is the hypothesis.',
            'reference_disagreement': aggregate([r['reference_disagreement'] for r in rows]),
            'published_cmi_rounding_tolerance': ROUNDING_TOLERANCE,
            'cmi_changed_beyond_rounding_clips': sum(r['cmi_changed_beyond_rounding'] for r in rows),
            'cmi_band_changed_numbers': [r['number'] for r in rows if r['published_band'] != r['audited_band']],
            'published_band_counts': dict(Counter(r['published_band'] for r in rows)),
            'audited_band_counts': dict(Counter(r['audited_band'] for r in rows)), 'systems': systems, 'per_clip': rows}


def markdown_report(result):
    def cell(value):
        return html.escape(str(value), quote=False).replace('\\', '\\\\').replace('|', '\\|').replace('`', '\\`').replace('\r', ' ').replace('\n', '<br>')

    disagreement = result['reference_disagreement']
    lines = ['# Published versus human-reviewed references — 50-clip audit', '',
             'Computed November 16, 2026 from frozen reviews and saved local/API predictions. No new ASR, network or credential access is needed.', '',
             '## What changed', '',
             f"- {result['selected_clips'] - result['exact_text_changed_clips']} references are unchanged; {result['exact_text_changed_clips']} were edited.",
             f"- {result['normalized_text_changed_clips']} edits remain after the frozen scoring normalization.",
             f"- Published text differs from the human reference by {disagreement['word_errors']} normalized word edits over {disagreement['reference_words']} human-reference words and {disagreement['character_errors']} character edits over {disagreement['reference_characters']} human-reference characters.",
             f"- Reference-disagreement WER/CER: {100 * disagreement['wer']:.2f}% / {100 * disagreement['cer']:.2f}%. These measure text disagreement with the human version as reference, not ASR performance or independently established ground-truth accuracy.", '',
             '## ASR reference sensitivity — exactly the same 50 clips', '',
             'The hypotheses are fixed. Only the reference version changes. Corpus totals use total edits / total reference units; corrected references can change denominators. Negative score changes mean lower measured error rates, not necessarily fewer edits.', '',
             '| System | Reference | Reference words | WER | CER |', '|---|---|---:|---:|---:|']
    for system, label in [('local', 'Local Large V2'), ('whisper_api', 'Whisper API')]:
        for version in ['published', 'corrected']:
            score = result['systems'][system][version]
            lines.append(f"| {label} | {version} | {score['reference_words']} | {100 * score['wer']:.2f}% | {100 * score['cer']:.2f}% |")
    lines += ['', '| System | WER change (corrected − published) | CER change |', '|---|---:|---:|']
    for system, label in [('local', 'Local Large V2'), ('whisper_api', 'Whisper API')]:
        delta = result['systems'][system]['corrected_minus_published_percentage_points']
        lines.append(f"| {label} | {delta['wer']:+.2f} pp | {delta['cer']:+.2f} pp |")
    lines += ['', 'Word-edit and denominator checks:', '']
    for system, label in [('local', 'Local Large V2'), ('whisper_api', 'Whisper API')]:
        original = result['systems'][system]['published']
        corrected = result['systems'][system]['corrected']
        lines.append(f"- {label}: word edits {original['word_errors']} → {corrected['word_errors']}; reference words {original['reference_words']} → {corrected['reference_words']}.")
    lines += ['', 'A decrease in WER need not mean fewer edit operations: reference content/length changes the denominator while the model hypotheses remain fixed. WER can exceed 100% because insertions count as errors. These 50-clip scores are not the 1,198-clip scores.', '',
              'Raw-case/punctuation sensitivity is also retained in the JSON output; the table above uses the frozen primary normalization.', '',
              '## CMI sensitivity', '',
              f"{result['cmi_changed_beyond_rounding_clips']} audited CMI values differ beyond the ±0.005-point rounding allowance for two-decimal source values. {len(result['cmi_band_changed_numbers'])} clips change bands: {', '.join(str(n) for n in result['cmi_band_changed_numbers']) or 'none'}.", '',
              'The published CMI uses source script-based labels; the audited value uses normalized corrected words and human lexical tags, excluding language-independent/other tokens. Differences can reflect reference edits, tokenization, denominator conventions or language judgments. Do not attribute them solely to tag overrides.', '',
              '| CMI band | Published selection | Human audited |', '|---|---:|---:|']
    for band in ['[0,10]', '(10,20]', '(20,30]', '(30,40]', '(40,50]']:
        lines.append(f"| {band} | {result['published_band_counts'].get(band, 0)} | {result['audited_band_counts'].get(band, 0)} |")
    lines += ['', '## All 50 original and reviewed transcripts', '',
              'The human text is copied from the frozen review without additional editing. Word edits use the human reference as denominator. CMI is displayed to two decimals only here; calculations retain full precision.', '',
              '| Item | Published dataset transcript | Human-reviewed transcript | Published → audited CMI | Word edits |',
              '|---|---|---|---:|---:|']
    for row in result['per_clip']:
        lines.append(f"| {row['number']} | {cell(row['published_reference'])} | {cell(row['corrected_reference'])} | {row['published_cmi']:.2f} → {row['audited_cmi']:.2f} | {row['reference_disagreement']['word_errors']} |")
    lines += ['', '## Notes on changed references', '']
    for row in result['per_clip']:
        if row['exact_text_changed']:
            lines.append(f"- Item {row['number']} (`{row['clip_id']}`): {cell(row['notes']) or 'No correction note recorded.'}")
    lines += ['', '## Limits and reproduction', '',
              'This is a balanced 10-per-published-CMI-band diagnostic audit across 18 videos and two source channels, not a random population sample. One researcher reviewed script-suggested tags; the assistant did not independently listen. The corrected references are operational references for sensitivity analysis, not an independent gold standard. Do not extrapolate the edited-clip fraction to the entire dataset.', '',
              'Compare these 50-clips scores only with each other. The 1,198-clip overall scores use a different population and remain unchanged. This analysis does not establish a CMI effect, statistical significance, a causal hosting effect or a general model ranking. Predeclared uncertainty/CMI analyses and report preparation remain outstanding.', '',
              'Original refs: `data/manifests/reference_audit_20261105_selection.json`. Human refs: `data/annotations/reference_audit_20261112_frozen.json`. Source dataset: `saileshbro/nepali-cs-asr`, pinned revision `dd00ca41dd38774cd6097c372c16939d7f3746df`, CC BY-NC 4.0 as recorded in the pinned dataset card. No source audio is copied into this report.', '',
              '```powershell', '.\\.venv\\Scripts\\python.exe src/compare_audited_references.py', '```', '',
              'The JSON result contains per-clip identities, text/version scores, edit counts, raw sensitivity, CMI changes and source checksums. Re-running uses saved outputs and adds no transcription requests.', '']
    return '\n'.join(lines)


def load_verified_inputs():
    paths = {'selection': ROOT / 'data/manifests/reference_audit_20261105_selection.json',
             'audit': ROOT / 'data/annotations/reference_audit_20261112_frozen.json',
             'manifest': ROOT / 'data/manifests/test_cs_benchmark_20261112.json'}
    contents = {key: path.read_bytes() for key, path in paths.items()}
    inputs = {key: json.loads(content) for key, content in contents.items()}
    checksums = {key: hashlib.sha256(content).hexdigest() for key, content in contents.items()}
    selection, audit, manifest = (inputs[name] for name in ['selection', 'audit', 'manifest'])
    if (not audit.get('frozen') or not audit.get('reviewer') or audit['selection_sha256'] != checksums['selection']
            or manifest['reference_audit_sha256'] != checksums['audit']
            or selection['evaluation_manifest_sha256'] != manifest['source_pool_sha256']):
        raise ValueError('Frozen audit, selection and evaluation-pool provenance differ.')
    validate_reviews(audit, selection)
    protocol_path = ROOT / manifest['protocol_config']
    protocol_bytes = protocol_path.read_bytes()
    if hashlib.sha256(protocol_bytes).hexdigest() != manifest['protocol_config_sha256']:
        raise ValueError('Frozen protocol differs.')
    checksums['protocol'] = hashlib.sha256(protocol_bytes).hexdigest()
    identities = {entry['identity']['clip_id']: entry for entry in manifest['clips']}
    for entry in selection['clips']:
        expected = identities[entry['identity']['clip_id']]
        if entry != expected:
            raise ValueError('Selected reference/input differs from the frozen full manifest.')
    predictions = {}
    for system in ['local', 'whisper_api']:
        path = ROOT / 'results/predictions' / f'test_cs_benchmark_20261112_{system}.json'
        content = path.read_bytes()
        verified_path = ROOT / 'results/metrics' / f'test_cs_benchmark_20261112_{system}_verified.json'
        verified = json.loads(verified_path.read_text(encoding='utf-8'))
        checksum = hashlib.sha256(content).hexdigest()
        if checksum != verified['predictions_sha256'] or not verified['coverage']['complete']:
            raise ValueError('Predictions differ from the verified full run.')
        state = json.loads(content)
        spec = state['run_spec']
        if spec['manifest_sha256'] != checksums['manifest'] or spec['config'] != manifest['frozen_system_configs'][system]:
            raise ValueError('Run inputs/settings differ from the frozen manifest.')
        rows = state['predictions']
        by_id = {row['clip_id']: row for row in rows}
        if len(rows) != len(by_id) or set(by_id) != set(identities):
            raise ValueError('Full-run prediction coverage differs.')
        for key, row in by_id.items():
            if (any(row.get(field) != value for field, value in identities[key]['identity'].items())
                    or spec['payload_sha256'][key] != identities[key]['payload_sha256']):
                raise ValueError('Prediction identity/payload differs from the frozen source.')
        predictions[system] = by_id
        checksums[system + '_predictions'] = checksum
        checksums[system + '_verification'] = hashlib.sha256(verified_path.read_bytes()).hexdigest()
    return selection, audit, manifest, predictions, checksums


def main():
    selection, audit, manifest, predictions, checksums = load_verified_inputs()
    result = compare_subset(selection['clips'], audit['reviews'], predictions)
    result.update(computed_on='2026-11-16', source_sha256=checksums, reviewer=audit['reviewer'],
                  inference_requests=0, frozen_inputs_modified=False,
                  scope='Same frozen 50-clip audit, fixed hypotheses, separate published/corrected reference versions. Single-reviewer sensitivity, not population-representative gold truth.')
    output = ROOT / 'results/metrics/audited_reference_comparison_20261116.json'
    save_state(output, result)
    (ROOT / 'reports/audited_reference_comparison_20261116.md').write_text(markdown_report(result), encoding='utf-8')
    print(json.dumps({key: result[key] for key in ['selected_clips', 'exact_text_changed_clips',
                       'normalized_text_changed_clips', 'reference_disagreement', 'cmi_changed_beyond_rounding_clips',
                       'cmi_band_changed_numbers', 'systems']}, indent=2))


if __name__ == '__main__':
    main()
