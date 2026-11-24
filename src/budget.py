"""Recompute API budget from clip durations and dated rates, with no API calls."""

from decimal import Decimal, ROUND_CEILING
import hashlib
import json
from pathlib import Path


def estimate_budget(durations_s, rates, reserve_fraction='0.20', conditions=1):
    if isinstance(conditions, bool) or not isinstance(conditions, int) or conditions < 1:
        raise ValueError('Conditions must be a positive integer.')
    reserve = Decimal(str(reserve_fraction))
    if not reserve.is_finite() or reserve < 0:
        raise ValueError('Reserve must be finite and nonnegative.')
    durations = []
    for value in durations_s:
        if isinstance(value, bool):
            raise ValueError('Duration must be a finite positive number.')
        duration = Decimal(str(value))
        if not duration.is_finite() or duration <= 0:
            raise ValueError('Duration must be a finite positive number.')
        durations.append(duration)
    if not durations or not rates:
        raise ValueError('Provide clips and at least one model rate.')
    raw_minutes = sum(durations) / 60
    rounded_minutes = sum(d.to_integral_value(rounding=ROUND_CEILING) for d in durations) / 60
    model_costs, total = {}, Decimal(0)
    for model, value in rates.items():
        rate = Decimal(str(value))
        if not rate.is_finite() or rate < 0:
            raise ValueError('Rate must be finite and nonnegative.')
        cost = rounded_minutes * rate * conditions
        total += cost
        model_costs[model] = {
            'usd_per_minute': str(rate), 'nominal_duration_cost_usd': str(raw_minutes * rate * conditions),
            'rounded_duration_cost_usd': str(cost),
        }
    return {
        'clips': len(durations), 'conditions_per_model': conditions,
        'requests_all_models': len(durations) * len(rates) * conditions,
        'audio_minutes_once': float(raw_minutes), 'planning_billable_minutes_per_model_per_condition': float(rounded_minutes),
        'by_model': model_costs, 'rounded_duration_total_usd': str(total),
        'reserve_fraction': str(reserve), 'with_reserve_usd': str(total * (1 + reserve)),
        'planning_amount_rounded_up_usd': str((total * (1 + reserve)).quantize(Decimal('.01'), rounding=ROUND_CEILING)),
    }


def cmi_band(value):
    if value is None or isinstance(value, bool):
        return 'invalid_or_missing'
    value = Decimal(str(value))
    if not value.is_finite() or not 0 <= value <= 50:
        return 'invalid_or_missing'
    for upper, label in [(10, '[0,10]'), (20, '(10,20]'), (30, '(20,30]'), (40, '(30,40]'), (50, '(40,50]')]:
        if value <= upper:
            return label


def main():
    root = Path(__file__).resolve().parents[1]
    metadata_path = root / 'data/manifests/budget_metadata_20261022.json'
    inventory = json.loads(metadata_path.read_text(encoding='utf-8'))
    pricing = json.loads((root / 'configs/api_prices_20261022.json').read_text(encoding='utf-8'))
    rows = [row for shard in inventory['shards'] for row in shard['rows']]
    summaries = {}
    for split in ['train', 'validation', 'test']:
        split_rows = [row for row in rows if row['split'] == split]
        cs_rows = [row for row in split_rows if row['speech_type'] == 'cs']
        bands = {}
        for row in cs_rows:
            band = cmi_band(row['cmi'])
            bands[band] = bands.get(band, 0) + 1
        summaries[split] = {'all_clips': len(split_rows), 'cs_clips': len(cs_rows),
                            'cs_audio_minutes': sum(row['duration_s'] for row in cs_rows) / 60, 'cs_cmi_band_counts': bands}
    scenarios = {}
    for name, selected in {
        'test_cs_candidates': [r for r in rows if r['split'] == 'test' and r['speech_type'] == 'cs'],
        'all_test_candidates': [r for r in rows if r['split'] == 'test'],
        'all_splits_cs_comparison_only': [r for r in rows if r['speech_type'] == 'cs'],
    }.items():
        scenarios[name] = estimate_budget([r['duration_s'] for r in selected], pricing['usd_per_audio_minute'], pricing['reserve_fraction'], pricing['request_conditions_per_model'])
    report = {'as_of': pricing['checked_on'], 'purpose': 'Preliminary budget, not a frozen evaluation manifest.',
              'dataset_id': inventory['dataset_id'], 'dataset_revision': inventory['revision'],
              'metadata_file': str(metadata_path.relative_to(root)).replace('\\', '/'),
              'metadata_sha256': hashlib.sha256(metadata_path.read_bytes()).hexdigest(),
              'metadata_bytes_retrieved': sum(s['metadata_bytes_retrieved'] for s in inventory['shards']),
              'pricing': pricing, 'split_inventory': summaries, 'scenarios': scenarios,
              'limitations': ['Metadata durations have not been independently checked against decoded audio.',
                              'Test candidates still require provenance, duplicate, audio and reference checks; final eligible counts may shrink.',
                              'All-splits scenario is a cost comparison, not the intended research evaluation.',
                              'Reserve is a planning allowance, not a guaranteed upper bound; extra runs and language settings add cost.']}
    target = root / 'results/metrics/api_budget_20261022.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({'split_inventory': summaries, 'scenarios': scenarios}, indent=2))


if __name__ == '__main__':
    main()
