"""Independently score the specialist and compare saved systems; no inference/API."""
from datetime import datetime, timezone
import argparse
import html
import json
import math

from analyze_cmi import audit_rows, build_rows, plt, rho
from analyze_forced_nepali import load_forced
from analyze_uncertainty import bootstrap_group, video_design
from budget import cmi_band
from check_local_environment import ROOT
from compare_audited_references import (COUNTS, RATES, aggregate, compare_subset,
                                        load_verified_inputs, text_scores)
from local_whisper_pilot import save_state
from prepare_codemix_model import CONFIG, checksum
from prepare_validation_check import BANDS
from run_evaluation import read_manifest

STEM = 'codemix_turbo_comparison_20261127'
LABELS = {'automatic_local': 'Large V2 local, automatic', 'automatic_api': 'whisper-1 API, automatic',
          'forced_local': 'Large V2 local, forced Nepali', 'forced_api': 'whisper-1 API, forced Nepali'}


def verify_saved(manifest, state, metrics, config, config_sha, manifest_sha):
    """Reconstruct raw hypotheses and edit counts, independently of runner scoring."""
    spec = state['run_spec']
    if (spec != metrics['run_spec'] or spec['config'] != config
            or spec['experiment_config_sha256'] != config_sha or spec['manifest_sha256'] != manifest_sha
            or spec['dataset'] != manifest['dataset'] or spec['system'] != 'codemix_turbo'
            or spec['condition'] != 'forced_ne_specialist' or spec['packages'] != config['runtime_packages']
            or state.get('actual_device') != 'cuda' or state.get('actual_compute_type') != 'float16'
            or not metrics['summary']['complete']):
        raise ValueError('Specialist specification/coverage differs from frozen settings.')
    expected = {e['identity']['clip_id']: e for e in manifest['clips']}
    saved = {r['clip_id']: r for r in state['predictions']}
    scored = {r['clip_id']: r for r in metrics['per_clip']}
    if (set(expected) != set(saved) or set(saved) != set(scored)
            or len(saved) != len(state['predictions']) or len(scored) != len(metrics['per_clip'])
            or spec['manifest'] != [e['identity'] for e in manifest['clips']]):
        raise ValueError('Specialist clip coverage/order/uniqueness differs.')
    counts = {}
    for key, row in saved.items():
        if (row['status'] != 'received' or not isinstance(row.get('hypothesis'), str)
                or any(row.get(k) != v for k, v in expected[key]['identity'].items())
                or spec['payload_sha256'][key] != expected[key]['payload_sha256']):
            raise ValueError('Specialist saved identity/payload/status differs.')
        reconstructed = ' '.join(part['text'].strip() for part in row['response']['segments']).strip()
        options = row['response']['info']['transcription_options']
        if (row['hypothesis'] != reconstructed or row['response']['info']['language'] != 'ne'
                or options['beam_size'] != 1 or options['best_of'] != 1 or options['temperatures'] != [0.0]
                or options['condition_on_previous_text'] or not options['without_timestamps']
                or any(options[k] is not None for k in ['initial_prompt', 'hotwords', 'prefix'])
                or not math.isfinite(row['transcription_s']) or row['transcription_s'] <= 0):
            raise ValueError('Raw output/options/timing differ from the recorded specialist run.')
        counts[key] = text_scores(row['transcription'], reconstructed)
        if any(not math.isclose(counts[key][m], scored[key][m], abs_tol=1e-12) for m, _, _ in RATES):
            raise ValueError('Per-clip specialist metric differs from independently counted edits.')
    total = aggregate(list(counts.values()))
    if any(not math.isclose(total[m], metrics['summary'][m], abs_tol=1e-12) for m, _, _ in RATES):
        raise ValueError('Corpus specialist metric differs from independently counted edits.')
    return saved, counts, total


def paired_summary(rows, video_ids, weights, settings):
    if not rows:
        return {'clips': 0, 'videos': 0, 'interval_status': 'withheld_empty_group', 'interval_95_pp': None}
    result = bootstrap_group(rows, video_ids, weights, settings)
    return {'clips': result['clips'], 'videos': result['videos'], 'channel_clips': result['channel_clips'],
            'specialist': result['systems']['local'], 'baseline': result['systems']['whisper_api'],
            'specialist_minus_baseline_pp': result['local_minus_api_pp'],
            'interval_95_pp': result['interval_95_pp'], 'interval_status': result['interval_status'],
            'invalid_zero_denominator_draws': result['invalid_zero_denominator_draws'],
            'paired_clip_changes': {metric: {
                name: sum(test(r['systems']['local'][error] - r['systems']['whisper_api'][error]) for r in rows)
                for name, test in [('improved', lambda d: d < 0), ('tied', lambda d: d == 0), ('worsened', lambda d: d > 0)]}
                for metric, error in [('wer', 'word_errors'), ('cer', 'character_errors')]}}


def markdown_report(result):
    def interval(g, metric='wer'):
        v = g['interval_95_pp']
        return f'[{v[metric][0]:+.2f}, {v[metric][1]:+.2f}]' if v else 'Withheld'

    score = result['specialist_scores']
    lines = ['# Exploratory Nepali English code mix model results', '',
             '**Sanskar Ananta Tiwari · November 27, 2026 · Separate from the published report**', '',
             f"The new fine-tuned Large V3 Turbo completed all **{result['clips']:,} benchmark clips**. "
             f"Its normalized corpus WER is **{100*score['wer']:.2f}%** and CER **{100*score['cer']:.2f}%**. "
             'Every saved hypothesis and score passed independent reconstruction/edit-count verification. '
             'The original local/API outputs were reused, without new API calls.', '',
             '**Interpretation:** these scores describe agreement with our fixed mixed-script references. '
             'The model was trained partly on the same source dataset; exact training overlap remains unknown. '
             'A large observed improvement is not proof of performance on unseen clips or an isolated fine-tuning effect.', '',
             '## Systems and overall scores', '',
             '| System | WER | CER | Word edits | Reference words |', '|---|---:|---:|---:|---:|',
             f"| Code-mix specialist, forced Nepali | {100*score['wer']:.2f}% | {100*score['cer']:.2f}% | {score['word_errors']} | {score['reference_words']} |"]
    for key, label in LABELS.items():
        s = result['comparisons'][key]['baseline']
        lines.append(f"| {label} | {100*s['wer']:.2f}% | {100*s['cer']:.2f}% | {s['word_errors']} | {s['reference_words']} |")
    lines += ['', 'WER/CER use the original normalization and sum edits before division; they are not averages of utterance rates. '
              'WER is not semantic accuracy, and one minus WER should not be presented as the percentage of correctly understood speech.', '',
              '## Paired changes and uncertainty', '',
              'Differences are specialist minus baseline in percentage points; negative means lower specialist error. '
              'The existing method resamples source videos within each channel 2,000 times, seed 42, with paired outcomes kept together. '
              'Intervals are conditional on two observed channels, 22 videos and fixed references, not training-disjointness or annotation uncertainty.', '',
              '| Baseline | WER change (pp) | Exploratory 95% interval | CER change (pp) | Exploratory 95% interval |',
              '|---|---:|---|---:|---|']
    for key, label in LABELS.items():
        g = result['comparisons'][key]
        lines.append(f"| {label} | {g['specialist_minus_baseline_pp']['wer']:+.2f} | {interval(g)} | {g['specialist_minus_baseline_pp']['cer']:+.2f} | {interval(g,'cer')} |")
    lines += ['', 'The word "significant" should be separated into effect size and uncertainty. '
              'A difference whose interval lies below zero is a consistent observed advantage under this conditional resampling design; '
              'it does not remove training-overlap, reference-convention, model-version or implementation confounding.', '',
              '## Original CMI groups', '',
              '| Published CMI | Clips | Specialist WER | Specialist CER | Local automatic WER | API automatic WER |',
              '|---|---:|---:|---:|---:|---:|']
    for band, group in result['bands'].items():
        s = group['specialist']
        lines.append(f"| {band} | {group['clips']} | {100*s['wer']:.2f}% | {100*s['cer']:.2f}% | {100*group['comparisons']['automatic_local']['baseline']['wer']:.2f}% | {100*group['comparisons']['automatic_api']['baseline']['wer']:.2f}% |")
    lines += ['', '![CMI band scores](../results/figures/codemix_turbo_cmi_20261127.png)', '',
              f"Descriptive clip-level Spearman association with published CMI: specialist WER {result['spearman']['cmi_vs_wer']:+.4f}; "
              f"CER {result['spearman']['cmi_vs_cer']:+.4f}. CMI is a balance measure, not switch frequency; these associations do not establish causation. "
              'Band-level paired intervals, channels and the full source-video draws are retained in the JSON. '
              'No clips are removed because their scores are high.', '',
              '## Same 50 human-reviewed references', '',
              'The separately audited subset is balanced across original CMI bands and is not population representative. '
              'Each comparison uses the same reference version for both systems; corrected references can change denominators.', '',
              '| Reference version | Specialist WER | Specialist CER | Local automatic WER | API automatic WER |',
              '|---|---:|---:|---:|---:|']
    for version, subset in result['audit_sensitivity'].items():
        first = subset['automatic_local']
        lines.append(f"| {version} | {100*first['specialist']['wer']:.2f}% | {100*first['specialist']['cer']:.2f}% | {100*first['baseline']['wer']:.2f}% | {100*subset['automatic_api']['baseline']['wer']:.2f}% |")
    lines += ['', '## Execution and limits', '',
              f"- Checkpoint: `{result['model_id']}`, pinned revision `{result['model_revision']}`.",
              '- Public BF16 safetensors were checksum-verified and converted to CTranslate2 FP16. Inference used faster-whisper 1.2.1 / CTranslate2 4.8.5 on the laptop GPU, batch one, beam one, temperature zero, Nepali specified, no VAD, transcript prompt or previous-clip context. This is a converted implementation, not a measured equivalence claim with the authors\' Transformers pipeline.',
              f"- Summed generation time: {result['timing']['generation_s']/60:.2f} minutes for {result['timing']['audio_s']/60:.2f} audio minutes; real-time factor {result['timing']['real_time_factor']:.3f}. This excludes setup, downloading, conversion, model loading, scoring and saving overhead.",
              f"- Largest whole-device post-transcription memory snapshot: {result['timing']['largest_observed_device_memory_mib']} MiB. Snapshots do not measure exact model peak memory.",
              '- The source checkpoint uses different training and output conventions from general Large V2, including number/symbol spelling. Primary references were not rewritten for the new model. Raw scores and reviewed-reference sensitivity remain separate.',
              '- The original Large V3 Turbo base was not rerun in this experiment. Differences from Large V2/whisper-1 cannot isolate fine-tuning from base-model, decoding or service differences.',
              '- Training included saileshbro/nepali-cs-asr; neither the public model files nor its card establish exclusion of these exact 1,198 clips. Do not describe this as a confirmed unseen-data benchmark.',
              '- Model source and attribution: [AI Lab Pvt. Ltd. pinned model card](https://huggingface.co/ailabpvtltd/whisper-large-v3-turbo-nepali-english-codemix-asr/blob/8eff5c489628694a9f3ff2a02f3225ccfd6c6046/README.md), released under CC BY-NC 4.0. See the separate [feasibility study](codemix_model_feasibility_20261124.md) for the training-data disclosure and local-resource checks.',
              '- No new listening judgments, tolerant word equivalences or semantic-accuracy labels were invented. The ten-example text comparison is a review aid, not an independent listening audit.',
              '- No OpenAI credits were spent by these local runs. The original research PDF, frozen baselines and GitHub publication remain unchanged.', '',
              'The [full JSON](../results/metrics/codemix_turbo_comparison_20261127.json) records source hashes, '
              'edit counts, raw scores, all paired comparisons and uncertainty. The [ten-example comparison](codemix_turbo_examples_20261127.md) '
              'shows the existing references and saved outputs without changing the prior annotations.', '',
              '```powershell', '.\\.venv\\Scripts\\python.exe src/run_codemix_experiment.py --split test --execute',
              '.\\.cache\\reproduction-20261124\\env\\Scripts\\python.exe src/analyze_codemix_experiment.py', '```', '',
              'The runner resumes successful saved clips. Do not delete checkpoints to bypass an unresolved attempt. '
              'The analysis performs no model inference or network calls; it independently rechecks the cached WAV identities.', '']
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--saved-text-only', action='store_true',
                        help='Replay saved responses without cached WAVs; preserve the original audio-verification receipt.')
    args = parser.parse_args(argv)
    config = json.loads(CONFIG.read_bytes())
    for receipt in config['sources'].values():
        if checksum(ROOT / receipt['path']) != receipt['sha256']:
            raise ValueError('Frozen exploratory source changed.')
    selection, audit, manifest, automatic, sources = load_verified_inputs()
    _, forced, forced_sources, _ = load_forced(manifest)
    source_manifest = ROOT / config['sources']['test_manifest']['path']
    if not args.saved_text_only:
        _, clips = read_manifest(source_manifest)
        del clips
    path = ROOT / 'results/predictions/test_codemix_turbo_20261127.json'
    metrics_path = ROOT / 'results/metrics' / path.name
    state = json.loads(path.read_bytes())
    metrics = json.loads(metrics_path.read_bytes())
    saved, counts, total = verify_saved(manifest, state, metrics, config, checksum(CONFIG), checksum(source_manifest))
    baselines = {'automatic_local': automatic['local'], 'automatic_api': automatic['whisper_api'],
                 'forced_local': forced['local'], 'forced_api': forced['whisper_api']}
    pairs = {k: build_rows(manifest, {'local': saved, 'whisper_api': baseline}) for k, baseline in baselines.items()}
    settings = config['bootstrap']
    video_ids, channels, weights = video_design(pairs['automatic_local'], settings)
    if len(saved) != 1198 or len(video_ids) != 22:
        raise ValueError('Expected the complete fixed 1,198-clip benchmark.')
    group = lambda rows: paired_summary(rows, video_ids, weights, settings)
    comparisons = {k: group(rows) for k, rows in pairs.items()}
    result = {'computed_at_utc': datetime.now(timezone.utc).isoformat(), 'scope': config['purpose'],
              'model_id': config['model_id'], 'model_revision': config['model_revision'],
              'clips': len(saved), 'specialist_scores': total, 'comparisons': comparisons,
              'inference_requests_by_analysis': 0, 'paid_api_calls': 0, 'training_overlap': config['training_evaluation_overlap'],
              'source_sha256': {**sources, **forced_sources, 'experiment_config': checksum(CONFIG),
                                'specialist_predictions': checksum(path), 'specialist_metrics': checksum(metrics_path),
                                'analysis_code': checksum(ROOT / 'src/analyze_codemix_experiment.py')},
              'bootstrap_settings': settings, 'video_ids': video_ids, 'video_channels': channels,
              'draw_video_multiplicities': weights.tolist(),
              'bands': {}, 'channels': {channel: {k: group([r for r in rows if r['channel'] == channel])
                                                for k, rows in pairs.items()} for channel in sorted(set(channels.values()))},
              'spearman': {f'cmi_vs_{m}': rho([r['cmi'] for r in pairs['automatic_local']],
                                            [r['systems']['local'][m] for r in pairs['automatic_local']]) for m in ['wer', 'cer']},
              'audit_sensitivity': {},
              'timing': {'generation_s': sum(r['transcription_s'] for r in saved.values()),
                         'audio_s': sum(e['identity']['decoded_duration_s'] for e in manifest['clips']),
                         'largest_observed_device_memory_mib': max(r['gpu_after_transcription']['used_memory_mib'] for r in saved.values()),
                         'first_requested_at_utc': min(r['requested_at_utc'] for r in saved.values()),
                         'last_requested_at_utc': max(r['requested_at_utc'] for r in saved.values())},
              'per_clip': [{'clip_id': e['identity']['clip_id'], 'cmi': e['identity']['cmi'],
                            'specialist': counts[e['identity']['clip_id']]} for e in manifest['clips']]}
    result['timing']['real_time_factor'] = result['timing']['generation_s'] / result['timing']['audio_s']
    for band in BANDS:
        chosen = {k: [r for r in rows if cmi_band(r['cmi']) == band] for k, rows in pairs.items()}
        result['bands'][band] = {'clips': len(chosen['automatic_local']),
                                 'specialist': aggregate([r['systems']['local'] for r in chosen['automatic_local']]),
                                 'comparisons': {k: group(rows) for k, rows in chosen.items()}}
    for key, baseline in baselines.items():
        comparison = compare_subset(selection['clips'], audit['reviews'], {'local': saved, 'whisper_api': baseline})
        for reference in ['published', 'corrected']:
            result['audit_sensitivity'].setdefault(reference, {})[key] = group(audit_rows(comparison, pairs[key], reference))
    if sum(g['clips'] for g in result['bands'].values()) != 1198:
        raise ValueError('CMI coverage differs.')
    json.dumps(result, allow_nan=False)
    save_state(ROOT / f'results/metrics/{STEM}.json', result)
    verification = {'predictions_sha256': checksum(path), 'experiment_config_sha256': checksum(CONFIG),
                    'coverage': {'expected': 1198, 'received': 1198, 'complete': True},
                    'independent_edit_counts': {k: total[k] for k in COUNTS},
                    'independent_scores': {m: total[m] for m, _, _ in RATES},
                    'checks': 'All input WAV payloads/waveforms rechecked. Raw text reconstructed from segments; settings and every corpus/per-clip normalized/raw metric independently checked.',
                    'inference_requests': 0, 'training_overlap': config['training_evaluation_overlap']}
    verification_path = ROOT / 'results/metrics/test_codemix_turbo_20261127_verified.json'
    if args.saved_text_only:
        if json.loads(verification_path.read_bytes()) != verification:
            raise ValueError('Saved text counts/settings differ from the original audio-verified receipt.')
    else:
        save_state(verification_path, verification)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    for ax, metric in zip(axes, ['wer', 'cer']):
        ax.plot(range(5), [100*result['bands'][b]['specialist'][metric] for b in BANDS], 'o-', label='Code-mix specialist')
        for key, label in list(LABELS.items())[:2]:
            ax.plot(range(5), [100*result['bands'][b]['comparisons'][key]['baseline'][metric] for b in BANDS], 'o--', label=label)
        ax.set(xticks=range(5), xticklabels=BANDS, xlabel='Published reference CMI', ylabel=f'Corpus {metric.upper()} (%)')
        ax.tick_params(axis='x', rotation=15)
        ax.legend(fontsize=8)
        ax.grid(alpha=.15)
    fig.suptitle('1,198 identical clips; exploratory comparison\nSpecialist training overlap unknown; fixed mixed-script references', fontsize=11)
    fig.tight_layout()
    for ext in ['png', 'svg']:
        fig.savefig(ROOT / f'results/figures/codemix_turbo_cmi_20261127.{ext}', dpi=200, bbox_inches='tight')
    plt.close(fig)
    (ROOT / f'reports/{STEM}.md').write_text(markdown_report(result), encoding='utf-8')
    examples = json.loads((ROOT / 'data/annotations/error_examples_20261120.json').read_bytes())
    lines = ['# Ten existing examples with the new specialist output', '',
             'Same ten previously selected clips; no new listening judgments or reference edits. '
             'A text comparison alone cannot establish that the recognizer heard the correct spoken words.', '']
    for example in examples['reviews']:
        key = example['clip_id']
        lines += [f"## Example {example['number']}", '', f'Clip: `{key}`', '',
                  '**Published reference:** ' + html.escape(saved[key]['transcription']), '',
                  '**New specialist:** ' + html.escape(saved[key]['hypothesis']), '']
        for name, label in list(LABELS.items())[:2]:
            lines += [f'**{label}:** ' + html.escape(baselines[name][key]['hypothesis']), '']
    (ROOT / 'reports/codemix_turbo_examples_20261127.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({'clips': 1198, 'scores': total, 'comparisons': comparisons,
                      'spearman': result['spearman'], 'timing': result['timing']}, indent=2))


if __name__ == '__main__':
    main()
