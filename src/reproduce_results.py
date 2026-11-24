"""Replay saved-output analyses/tests/PDF in an isolated, network-blocked copy."""
import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ['audited_reference_comparison_20261116.json', 'cmi_analysis_20261116.json',
           'paired_uncertainty_20261119.json', 'variant_sensitivity_20261122.json']


def compare(actual, expected, path='result'):
    if type(actual) is not type(expected):
        raise ValueError(f'{path}: types differ')
    if isinstance(expected, dict):
        if actual.keys() != expected.keys():
            raise ValueError(f'{path}: fields differ')
        for key in expected:
            compare(actual[key], expected[key], f'{path}.{key}')
    elif isinstance(expected, list):
        if len(actual) != len(expected):
            raise ValueError(f'{path}: lengths differ')
        for i, (a, b) in enumerate(zip(actual, expected)):
            compare(a, b, f'{path}[{i}]')
    elif isinstance(expected, float):
        if not math.isclose(actual, expected, rel_tol=0, abs_tol=1e-12):
            raise ValueError(f'{path}: numerical values differ')
    elif actual != expected:
        raise ValueError(f'{path}: values differ')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'output/reproduction')
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    cache = ROOT / '.cache'
    cache.mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='reproduction-', dir=cache)).resolve()
    assert work.is_relative_to(cache.resolve())
    folders = ['src', 'tests', 'configs', 'data/annotations', 'data/manifests',
               'results/predictions', 'results/metrics', 'results/figures', 'reports',
               'notebooks', 'output/pdf']
    for name in folders:
        shutil.copytree(ROOT / name, work / name,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.tmp', '*.lock'))
    shutil.copyfile(ROOT / 'README.md', work / 'README.md')
    expected = {name: json.loads((ROOT / 'results/metrics' / name).read_bytes()) for name in RESULTS}
    protected = [p for directory in ['data/annotations', 'data/manifests', 'configs', 'results/predictions']
                 for p in (ROOT / directory).rglob('*') if p.is_file()]
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    original_hashes = {str(p.relative_to(ROOT)): digest(p) for p in protected}
    guard = work / '.network_guard'
    guard.mkdir()
    attempts = guard / 'attempts.jsonl'
    (guard / 'sitecustomize.py').write_text(
        "import json, os, socket\n"
        "def blocked(*args, **kwargs):\n"
        "    with open(os.environ['REPRO_NETWORK_LOG'], 'a', encoding='utf-8') as stream:\n"
        "        stream.write(json.dumps({'attempt_blocked': True})+'\\n')\n"
        "    raise RuntimeError('Network connections are disabled during saved-output reproduction')\n"
        "socket.socket.connect = blocked\nsocket.socket.connect_ex = blocked\n"
        "socket.create_connection = blocked\n", encoding='utf-8')
    env = {k: v for k, v in os.environ.items() if not any(
        marker in k.upper() for marker in ['API_KEY', 'ACCESS_TOKEN', 'AUTH_TOKEN', 'HF_TOKEN'])}
    env.update(PYTHONNOUSERSITE='1', PYTHONPATH=str(guard), PYTHONUTF8='1',
               HF_HUB_OFFLINE='1', HF_DATASETS_OFFLINE='1', MPLCONFIGDIR=str(work / '.cache/matplotlib'),
               REPRO_NETWORK_LOG=str(attempts))
    report = {'checked_on': '2026-11-24', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
              'passed': False, 'python': sys.version, 'executable': sys.executable,
              'isolated_working_copy': str(work), 'site_packages_inherited': sys.prefix == sys.base_prefix,
              'packages': {p: version(p) for p in ['numpy', 'soundfile', 'jiwer', 'scipy', 'matplotlib',
                                                 'nbformat', 'openai', 'reportlab', 'pypdf']},
              'audio_included': False, 'audio_revalidated': False, 'inference_requests': 0, 'stages': []}
    stages = [('pip_check', ['-m', 'pip', 'check']),
              ('offline_tests', ['-m', 'unittest', 'discover', '-s', 'tests']),
              ('reference_sensitivity', ['src/compare_audited_references.py']),
              ('cmi_analysis', ['src/analyze_cmi.py']),
              ('paired_uncertainty', ['src/analyze_uncertainty.py']),
              ('reviewed_variants', ['src/variant_sensitivity.py', '--saved-text-only']),
              ('report_pdf', ['src/build_research_report.py'])]
    try:
        for label, command in stages:
            print(f'Running {label} ...', flush=True)
            start = time.perf_counter()
            with (output / f'{label}.log').open('w', encoding='utf-8') as log:
                completed = subprocess.run([sys.executable, *command], cwd=work, env=env,
                                           stdout=log, stderr=subprocess.STDOUT, check=False)
            report['stages'].append({'name': label, 'exit_code': completed.returncode,
                                     'elapsed_s': round(time.perf_counter() - start, 3)})
            if completed.returncode:
                raise ValueError(f'{label} failed; see {output / (label + ".log")}')
        for name, saved in expected.items():
            regenerated = json.loads((work / 'results/metrics' / name).read_bytes())
            if name.startswith('variant_sensitivity'):
                regenerated.pop('computed_on', None)
                saved.pop('computed_on', None)
            compare(regenerated, saved, name)
        from pypdf import PdfReader
        filename = 'output/pdf/nepali_english_asr_research_report_draft.pdf'
        before, after = PdfReader(ROOT / filename), PdfReader(work / filename)
        compare([p.extract_text() for p in after.pages], [p.extract_text() for p in before.pages], 'PDF text/pages')
        report['pdf_pages'] = len(after.pages)
        report['pdf_text_and_page_count_match'] = True
        report['regenerated_json_results_match'] = RESULTS
        figure_names = ['cmi_band_error_rates_20261116', 'cmi_continuous_wer_20261116',
                        'cmi_by_channel_20261116', 'cmi_duration_checks_20261116',
                        'paired_uncertainty_20261119']
        for stem in figure_names:
            for suffix in ['png', 'svg']:
                if not (work / f'results/figures/{stem}.{suffix}').is_file():
                    raise ValueError(f'Missing reproduced figure: {stem}.{suffix}')
        report['analysis_figures_regenerated'] = figure_names
        report['report_figures'] = 'PDF uses the two included report figure assets; other analysis figures are regenerated.'
        report['network_connection_attempts'] = len(attempts.read_text().splitlines()) if attempts.exists() else 0
        if report['network_connection_attempts']:
            raise ValueError('Unexpected network attempt during reproduction')
        if any(digest(ROOT / name) != value or digest(work / name) != value
               for name, value in original_hashes.items()):
            raise ValueError('Frozen inputs/predictions/annotations changed')
        report['input_hashes_unchanged'] = original_hashes
        report['passed'] = True
    except Exception as error:
        report['failure'] = str(error)
        raise
    finally:
        report['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        (output / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print('PASS: saved-output analyses, offline tests and PDF reproduced without audio or network calls.', flush=True)
    print(output / 'verification.json')


if __name__ == '__main__':
    main()
