"""Frozen-band and descriptive continuous CMI analysis; saved outputs only."""
from collections import Counter
from importlib.metadata import version
import json
import math
import os

from check_local_environment import ROOT
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.cache/matplotlib'))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import spearmanr

from budget import cmi_band
from compare_audited_references import aggregate, compare_subset, load_verified_inputs, text_scores
from local_whisper_pilot import save_state
from prepare_validation_check import BANDS

SYSTEMS = {'local': 'Local Large V2', 'whisper_api': 'Whisper API'}
COLORS = {'local': '#1769aa', 'whisper_api': '#d66a13'}


def rho(x, y):
    if len(x) != len(y) or not all(math.isfinite(v) for v in [*x, *y]):
        raise ValueError('Spearman inputs must be paired finite values.')
    if len(x) < 3 or len(set(x)) < 2 or len(set(y)) < 2:
        return None
    return float(spearmanr(x, y).statistic)


def describe(values):
    return {'min': min(values), 'median': float(np.median(values)),
            'mean': float(np.mean(values)), 'max': max(values)} if values else None


def summarize(rows):
    result = {'clips': len(rows), 'videos': len({r['video_id'] for r in rows}),
              'channels': dict(Counter(r['channel'] for r in rows)),
              'cmi': describe([r['cmi'] for r in rows]),
              'duration_s': describe([r['duration_s'] for r in rows]),
              'reference_words': describe([r['systems']['local']['reference_words'] for r in rows]),
              'systems': {s: aggregate([r['systems'][s] for r in rows]) if rows else None for s in SYSTEMS}}
    cmi = [r['cmi'] for r in rows]
    associations = {f'cmi_vs_{s}_{metric}': rho(cmi, [r['systems'][s][metric] for r in rows])
                    for s in SYSTEMS for metric in ['wer', 'cer']}
    associations.update(cmi_vs_local_minus_api_wer=rho(cmi, [r['systems']['local']['wer'] - r['systems']['whisper_api']['wer'] for r in rows]),
                        cmi_vs_duration=rho(cmi, [r['duration_s'] for r in rows]),
                        cmi_vs_reference_words=rho(cmi, [r['systems']['local']['reference_words'] for r in rows]))
    associations.update({f'duration_vs_{s}_wer': rho([r['duration_s'] for r in rows], [r['systems'][s]['wer'] for r in rows]) for s in SYSTEMS})
    result['spearman'] = associations
    return result


def bands(rows):
    groups = {band: [r for r in rows if cmi_band(r['cmi']) == band] for band in BANDS}
    if sum(map(len, groups.values())) != len(rows):
        raise ValueError('CMI band coverage differs.')
    return {key: summarize(group) for key, group in groups.items()}


def duration_groups(rows):
    cuts = np.quantile([r['duration_s'] for r in rows], [.25, .5, .75]).tolist()
    groups = {f'Q{i + 1}': [] for i in range(4)}
    for row in rows:
        groups[f"Q{int(np.searchsorted(cuts, row['duration_s'], side='left')) + 1}"].append(row)
    return {'cutpoints_s': cuts, 'rule': 'Empirical duration quartiles, ties in lower group; empty groups retained.',
            'groups': {key: summarize(group) for key, group in groups.items()}}


def build_rows(manifest, predictions):
    rows = []
    for entry in manifest['clips']:
        identity = entry['identity']
        key = identity['clip_id']
        scores = {}
        for system in SYSTEMS:
            saved = predictions[system][key]
            if saved.get('status') != 'received' or not isinstance(saved.get('hypothesis'), str):
                raise ValueError(f'Missing successful output: {system} {key}')
            scores[system] = text_scores(identity['transcription'], saved['hypothesis'])
        rows.append({'clip_id': key, 'video_id': identity['video_id'], 'channel': identity['speaker_id'],
                     'cmi': identity['cmi'], 'duration_s': identity['duration_s'], 'systems': scores})
    return rows


def audit_rows(comparison, full_rows, condition):
    by_id = {r['clip_id']: r for r in full_rows}
    return [{**by_id[r['clip_id']], 'cmi': r['published_cmi'] if condition == 'published' else r['audited_cmi'],
             'systems': {s: r['systems'][s][condition] for s in SYSTEMS}} for r in comparison['per_clip']]


def rate(summary, system, metric='wer'):
    return 100 * summary['systems'][system][metric] if summary['clips'] else float('nan')


def figures(result):
    folder = ROOT / 'results/figures'
    folder.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})

    def save(fig, name):
        fig.tight_layout()
        for suffix in ['png', 'svg']:
            fig.savefig(folder / f'{name}.{suffix}', dpi=200, bbox_inches='tight')
        plt.close(fig)

    x = np.arange(len(BANDS))
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
    counts = [result['bands'][b]['clips'] for b in BANDS]
    axes[0].bar(x, counts, color='#65768a')
    axes[0].bar_label(axes[0].containers[0], padding=3)
    axes[0].set(title='Published CMI distribution', ylabel='Clips', ylim=(0, max(counts) * 1.15))
    for ax, metric in zip(axes[1:], ['wer', 'cer']):
        for s, label in SYSTEMS.items():
            ax.plot(x, [rate(result['bands'][b], s, metric) for b in BANDS], 'o-', label=label, color=COLORS[s])
        ax.set(title=f'Corpus {metric.upper()} by fixed band', ylabel=f'{metric.upper()} (%)')
        ax.legend()
    for ax in axes:
        ax.set_xticks(x, BANDS, rotation=20)
        ax.set_xlabel('Published reference CMI (0–50)')
    fig.suptitle('1,198 paired CS clips • published silver references • descriptive, no intervals', y=1.04)
    save(fig, 'cmi_band_error_rates_20261116')

    rows = result['per_clip']
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)
    for ax, (s, label) in zip(axes, SYSTEMS.items()):
        for channel, alias in result['channel_aliases'].items():
            subset = [r for r in rows if r['channel'] == channel]
            ax.scatter([r['cmi'] for r in subset], [100 * r['systems'][s]['wer'] for r in subset], s=10, alpha=.4, label=alias, rasterized=True)
        correlation = result['overall']['spearman'][f'cmi_vs_{s}_wer']
        ax.set(title=f'{label} • Spearman ρ = {correlation:+.3f}', xlabel='Published reference CMI (0–50)', xlim=(-1, 51))
        ax.set_yscale('symlog', linthresh=100)
        ax.legend()
    axes[0].set_ylabel('Utterance WER (%) • linear to 100, log above')
    fig.suptitle('All 1,198 observations retained; insertions allow WER above 100%')
    save(fig, 'cmi_continuous_wer_20261116')

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for column, (channel, alias) in enumerate(result['channel_aliases'].items()):
        summary = result['channels'][channel]
        axes[0, column].bar(x, [summary['bands'][b]['clips'] for b in BANDS], color='#65768a')
        axes[0, column].bar_label(axes[0, column].containers[0], padding=3)
        axes[0, column].set(title=f"{alias} • {summary['overall']['clips']} clips", ylabel='Clips')
        for s, label in SYSTEMS.items():
            axes[1, column].plot(x, [rate(summary['bands'][b], s) for b in BANDS], 'o-', label=label, color=COLORS[s])
        axes[1, column].set(ylabel='Corpus WER (%)')
        axes[1, column].legend()
    for ax in axes.flat:
        ax.set_xticks(x, BANDS, rotation=20)
        ax.set_xlabel('Published reference CMI')
    fig.suptitle('Channel composition and within-channel band scores • descriptive')
    save(fig, 'cmi_by_channel_20261116')

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
    for channel, alias in result['channel_aliases'].items():
        subset = [r for r in rows if r['channel'] == channel]
        axes[0].scatter([r['cmi'] for r in subset], [r['duration_s'] for r in subset], s=10, alpha=.4, label=alias, rasterized=True)
    axes[0].set(xlabel='Published reference CMI', ylabel='Audio duration (seconds)', title='CMI versus clip duration')
    axes[0].legend()
    groups = result['duration']['groups']
    for s, label in SYSTEMS.items():
        axes[1].plot(list(groups), [rate(g, s) for g in groups.values()], 'o-', color=COLORS[s], label=label)
    axes[1].set(xlabel='Duration quartile (ties in lower group)', ylabel='Corpus WER (%)', title='Length context; no confound adjustment')
    axes[1].legend()
    save(fig, 'cmi_duration_checks_20261116')


def report(result):
    def table(groups):
        lines = ['| Group | Clips | Videos | Words | Mean CMI | Local WER | API WER | Local CER | API CER |',
                 '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
        for label, group in groups.items():
            if not group['clips']:
                lines.append(f'| {label} | 0 | 0 | 0 | — | — | — | — | — |')
                continue
            values = [f'{rate(group, s, m):.2f}%' for m in ['wer', 'cer'] for s in SYSTEMS]
            lines.append(f"| {label} | {group['clips']} | {group['videos']} | {group['systems']['local']['reference_words']} | {group['cmi']['mean']:.2f} | " + ' | '.join(values) + ' |')
        return lines

    lines = ['# CMI analysis — November 16, 2026', '',
             'November 18 work completed early, using the frozen protocol and saved predictions only. No new transcription, network request or credential access.', '',
             '## Fixed published-CMI bands', '',
             'CMI measures bilingual balance (0–50), not switch frequency or simply the English percentage. Published CMI is based on source script labels. Scores retain mixed-script references and use the frozen normalization. Corpus WER/CER sum edit counts and divide by summed reference words/characters; they are not averages of utterance rates.', '']
    lines += table(result['bands'])
    lines += ['', '![Band results](../results/figures/cmi_band_error_rates_20261116.png)', '', '## Continuous descriptive associations', '',
              'Spearman uses per-clip rates, with tied ranks. Positive rho means higher values co-occur; it does not establish a causal mixing effect. Undefined correlations are recorded as null. No p-values, significance decisions or intervals are produced in this step.', '',
              '| Variables | Spearman rho |', '|---|---:|']
    for key, value in result['overall']['spearman'].items():
        lines.append(f"| {key} | {value:+.4f} |" if value is not None else f'| {key} | undefined |')
    lines += ['', 'For local-minus-API WER, a positive difference means more local error. The correlation of this difference is distinct from the difference between two corpus rates.', '',
              '![Continuous CMI](../results/figures/cmi_continuous_wer_20261116.png)', '', '## Channel and video composition', '',
              'The source speaker_id identifies a channel, not an independently identified speaker. Two channels and 22 videos limit generalization. Descriptive conditioning does not remove confounding.', '']
    lines += table({alias: result['channels'][key]['overall'] for key, alias in result['channel_aliases'].items()})
    lines += ['', '| Channel | CMI–local WER rho | CMI–API WER rho |', '|---|---:|---:|']
    for key, alias in result['channel_aliases'].items():
        associations = result['channels'][key]['overall']['spearman']
        lines.append(f"| {alias} | {associations['cmi_vs_local_wer']:+.4f} | {associations['cmi_vs_whisper_api_wer']:+.4f} |")
    lines += ['', '| Channel | CMI–local CER rho | CMI–API CER rho |', '|---|---:|---:|']
    for key, alias in result['channel_aliases'].items():
        associations = result['channels'][key]['overall']['spearman']
        lines.append(f"| {alias} | {associations['cmi_vs_local_cer']:+.4f} | {associations['cmi_vs_whisper_api_cer']:+.4f} |")
    lines += ['', 'Channel IDs: ' + '; '.join(f'`{alias}` = `{key}`' for key, alias in result['channel_aliases'].items()) + '.', '',
              '![Channel composition](../results/figures/cmi_by_channel_20261116.png)', '', 'Per-video summaries (not independent clip samples):', '']
    lines += table(result['videos'])
    lines += ['', '## Duration and reference length', '',
              f"Duration quartile cutpoints: {', '.join(f'{v:.3f}' for v in result['duration']['cutpoints_s'])} seconds. These are descriptive reporting groups, not frozen CMI bins. Ties go in the lower group; no clip is discarded.", '']
    lines += table(result['duration']['groups'])
    lines += ['', 'Full min/median/mean/max CMI, duration and reference-word distributions are in the JSON for every band, channel, video and duration group.', '',
              '![Duration checks](../results/figures/cmi_duration_checks_20261116.png)', '', '## Same-50 reference and lexical-CMI sensitivity', '',
              'This balanced diagnostic subset is not population-representative. Published condition uses source CMI/published references; corrected condition uses human lexical CMI/corrected references. Both labels and reference definitions can change, while hypotheses remain fixed. This does not isolate the causal effect of either change. One reviewer checked script suggestions; these are operational references, not independent gold truth.', '']
    for condition, subset in result['audit_sensitivity'].items():
        lines += [f'### {condition.capitalize()} condition', ''] + table(subset['bands'])
        values = subset['overall']['spearman']
        lines += ['', f"CMI–WER rho: local {values['cmi_vs_local_wer']:+.4f}, API {values['cmi_vs_whisper_api_wer']:+.4f}; paired-difference rho {values['cmi_vs_local_minus_api_wer']:+.4f}.", '']
    lines += ['## Interpretation and next step', '',
              'The predeclared clip-level CMI–WER associations are near zero: local rho +0.0093, hosted +0.0109. The paired local-minus-API WER association is also near zero (−0.0204). These results do not support a clear monotonic word-error gradient over this pool; near-zero rho does not rule out nonlinear patterns or subgroup effects.', '',
              'Corpus WER by fixed band is mostly flat for local (90.22–92.86%). Hosted WER is nonmonotonic, with its highest rate in (40,50]: 106.73%, compared with 93.61% in [0,10]. WER above 100% is possible because insertions count. Weighted corpus band rates and clip-level rank correlations answer different questions, so these observations are compatible.', '',
              'Character errors show a clearer positive descriptive association: CMI–CER rho +0.2698 local and +0.2514 hosted; corpus CER rises across all five bands for both systems. The channels have different mean CMIs (16.85 versus 29.50), baseline errors and video coverage (3 versus 19 videos). This composition and the script-derived CMI warrant caution: higher CER is not proof that mixing itself caused the errors. High measured errors can reflect recognition and language/script/reference conventions; this step has not classified their causes.', '',
              'The CER pattern also varies by channel: Channel A rho +0.2891 local / +0.3048 hosted, versus Channel B +0.0452 / +0.0145. Thus the pooled character-error association is not uniform across sources. Duration has little pooled association with CMI (rho +0.0236); that descriptive check does not establish absence of confounding.', '',
              'The systems have different implementations, decoding and provider internals. This is a configured-system comparison and does not identify a causal effect of hosting. Published references are silver; the 50-clip audit does not validate every reference or source CMI.', '',
              'Paired video-cluster uncertainty remains the next scheduled task: 2,000 paired video resamples within channels, seed 42, with the frozen minimum-video rule. No confidence intervals or statistical superiority claims are made here. Error-example listening, final report and release also remain.', '',
              '## Reproduction', '', '```powershell', '.\\.venv\\Scripts\\python.exe -m pip install -r requirements-analysis.txt',
              '.\\.venv\\Scripts\\python.exe src/analyze_cmi.py', '```', '',
              'Results: `results/metrics/cmi_analysis_20261116.json`; four figures in both PNG and SVG under `results/figures/`. JSON includes all per-clip edit counts, grouping summaries, dependency versions and frozen-input checksums. Global counts are checked against independently verified runs before writing. Saved predictions, references and protocol are never edited.', '']
    return '\n'.join(lines)


def main():
    selection, audit, manifest, predictions, checksums = load_verified_inputs()
    protocol = json.loads((ROOT / manifest['protocol_config']).read_text(encoding='utf-8'))
    if protocol['analysis']['cmi_bands'] != BANDS:
        raise ValueError('Reporting bands differ from the frozen protocol.')
    rows = build_rows(manifest, predictions)
    overall = summarize(rows)
    for s in SYSTEMS:
        verified = json.loads((ROOT / f'results/metrics/test_cs_benchmark_20261112_{s}_verified.json').read_text(encoding='utf-8'))
        if overall['systems'][s] != {**verified['independent_edit_counts'], **verified['independent_scores']}:
            raise ValueError('Full-corpus counts/rates differ from independent verification.')
    grouped = bands(rows)
    if len(rows) != 1198 or [g['clips'] for g in grouped.values()] != [199, 360, 286, 230, 123]:
        raise ValueError('Frozen population or band counts differ.')
    channels = sorted({r['channel'] for r in rows})
    video_ids = sorted({r['video_id'] for r in rows})
    if len(channels) != 2 or len(video_ids) != 22:
        raise ValueError('Source channel/video population differs.')
    comparison = compare_subset(selection['clips'], audit['reviews'], predictions)
    result = {'computed_on': '2026-11-16', 'source_sha256': checksums, 'inference_requests': 0,
              'packages': {p: version(p) for p in ['numpy', 'scipy', 'matplotlib', 'jiwer']},
              'scope': 'Descriptive frozen-protocol CMI analysis; no p-values/intervals or causal claims.',
              'overall': overall, 'bands': grouped, 'per_clip': rows,
              'channel_aliases': {c: f'Channel {chr(65+i)}' for i, c in enumerate(channels)},
              'channels': {c: {'overall': summarize([r for r in rows if r['channel'] == c]),
                               'bands': bands([r for r in rows if r['channel'] == c])} for c in channels},
              'videos': {v: summarize([r for r in rows if r['video_id'] == v]) for v in video_ids},
              'duration': duration_groups(rows), 'audit_sensitivity': {}}
    for condition in ['published', 'corrected']:
        subset = audit_rows(comparison, rows, condition)
        result['audit_sensitivity'][condition] = {'overall': summarize(subset), 'bands': bands(subset)}
    # Every reporting partition must preserve the same edits and reference denominators.
    for partition in [grouped, result['videos'], result['duration']['groups'], {c: g['overall'] for c, g in result['channels'].items()}]:
        for s in SYSTEMS:
            combined = aggregate([g['systems'][s] for g in partition.values() if g['clips']])
            if combined != overall['systems'][s] or sum(g['clips'] for g in partition.values()) != len(rows):
                raise ValueError('Reporting partition loses or duplicates clips/edits.')
    # Reject nonfinite JSON before creating the output artifacts.
    json.dumps(result, allow_nan=False)
    figures(result)
    save_state(ROOT / 'results/metrics/cmi_analysis_20261116.json', result)
    (ROOT / 'reports/cmi_analysis_20261116.md').write_text(report(result), encoding='utf-8')
    print(json.dumps({'clips': len(rows), 'spearman': overall['spearman'],
                      'bands': {b: {s: g['systems'][s]['wer'] for s in SYSTEMS} for b, g in grouped.items()}}, indent=2))


if __name__ == '__main__':
    main()
