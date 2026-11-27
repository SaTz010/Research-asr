"""Paired forced-Nepali versus saved automatic results; no inference or network."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version as package_version
import json
import math

import numpy as np

from analyze_cmi import SYSTEMS, audit_rows, build_rows, plt, rho
from analyze_uncertainty import COUNT_KEYS, video_counts, video_design
from asr_common import normalize_text
from budget import cmi_band
from check_local_environment import ROOT
from compare_audited_references import aggregate, compare_subset, load_verified_inputs
from local_whisper_pilot import save_state
from prepare_forced_nepali import MAIN, PROTOCOL
from prepare_validation_check import BANDS
from run_evaluation import verify_followup

CONDITIONS = ['auto', 'forced_ne']
STEM = 'forced_ne_comparison_20261124'


def paired_group(automatic, forced, video_ids, weights, settings):
    """Keep all four outcomes paired in the same video/channel resamples."""
    if ([{k: r[k] for k in ['clip_id', 'video_id', 'channel', 'cmi']} for r in automatic]
            != [{k: r[k] for k in ['clip_id', 'video_id', 'channel', 'cmi']} for r in forced]):
        raise ValueError('Conditions must contain the same ordered clip identities and CMI.')
    result = {'clips': len(automatic), 'videos': len({r['video_id'] for r in automatic}),
              'channel_clips': dict(Counter(r['channel'] for r in automatic)),
              'systems': {}, 'change_difference_local_minus_api_pp': None,
              'change_difference_interval_95_pp': None, 'invalid_zero_denominator_draws': 0}
    if not automatic:
        return {**result, 'interval_status': 'withheld_empty_group'}
    counts = np.stack([video_counts(rows, video_ids) for rows in [automatic, forced]], axis=1)
    if not np.array_equal(counts[:, 0, :, [1, 3]], counts[:, 1, :, [1, 3]]):
        raise ValueError('Reference denominators differ between conditions.')
    for system in SYSTEMS:
        scores = {condition: aggregate([r['systems'][system] for r in rows])
                  for condition, rows in zip(CONDITIONS, [automatic, forced])}
        result['systems'][system] = {
            **scores, 'forced_minus_auto_pp': {m: 100 * (scores['forced_ne'][m] - scores['auto'][m])
                                              for m in ['wer', 'cer', 'raw_wer', 'raw_cer']},
            'interval_95_pp': None,
            'paired_clip_changes': {metric: {
                label: sum(test(b['systems'][system][errors] - a['systems'][system][errors])
                           for a, b in zip(automatic, forced))
                for label, test in [('improved', lambda d: d < 0), ('tied', lambda d: d == 0),
                                    ('worsened', lambda d: d > 0)]}
                for metric, errors in [('wer', 'word_errors'), ('cer', 'character_errors')]}}
    result['change_difference_local_minus_api_pp'] = {
        m: result['systems']['local']['forced_minus_auto_pp'][m]
        - result['systems']['whisper_api']['forced_minus_auto_pp'][m] for m in ['wer', 'cer']}
    if result['videos'] < settings['minimum_videos_for_interval']:
        return {**result, 'interval_status': 'withheld_fewer_than_minimum_videos'}
    sampled = (weights @ counts.reshape(len(video_ids), -1)).reshape(len(weights), 2, 2, 4)
    valid = np.all(sampled[..., [1, 3]] > 0, axis=(1, 2, 3))
    result['invalid_zero_denominator_draws'] = int((~valid).sum())
    if not valid.all():
        return {**result, 'interval_status': 'withheld_zero_denominator_draws'}
    intervals, interactions = {}, {}
    for metric, error, denominator in [('wer', 0, 1), ('cer', 2, 3)]:
        rates = sampled[..., error] / sampled[..., denominator]
        changes = 100 * (rates[:, 1, :] - rates[:, 0, :])
        intervals[metric] = np.percentile(changes, settings['percentiles'], axis=0, method='linear')
        interactions[metric] = np.percentile(changes[:, 0] - changes[:, 1],
                                            settings['percentiles'], method='linear').tolist()
    for s, system in enumerate(SYSTEMS):
        result['systems'][system]['interval_95_pp'] = {m: v[:, s].tolist() for m, v in intervals.items()}
    result['change_difference_interval_95_pp'] = interactions
    return {**result, 'interval_status': 'exploratory_paired_percentile_interval'}


def load_forced(original):
    content = (ROOT / MAIN).read_bytes()
    manifest = json.loads(content)
    verify_followup(manifest)
    if manifest['clips'] != original['clips'] or manifest['dataset'] != original['dataset']:
        raise ValueError('Forced and automatic full populations differ.')
    sources = {'forced_manifest': hashlib.sha256(content).hexdigest()}
    predictions, periods = {}, {}
    expected = {e['identity']['clip_id']: e for e in manifest['clips']}
    for system in SYSTEMS:
        name = f'{(ROOT / MAIN).stem}_{system}'
        path = ROOT / f'results/predictions/{name}.json'
        content = path.read_bytes()
        state = json.loads(content)
        verified_path = ROOT / f'results/metrics/{name}_verified.json'
        verified = json.loads(verified_path.read_bytes())
        spec = state['run_spec']
        if (hashlib.sha256(content).hexdigest() != verified['predictions_sha256']
                or verified['coverage'] != {'expected': len(expected), 'received': len(expected), 'complete': True}
                or verified.get('condition') != 'forced_ne'
                or spec.get('condition') != 'forced_ne' or spec['system'] != system
                or spec['manifest_sha256'] != sources['forced_manifest']
                or spec['dataset'] != manifest['dataset']
                or spec['config'] != manifest['frozen_system_configs'][system]
                or spec['packages'] != manifest['frozen_packages'][system]
                or spec.get('protocol_config_sha256') != manifest['protocol_config_sha256']):
            raise ValueError('Forced outputs/settings differ from the verified condition.')
        saved = {r['clip_id']: r for r in state['predictions']}
        if len(saved) != len(state['predictions']) or set(saved) != set(expected):
            raise ValueError('Forced output coverage/uniqueness differs.')
        for key, row in saved.items():
            if (row['status'] != 'received' or not isinstance(row.get('hypothesis'), str)
                    or any(row.get(k) != v for k, v in expected[key]['identity'].items())
                    or spec['payload_sha256'][key] != expected[key]['payload_sha256']):
                raise ValueError('Forced saved identity/payload/response differs.')
        predictions[system] = saved
        sources[system + '_forced_predictions'] = hashlib.sha256(content).hexdigest()
        sources[system + '_forced_verification'] = hashlib.sha256(verified_path.read_bytes()).hexdigest()
        dates = [r['requested_at_utc'] for r in saved.values()]
        periods[system] = {'first_requested_at_utc': min(dates), 'last_requested_at_utc': max(dates)}
    return manifest, predictions, sources, periods


def check_counts(group, prefix):
    for system in SYSTEMS:
        verification = json.loads((ROOT / f'results/metrics/{prefix}_{system}_verified.json').read_bytes())
        if (any(group[system][k] != verification['independent_edit_counts'][k] for k in COUNT_KEYS)
                or any(not math.isclose(group[system][m], verification['independent_scores'][m], abs_tol=1e-12)
                       for m in ['wer', 'cer', 'raw_wer', 'raw_cer'])):
            raise ValueError('Recomputed corpus scores differ from independent verification.')


def markdown_report(result):
    def interval(values, metric):
        def number(v):
            return f'{v:+.3f}' if 0 < abs(v) < .01 else f'{v:+.2f}'
        return f'[{number(values[metric][0])}, {number(values[metric][1])}]' if values else 'Withheld'

    lines = ['# Forced Nepali versus automatic language — November 24, 2026', '',
             'Both forced-Nepali systems completed all 1,198 test clips and passed independent verification. '
             'This comparison reuses the original automatic outputs and makes no new inference/API calls.', '',
             '## Plain-language result', '',
             'Forcing Nepali did not improve either overall exact-transcript score on this dataset. '
             'Word and character error rates increased slightly. Individual clips improved, worsened or tied; '
             'these are corpus averages, not a claim that every transcript became worse.', '',
             '## Same 1,198 clips, unchanged references', '',
             '| System | Automatic WER | Forced WER | Change (pp) | Automatic CER | Forced CER | Change (pp) |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for system, label in SYSTEMS.items():
        s = result['overall']['systems'][system]
        lines.append(f"| {label} | {100*s['auto']['wer']:.2f}% | {100*s['forced_ne']['wer']:.2f}% | {s['forced_minus_auto_pp']['wer']:+.2f} | {100*s['auto']['cer']:.2f}% | {100*s['forced_ne']['cer']:.2f}% | {s['forced_minus_auto_pp']['cer']:+.2f} |")
    lines += ['', 'Positive forced-minus-automatic changes mean more error with forced Nepali. '
              'Corpus rates sum edit counts before dividing by the same reference units; they are not averages of per-clip percentages. '
              'Strict WER/CER measure agreement with mixed-script silver references, not semantic understanding.', '',
              '## Paired video uncertainty and CMI groups', '',
              'The frozen method uses 2,000 video resamples within each of the two observed channels, seed 42. '
              'All four outcomes for a video receive the same multiplicity. Intervals are exploratory and conditional '
              'on these sources/references. Groups with fewer than ten videos or any zero-denominator draw have no interval.', '',
              '| Group | Clips | Videos | Local WER change (pp) | 95% interval | API WER change (pp) | 95% interval |',
              '|---|---:|---:|---:|---|---:|---|']
    for name, g in {'Overall': result['overall'], **result['bands']}.items():
        a, b = (g['systems'][s] for s in SYSTEMS)
        lines.append(f"| {name} | {g['clips']} | {g['videos']} | {a['forced_minus_auto_pp']['wer']:+.2f} | {interval(a['interval_95_pp'],'wer')} | {b['forced_minus_auto_pp']['wer']:+.2f} | {interval(b['interval_95_pp'],'wer')} |")
    lines += ['', '![Forced-minus-automatic uncertainty](../results/figures/forced_ne_change_20261124.png)', '',
              'The local-minus-API difference in the language-setting change is estimated directly from all four paired outcomes. '
              'This avoids inferring a difference merely because two separate intervals have different labels.', '',
              '| Metric | Local change (pp) | 95% interval | API change (pp) | 95% interval | Local change minus API change (pp) | 95% interval |',
              '|---|---:|---|---:|---|---:|---|']
    g = result['overall']
    for metric in ['wer', 'cer']:
        a, b = (g['systems'][s] for s in SYSTEMS)
        lines.append(f"| {metric.upper()} | {a['forced_minus_auto_pp'][metric]:+.2f} | {interval(a['interval_95_pp'],metric)} | {b['forced_minus_auto_pp'][metric]:+.2f} | {interval(b['interval_95_pp'],metric)} | {g['change_difference_local_minus_api_pp'][metric]:+.2f} | {interval(g['change_difference_interval_95_pp'],metric)} |")
    lines += ['', 'These intervals do not measure provider rerun variability or human-annotation uncertainty. '
              'CMI bands are exploratory summaries, not simultaneous confidence intervals or causal mixing effects.', '',
              'Both overall WER intervals span zero: the small observed increases do not establish a reliable direction '
              'for word error under this resampling design. Both CER intervals lie above zero; the local lower bound '
              'is extremely close to zero. Both local-minus-API change intervals span zero, so this comparison does '
              'not establish that the systems respond differently to the language setting.', '',
              '## Clip-level changes', '',
              '| System | Metric | Improved | Tied edit count | Worsened | Identical normalized transcript |',
              '|---|---|---:|---:|---:|---:|']
    for system, label in SYSTEMS.items():
        for metric in ['wer', 'cer']:
            c = g['systems'][system]['paired_clip_changes'][metric]
            lines.append(f"| {label} | {metric.upper()} | {c['improved']} | {c['tied']} | {c['worsened']} | {result['output_changes'][system]['identical_normalized_transcripts']} |")
    lines += ['', 'Tied edit counts can occur even when output text differs. Improvements/worsenings compare each clip with its own automatic result, using identical reference denominators. '
              'There are more improved clips than worsened clips in both systems, but a few larger deteriorations '
              'outweigh the smaller improvements in summed word edits. Counting clips and measuring corpus error answer different questions.', '',
              '## Raw-text sensitivity', '',
              'The primary scores above retain the original normalization. Raw scores preserve case and punctuation '
              '(with the existing whitespace handling). They are sensitivity checks, not substitute primary outcomes.', '',
              '| System | Automatic raw WER | Forced raw WER | Change (pp) | Automatic raw CER | Forced raw CER | Change (pp) |',
              '|---|---:|---:|---:|---:|---:|---:|']
    for system, label in SYSTEMS.items():
        s = result['overall']['systems'][system]
        lines.append(f"| {label} | {100*s['auto']['raw_wer']:.2f}% | {100*s['forced_ne']['raw_wer']:.2f}% | {s['forced_minus_auto_pp']['raw_wer']:+.2f} | {100*s['auto']['raw_cer']:.2f}% | {100*s['forced_ne']['raw_cer']:.2f}% | {s['forced_minus_auto_pp']['raw_cer']:+.2f} |")
    lines += ['', 'Local raw WER decreases slightly while normalized WER increases slightly. '
              'The direction of this small word-error change is sensitive to scoring conventions; '
              'neither result implies a measured change in semantic accuracy.', '',
              '## Fifty-clip reference sensitivity', '',
              'This separately audited, balanced subset is not representative of the full corpus. '
              'Both conditions use the same reference version within each comparison. The corrected condition also uses the audited lexical CMI.', '',
              '| Reference version | System | Automatic WER | Forced WER | Change (pp) | Automatic CER | Forced CER | Change (pp) |',
              '|---|---|---:|---:|---:|---:|---:|---:|']
    for version, subset in result['audit_sensitivity'].items():
        for system, label in SYSTEMS.items():
            s = subset['overall']['systems'][system]
            lines.append(f"| {version} | {label} | {100*s['auto']['wer']:.2f}% | {100*s['forced_ne']['wer']:.2f}% | {s['forced_minus_auto_pp']['wer']:+.2f} | {100*s['auto']['cer']:.2f}% | {100*s['forced_ne']['cer']:.2f}% | {s['forced_minus_auto_pp']['cer']:+.2f} |")
    lines += ['', '## Scope and next work', '',
              'The new local run keeps the original pinned Large V2 weights, software and decoding settings; '
              'the exposed language setting changes to `ne`. The hosted model remains `whisper-1`, with `language="ne"`. '
              'API automatic and forced runs occurred at different times, so hosted differences can also reflect service variability. '
              'A forced Nepali label is not an independently measured language-detection success.', '',
              'The earlier five-clip API pilot was unchanged across settings; it did not predict the full-corpus result. '
              'This null-to-worse corpus finding is a useful outcome and does not require buying another round of calls.', '',
              'The next qualitative task is to review the same ten selected examples with both new forced outputs. '
              'No new tolerant word equivalences or causes of error are inferred automatically. '
              'The published v0.5 main report and baseline results remain intact; this separate follow-up is ready for later report integration.', '',
              'Full per-clip counts, raw-score sensitivity, CMI bands, channel comparisons, correlations, '
              'bootstrap draws, source checksums and execution-date ranges are in '
              '[the analysis JSON](../results/metrics/forced_ne_comparison_20261124.json).', '',
              '```powershell', '.\\.venv\\Scripts\\python.exe src/analyze_forced_nepali.py', '```', '']
    return '\n'.join(lines)


def plot_changes(result):
    groups = {'Overall': result['overall'], **result['bands']}
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    for ax, metric in zip(axes, ['wer', 'cer']):
        for system, color, offset in [('local', '#1769aa', -.12), ('whisper_api', '#d66a13', .12)]:
            for i, group in enumerate(groups.values()):
                values = group['systems'][system]
                interval = values['interval_95_pp']
                if interval:
                    ax.hlines(i + offset, *interval[metric], color=color)
                ax.plot(values['forced_minus_auto_pp'][metric], i + offset, 'o', color=color,
                        label=SYSTEMS[system] if i == 0 else None)
        ax.axvline(0, color='#777777', linestyle='--', linewidth=1)
        ax.set(xlabel=f'Forced minus automatic {metric.upper()} (percentage points)',
               yticks=range(len(groups)), yticklabels=[f"{k} (n={v['clips']})" for k, v in groups.items()])
        ax.legend()
        ax.grid(axis='x', alpha=.15)
    axes[0].invert_yaxis()
    fig.suptitle('Same 1,198 clips; saved automatic outputs reused\n2,000 paired video resamples within channels; negative means lower forced error', fontsize=11)
    fig.tight_layout()
    for extension in ['png', 'svg']:
        fig.savefig(ROOT / f'results/figures/forced_ne_change_20261124.{extension}', dpi=200, bbox_inches='tight')
    plt.close(fig)


def main():
    selection, audit, original, automatic, sources = load_verified_inputs()
    manifest, forced, forced_sources, periods = load_forced(original)
    protocol = json.loads((ROOT / PROTOCOL).read_bytes())
    settings = protocol['analysis']['bootstrap']
    rows = {c: build_rows(manifest, saved) for c, saved in [('auto', automatic), ('forced_ne', forced)]}
    video_ids, channels, weights = video_design(rows['auto'], settings)
    if len(rows['auto']) != 1198 or len(video_ids) != 22 or sorted(Counter(channels.values()).values()) != [3, 19]:
        raise ValueError('Frozen population differs.')
    group = lambda a, b: paired_group(a, b, video_ids, weights, settings)
    by_band = lambda a, b: {band: group([r for r in a if cmi_band(r['cmi']) == band],
                                       [r for r in b if cmi_band(r['cmi']) == band]) for band in BANDS}
    overall = group(rows['auto'], rows['forced_ne'])
    for condition, prefix in [('auto', 'test_cs_benchmark_20261112'), ('forced_ne', 'test_cs_forced_ne_20261124')]:
        check_counts({s: overall['systems'][s][condition] for s in SYSTEMS}, prefix)
    result = {'computed_at_utc': datetime.now(timezone.utc).isoformat(), 'condition': 'forced_ne',
              'inference_requests': 0, 'automatic_outputs_reused': True, 'frozen_inputs_modified': False,
              'difference_sign': 'forced minus automatic; positive means more forced error',
              'interaction_sign': '(local forced-auto) minus (API forced-auto)',
              'source_sha256': {**sources, **forced_sources, 'followup_protocol': hashlib.sha256((ROOT / PROTOCOL).read_bytes()).hexdigest(),
                                'analysis_code': hashlib.sha256((ROOT / 'src/analyze_forced_nepali.py').read_bytes()).hexdigest()},
              'bootstrap_settings': settings, 'video_ids': video_ids, 'video_channels': channels,
              'draw_video_multiplicities': weights.tolist(), 'forced_execution_periods': periods,
              'automatic_execution_periods': {s: {'first_requested_at_utc': min(r['requested_at_utc'] for r in automatic[s].values()),
                                                  'last_requested_at_utc': max(r['requested_at_utc'] for r in automatic[s].values())}
                                              for s in SYSTEMS},
              'analysis_packages': {p: package_version(p) for p in ['numpy', 'scipy', 'matplotlib', 'jiwer']},
              'overall': overall, 'bands': by_band(rows['auto'], rows['forced_ne']),
              'channels': {c: group(*[[r for r in rows[k] if r['channel'] == c] for k in CONDITIONS])
                           for c in sorted(set(channels.values()))},
              'continuous_associations': {s: {f'cmi_vs_{c}_{m}': rho([r['cmi'] for r in rows[c]], [r['systems'][s][m] for r in rows[c]])
                                              for c in CONDITIONS for m in ['wer', 'cer']} for s in SYSTEMS},
              'output_changes': {s: {
                  'identical_exact_transcripts': sum(automatic[s][k]['hypothesis'] == forced[s][k]['hypothesis'] for k in automatic[s]),
                  'identical_normalized_transcripts': 0} for s in SYSTEMS},
              'audit_sensitivity': {},
              'per_clip': [{k: a[k] for k in ['clip_id', 'video_id', 'channel', 'cmi', 'duration_s']}
                           | {'conditions': {'auto': a['systems'], 'forced_ne': b['systems']}}
                           for a, b in zip(rows['auto'], rows['forced_ne'])],
              'limitations': protocol['limitations']}
    for s in SYSTEMS:
        result['output_changes'][s]['identical_normalized_transcripts'] = sum(
            normalize_text(automatic[s][k]['hypothesis']) == normalize_text(forced[s][k]['hypothesis']) for k in automatic[s])
    comparisons = {c: compare_subset(selection['clips'], audit['reviews'], saved)
                   for c, saved in [('auto', automatic), ('forced_ne', forced)]}
    for version in ['published', 'corrected']:
        a, b = [audit_rows(comparisons[c], rows[c], version) for c in CONDITIONS]
        result['audit_sensitivity'][version] = {'overall': group(a, b), 'bands': by_band(a, b)}
    if sum(g['clips'] for g in result['bands'].values()) != 1198:
        raise ValueError('CMI group coverage differs.')
    json.dumps(result, allow_nan=False)
    save_state(ROOT / f'results/metrics/{STEM}.json', result)
    plot_changes(result)
    (ROOT / f'reports/{STEM}.md').write_text(markdown_report(result), encoding='utf-8')
    print(json.dumps({'overall': result['overall'], 'output_changes': result['output_changes']}, indent=2))


if __name__ == '__main__':
    main()
