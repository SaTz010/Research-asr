"""Paired video-cluster bootstrap under the frozen protocol; no inference."""
from collections import Counter
import hashlib
from importlib.metadata import version
import json
import math

from analyze_cmi import (ROOT, SYSTEMS, audit_rows, build_rows, duration_groups,
                         plt, summarize)
from budget import cmi_band
from compare_audited_references import compare_subset, load_verified_inputs
from local_whisper_pilot import save_state
from prepare_validation_check import BANDS
import numpy as np

COUNT_KEYS = ['word_errors', 'reference_words', 'character_errors', 'reference_characters']


def video_design(rows, settings):
    if not rows or len({r['clip_id'] for r in rows}) != len(rows):
        raise ValueError('A nonempty selection of unique paired clips is required.')
    channels = {}
    for row in rows:
        video, channel = row['video_id'], row['channel']
        if video in channels and channels[video] != channel:
            raise ValueError('A video cannot span source channels.')
        channels[video] = channel
    video_ids = sorted(channels)
    rng = np.random.default_rng(settings['seed'])
    weights = np.zeros((settings['replicates'], len(video_ids)), dtype=np.int64)
    for channel in sorted(set(channels.values())):
        indices = np.array([i for i, video in enumerate(video_ids) if channels[video] == channel])
        sampled = rng.choice(indices, size=(len(weights), len(indices)), replace=True)
        np.add.at(weights, (np.arange(len(weights))[:, None], sampled), 1)
        if not np.all(weights[:, indices].sum(axis=1) == len(indices)):
            raise ValueError('Bootstrap channel stratum size differs.')
    return video_ids, channels, weights


def video_counts(rows, video_ids):
    indices = {video: i for i, video in enumerate(video_ids)}
    counts = np.zeros((len(video_ids), 2, 4), dtype=np.int64)
    seen = set()
    for row in rows:
        if row['clip_id'] in seen or row['video_id'] not in indices:
            raise ValueError('Duplicate clip or unknown source video.')
        seen.add(row['clip_id'])
        pair = []
        for system in SYSTEMS:
            values = [row['systems'][system][key] for key in COUNT_KEYS]
            if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in values) or not values[1] or not values[3]:
                raise ValueError('Paired edit counts must be nonnegative integers with positive reference lengths.')
            pair.append(values)
        if pair[0][1::2] != pair[1][1::2]:
            raise ValueError('Paired reference denominators differ.')
        counts[indices[row['video_id']]] += pair
    return counts


def point_estimate(counts):
    if counts.shape != (2, 4) or np.any(counts[:, [1, 3]] <= 0):
        raise ValueError('Both systems require nonempty corpus denominators.')
    systems = {system: {**{key: int(value) for key, value in zip(COUNT_KEYS, counts[i])},
                        'wer': float(counts[i, 0] / counts[i, 1]),
                        'cer': float(counts[i, 2] / counts[i, 3])} for i, system in enumerate(SYSTEMS)}
    return {'systems': systems, 'local_minus_api_pp': {
        metric: 100 * (systems['local'][metric] - systems['whisper_api'][metric]) for metric in ['wer', 'cer']}}


def bootstrap_group(rows, video_ids, weights, settings):
    counts = video_counts(rows, video_ids)
    result = {'clips': len(rows), 'videos': len({r['video_id'] for r in rows}),
              'channel_clips': dict(Counter(r['channel'] for r in rows)),
              **point_estimate(counts.sum(axis=0)), 'interval_95_pp': None,
              'invalid_zero_denominator_draws': 0}
    if result['videos'] < settings['minimum_videos_for_interval']:
        result['interval_status'] = 'withheld_fewer_than_minimum_videos'
        return result
    sampled = (weights @ counts.reshape(len(video_ids), -1)).reshape(len(weights), 2, 4)
    valid = np.all(sampled[:, :, [1, 3]] > 0, axis=(1, 2))
    result['invalid_zero_denominator_draws'] = int((~valid).sum())
    if not valid.all():
        # Do not condition intervals on nonempty draws or silently draw replacements.
        result['interval_status'] = 'withheld_zero_denominator_draws'
        return result
    differences = np.column_stack([
        100 * (sampled[:, 0, e] / sampled[:, 0, d] - sampled[:, 1, e] / sampled[:, 1, d])
        for e, d in [(0, 1), (2, 3)]])
    result['interval_95_pp'] = {metric: np.percentile(differences[:, i], settings['percentiles'], method='linear').tolist()
                                 for i, metric in enumerate(['wer', 'cer'])}
    result['interval_status'] = 'exploratory_paired_percentile_interval'
    return result


def influence(rows, video_ids, channels):
    counts = video_counts(rows, video_ids)
    totals = counts.sum(axis=0)
    original = point_estimate(totals)['local_minus_api_pp']
    by_video = []
    for i, video in enumerate(video_ids):
        point = point_estimate(totals - counts[i])
        by_video.append({'removed_video': video, 'channel': channels[video],
                         'removed_clips': sum(r['video_id'] == video for r in rows),
                         'removed_reference_words': int(counts[i, 0, 1]),
                         'removed_word_edit_difference_local_minus_api': int(counts[i, 0, 0] - counts[i, 1, 0]),
                         **point, 'change_from_full_pp': {m: point['local_minus_api_pp'][m] - original[m] for m in original}})
    by_channel = {}
    for channel in sorted(set(channels.values())):
        kept = [i for i, v in enumerate(video_ids) if channels[v] != channel]
        by_channel[channel] = point_estimate(counts[kept].sum(axis=0))
    return {'leave_one_video_out': by_video, 'leave_one_channel_out': by_channel,
            'leave_one_video_out_range_pp': {m: [min(r['local_minus_api_pp'][m] for r in by_video),
                                                 max(r['local_minus_api_pp'][m] for r in by_video)] for m in original}}


def paired_clips(rows):
    result = {}
    for metric, errors, units in [('wer', 'word_errors', 'reference_words'), ('cer', 'character_errors', 'reference_characters')]:
        edits = [r['systems']['local'][errors] - r['systems']['whisper_api'][errors] for r in rows]
        differences = [100 * difference / r['systems']['local'][units] for r, difference in zip(rows, edits)]
        result[metric] = {'local_lower_error': sum(v < 0 for v in edits), 'tied': sum(v == 0 for v in edits),
                          'api_lower_error': sum(v > 0 for v in edits),
                          'difference_pp': {'min': min(differences), 'q25': float(np.percentile(differences, 25)),
                                            'median': float(np.median(differences)), 'mean': float(np.mean(differences)),
                                            'q75': float(np.percentile(differences, 75)), 'max': max(differences)}}
    return result


def plot_results(result):
    groups = {'Overall': result['overall'], **result['bands']}
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), sharey=True)
    labels = [f"{name} (n={g['clips']}, v={g['videos']})" for name, g in groups.items()]
    for ax, metric in zip(axes, ['wer', 'cer']):
        for i, group in enumerate(groups.values()):
            point = group['local_minus_api_pp'][metric]
            interval = group['interval_95_pp'][metric]
            ax.hlines(i, *interval, color='#1769aa', linewidth=2)
            ax.plot(point, i, 'o', color='#1769aa')
        ax.axvline(0, color='#667580', linestyle='--', linewidth=1)
        ax.set(xlabel=f'Local minus API corpus {metric.upper()} (percentage points)', yticks=range(len(labels)), yticklabels=labels)
        ax.grid(axis='x', alpha=.15)
    axes[0].invert_yaxis()
    fig.suptitle('2,000 paired video resamples within channels | exploratory 95% intervals\nNegative = lower local error; two observed channels limit generalization', fontsize=11)
    fig.tight_layout()
    for suffix in ['png', 'svg']:
        fig.savefig(ROOT / f'results/figures/paired_uncertainty_20261119.{suffix}', dpi=200, bbox_inches='tight')
    plt.close(fig)


def markdown_report(result):
    def table(groups):
        lines = ['| Group | Clips | Videos | WER difference (pp) | 95% interval | CER difference (pp) | 95% interval |',
                 '|---|---:|---:|---:|---|---:|---|']
        for name, group in groups.items():
            intervals = group['interval_95_pp']
            shown = {m: f"[{intervals[m][0]:+.2f}, {intervals[m][1]:+.2f}]" if intervals else 'Withheld' for m in ['wer', 'cer']}
            lines.append(f"| {name} | {group['clips']} | {group['videos']} | {group['local_minus_api_pp']['wer']:+.2f} | {shown['wer']} | {group['local_minus_api_pp']['cer']:+.2f} | {shown['cer']} |")
        return lines

    lines = ['# Paired system uncertainty — November 19, 2026', '',
             'The November 19 analysis is complete. Saved outputs only; no model loading, audio submission, credential access or paid API call.', '',
             '## Frozen method and sign', '',
             'Differences are **local minus API**, in percentage points. Negative means lower local error. Corpus scores sum edit counts and reference units before division; no mean-utterance substitute is used. WER is primary, CER secondary.', '',
             'The frozen protocol uses 2,000 source-video bootstrap draws, seed 42, with videos sampled with replacement separately within each channel. Each draw contains three Channel A video selections and nineteen Channel B selections; it may contain repeated videos and a varying number of clips. All clips belonging to a selected video receive the same multiplicity in both systems. The 2.5th/97.5th percentiles of the paired corpus differences form exploratory intervals.', '',
             'The same full-pool video draws are reused for bands/subsets, applying the group filter after assigning video multiplicities; videos with no group observations contribute zero. This preserves paired sampling and channel strata rather than independently redrawing each condition. There is no clip-level bootstrap, channel resampling, p-value, confirmatory significance decision or causal hosting claim.', '',
             'Groups with fewer than ten represented videos have no interval, following the frozen rule. A zero-denominator draw would withhold the interval rather than silently redrawing or dropping that draw. All reported interval groups have 2,000 valid draws.', '',
             '## Full pool and fixed CMI bands', '']
    lines += table({'Overall': result['overall'], **result['bands']})
    overall = result['overall']
    lines += ['', f"The overall local-minus-API WER difference is {overall['local_minus_api_pp']['wer']:+.2f} pp, with interval [{overall['interval_95_pp']['wer'][0]:+.2f}, {overall['interval_95_pp']['wer'][1]:+.2f}]. CER is {overall['local_minus_api_pp']['cer']:+.2f} pp, with interval [{overall['interval_95_pp']['cer'][0]:+.2f}, {overall['interval_95_pp']['cer'][1]:+.2f}]. Both overall intervals lie below zero under this conditional resampling design. That supports the observed local advantage on this fixed pool; it is not a claim about every speaker, future provider run or deployment.", '',
              'The three lower-CMI WER intervals lie below zero, while both higher-CMI WER intervals include zero. Their larger observed local advantages are accompanied by wider uncertainty. Separate band intervals do not establish different degradation slopes or equivalence in bands whose intervals span zero.']
    lines += ['', '![Paired uncertainty](../results/figures/paired_uncertainty_20261119.png)', '',
              'These intervals describe source-video resampling conditional on the two observed channels and fixed silver labels. They do not quantify provider rerun variability, annotation uncertainty or generalization to independent Nepali speakers/channels. Band intervals are separate exploratory summaries, not simultaneous intervals or a formal test that degradation slopes differ.', '',
              '## Paired clip descriptions', '',
              '| Metric | Local lower error | Tie | API lower error | Median paired difference (pp) | Mean paired difference (pp) |',
              '|---|---:|---:|---:|---:|---:|']
    for metric, values in result['paired_clip_descriptions'].items():
        lines.append(f"| {metric.upper()} | {values['local_lower_error']} | {values['tied']} | {values['api_lower_error']} | {values['difference_pp']['median']:+.2f} | {values['difference_pp']['mean']:+.2f} |")
    lines += ['', 'Each clip has the same reference denominator for both systems. Ties are exact equal edit counts. These clip summaries weight clips equally and are distinct from the reference-length-weighted corpus gap; no independence-based test is applied.', '',
              '## Channel and duration context', '']
    lines += table({result['channel_aliases'][c]: g for c, g in result['channels'].items()})
    lines += ['', 'Channel A has three videos, so its interval is withheld even though it contributes 608 clips. Channel B has nineteen. Channels represent source IDs, not verified individual speakers. Duration-group differences below are descriptive only; cutpoints are 8.608, 9.872 and 11.552 seconds, with ties in the lower group.', '',
              '| Duration group | Clips | Videos | Local-minus-API WER (pp) | CER (pp) |', '|---|---:|---:|---:|---:|']
    for key, group in result['duration_context']['groups'].items():
        delta = {m: 100 * (group['systems']['local'][m] - group['systems']['whisper_api'][m]) for m in ['wer', 'cer']}
        lines.append(f"| {key} | {group['clips']} | {group['videos']} | {delta['wer']:+.2f} | {delta['cer']:+.2f} |")
    lines += ['', '## Video influence and source removal', '',
              'Leave-one-video-out is an additional descriptive influence diagnostic, not a confidence interval, exclusion rule or replacement benchmark. Every planned clip remains in the headline result.', '',
              '| Removed source video | Clips removed | WER difference after removal (pp) | CER difference after removal (pp) | WER change from full (pp) |',
              '|---|---:|---:|---:|---:|']
    for row in result['influence']['leave_one_video_out']:
        lines.append(f"| {row['removed_video']} | {row['removed_clips']} | {row['local_minus_api_pp']['wer']:+.2f} | {row['local_minus_api_pp']['cer']:+.2f} | {row['change_from_full_pp']['wer']:+.2f} |")
    lines += ['', 'Remaining-corpus differences after removing each whole channel:', '']
    for channel, point in result['influence']['leave_one_channel_out'].items():
        lines.append(f"- Remove {result['channel_aliases'][channel]}: WER {point['local_minus_api_pp']['wer']:+.2f} pp; CER {point['local_minus_api_pp']['cer']:+.2f} pp.")
    ranges = result['influence']['leave_one_video_out_range_pp']
    lines += ['', f"Across all 22 single-video removals, WER gaps range {ranges['wer'][0]:+.2f} to {ranges['wer'][1]:+.2f} pp; CER gaps range {ranges['cer'][0]:+.2f} to {ranges['cer'][1]:+.2f} pp. This tests sensitivity to one observed video, not unmeasured confounding or unseen channels.", '',
              'No single-video removal reverses the observed overall local advantage, and the point-estimate direction is also retained after removing either entire channel. This does not rule out joint influence of several videos or weak generalization to unseen sources. The longest duration quartile favors the API slightly on CER even though local has lower overall CER; the advantage is not universal across every descriptive group.', '',
              '## Same-50 reference and lexical-CMI sensitivity', '']
    lines += table({condition: group['overall'] for condition, group in result['audit_sensitivity'].items()})
    lines += ['', 'Each condition uses the same 50 fixed hypotheses; published versus corrected references/CMI are separate. Eighteen represented videos permit an overall exploratory interval, but every audit band has fewer than ten videos and its interval is withheld. JSON records all audit-band points, counts and reasons. These balanced single-reviewer results are not population representative and cannot replace the full pool.', '',
              'The audit-subset WER point estimate favors the API, but both reference-version intervals span zero widely. This subset does not establish a dependable opposite ranking; reference corrections leave the broad uncertainty and point direction largely unchanged.', '',
              '## Interpretation and remaining work', '',
              'The previously measured CMI–WER associations remain descriptive and near zero; this bootstrap targets corpus system differences, not Spearman uncertainty or a causal CMI effect. Channel/duration/influence checks can identify sensitivity, but cannot establish why recognition or script errors occurred. Listening to the ten preselected examples remains necessary before assigning speech-level error categories.', '',
              'The configured systems differ in decoding/runtime and unknown provider internals. Silver-label and script-derived CMI uncertainty remain outside these intervals. Source-video clustering is an improvement over treating all clips as independent, but two channels are still a major limitation.', '',
              'Next scheduled work: incorporate this analysis into the research-report draft on November 20; complete bounded listening examples November 21; reproduction/release checks November 22–24. The original November 16 PDF remains a dated v0.1 draft until revised.', '',
              '## Reproduction and provenance', '', '```powershell', '.\\.venv\\Scripts\\python.exe src/analyze_uncertainty.py', '```', '',
              'Install the existing `requirements-analysis.txt` in the project environment. JSON output: `results/metrics/paired_uncertainty_20261119.json`; figure PNG/SVG: `results/figures/paired_uncertainty_20261119.*`. JSON includes ordered video IDs, every draw multiplicity, source hashes, package versions, paired corpus points/intervals, audit bands and all 22 influence checks. All frozen inputs/predictions remain unchanged. The protocol/config are read and hash-validated before analysis; the overall totals are checked against both independent verifications.', '']
    return '\n'.join(lines)


def main():
    selection, audit, manifest, predictions, checksums = load_verified_inputs()
    protocol = json.loads((ROOT / manifest['protocol_config']).read_text(encoding='utf-8'))
    settings = protocol['analysis']['bootstrap']
    expected = {'resample': 'source videos within each channel; same sampled clips for both systems',
                'replicates': 2000, 'seed': 42, 'percentiles': [2.5, 97.5], 'minimum_videos_for_interval': 10}
    if settings != expected or protocol['analysis']['cmi_bands'] != BANDS:
        raise ValueError('Frozen uncertainty settings differ.')
    protocol_bytes = (ROOT / protocol['protocol_document']).read_bytes()
    if hashlib.sha256(protocol_bytes).hexdigest() != protocol['protocol_document_sha256']:
        raise ValueError('Frozen protocol document hash differs.')
    checksums['protocol_document'] = hashlib.sha256(protocol_bytes).hexdigest()
    rows = build_rows(manifest, predictions)
    video_ids, channels, weights = video_design(rows, settings)
    if len(rows) != 1198 or len(video_ids) != 22 or sorted(Counter(channels.values()).values()) != [3, 19]:
        raise ValueError('Frozen video/channel population differs.')
    overall = bootstrap_group(rows, video_ids, weights, settings)
    for system in SYSTEMS:
        verified = json.loads((ROOT / f'results/metrics/test_cs_benchmark_20261112_{system}_verified.json').read_text(encoding='utf-8'))
        point = overall['systems'][system]
        if any(point[k] != verified['independent_edit_counts'][k] for k in COUNT_KEYS) or any(
                not math.isclose(point[m], verified['independent_scores'][m], abs_tol=1e-12) for m in ['wer', 'cer']):
            raise ValueError('Corpus counts differ from verified predictions.')
    comparison = compare_subset(selection['clips'], audit['reviews'], predictions)
    result = {'computed_on': '2026-11-19', 'inference_requests': 0, 'frozen_inputs_modified': False,
              'source_sha256': checksums, 'packages': {p: version(p) for p in ['numpy', 'scipy', 'matplotlib', 'jiwer']},
              'bootstrap_settings': settings, 'difference_sign': 'local minus API; negative means lower local error',
              'interval_scope': 'Exploratory video-resampling uncertainty conditional on two observed channels and fixed silver references; not causal or confirmatory.',
              'video_ids': video_ids, 'video_channel': channels, 'draw_video_multiplicities': weights.tolist(),
              'overall': overall, 'bands': {band: bootstrap_group([r for r in rows if cmi_band(r['cmi']) == band], video_ids, weights, settings) for band in BANDS},
              'channel_aliases': {c: f'Channel {chr(65+i)}' for i, c in enumerate(sorted(set(channels.values())))},
              'channels': {c: bootstrap_group([r for r in rows if r['channel'] == c], video_ids, weights, settings) for c in sorted(set(channels.values()))},
              'paired_clip_descriptions': paired_clips(rows), 'duration_context': duration_groups(rows),
              'continuous_associations': summarize(rows)['spearman'], 'influence': influence(rows, video_ids, channels), 'audit_sensitivity': {}}
    for condition in ['published', 'corrected']:
        subset = audit_rows(comparison, rows, condition)
        result['audit_sensitivity'][condition] = {
            'overall': bootstrap_group(subset, video_ids, weights, settings),
            'bands': {band: bootstrap_group([r for r in subset if cmi_band(r['cmi']) == band], video_ids, weights, settings) for band in BANDS}}
    if sum(g['clips'] for g in result['bands'].values()) != 1198:
        raise ValueError('Band coverage differs.')
    json.dumps(result, allow_nan=False)
    plot_results(result)
    save_state(ROOT / 'results/metrics/paired_uncertainty_20261119.json', result)
    (ROOT / 'reports/paired_uncertainty_20261119.md').write_text(markdown_report(result), encoding='utf-8')
    print(json.dumps({key: result[key] for key in ['overall', 'paired_clip_descriptions', 'bands']}, indent=2))


if __name__ == '__main__':
    main()
