"""Post-hoc, human-approved one-token spelling/transliteration sensitivity."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from html import escape
import json

from jiwer import process_words

from asr_common import normalize_text
from check_local_environment import ROOT
from error_example_review import load_examples, show_audio
from local_whisper_pilot import save_state

ANNOTATIONS = ROOT / 'data/annotations/word_variants_20261122.json'
DECISIONS = {'pending', 'same', 'different', 'unsure', 'reference_issue'}


def candidates(clip):
    pairs = {}
    for system, hypothesis in clip['outputs'].items():
        score = process_words(normalize_text(clip['published_reference']), normalize_text(hypothesis))
        for chunk in score.alignments[0]:
            if chunk.type != 'substitute':
                continue
            refs = score.references[0][chunk.ref_start_idx:chunk.ref_end_idx]
            hyps = score.hypotheses[0][chunk.hyp_start_idx:chunk.hyp_end_idx]
            if len(refs) != len(hyps):
                raise ValueError('Expected one-to-one substitution alignment.')
            for ref, hyp in zip(refs, hyps):
                pair = pairs.setdefault((ref, hyp), {'id': len(pairs)+1, 'reference': ref, 'output': hyp, 'occurrences': {}})
                pair['occurrences'][system] = pair['occurrences'].get(system, 0)+1
    return list(pairs.values())


def variant_counts(reference, hypothesis, approved):
    ref, hyp = normalize_text(reference).split(), normalize_text(hypothesis).split()
    if not ref:
        raise ValueError('A nonempty normalized reference is required.')
    if any(len(pair) != 2 or any(not isinstance(t, str) or len(normalize_text(t).split()) != 1 or normalize_text(t) != t for t in pair) for pair in approved):
        raise ValueError('Approved pairs must contain two normalized single tokens.')
    approved = set(approved)
    costs = [[0]*(len(hyp)+1) for _ in range(len(ref)+1)]
    for i in range(len(ref)+1):
        costs[i][0] = i
    for j in range(len(hyp)+1):
        costs[0][j] = j
    for i, a in enumerate(ref, 1):
        for j, b in enumerate(hyp, 1):
            penalty = int(a != b and (a, b) not in approved)
            costs[i][j] = min(costs[i-1][j-1]+penalty, costs[i-1][j]+1, costs[i][j-1]+1)
    counts = {'substitutions': 0, 'deletions': 0, 'insertions': 0, 'approved_variant_matches': 0, 'exact_matches': 0}
    i, j = len(ref), len(hyp)
    # Equal-cost tracebacks prefer diagonal, then deletion, then insertion.
    while i or j:
        if i and j:
            a, b = ref[i-1], hyp[j-1]
            penalty = int(a != b and (a, b) not in approved)
            if costs[i][j] == costs[i-1][j-1]+penalty:
                label = 'exact_matches' if a == b else 'approved_variant_matches' if penalty == 0 else 'substitutions'
                counts[label] += 1
                i, j = i-1, j-1
                continue
        if i and costs[i][j] == costs[i-1][j]+1:
            counts['deletions'] += 1
            i -= 1
        else:
            counts['insertions'] += 1
            j -= 1
    errors = sum(counts[k] for k in ['substitutions', 'deletions', 'insertions'])
    if errors != costs[-1][-1]:
        raise ValueError('Variant traceback and distance differ.')
    return {**counts, 'word_errors': errors, 'reference_words': len(ref), 'wer': errors/len(ref)}


def load_reviews(bundle):
    expected = [{'number': c['number'], 'clip_id': c['clip_id'], 'candidates': candidates(c)} for c in bundle['clips']]
    if ANNOTATIONS.exists():
        state = json.loads(ANNOTATIONS.read_bytes())
        if state['source_sha256'] != bundle['source_sha256'] or state['selection'] != expected:
            raise ValueError('Saved variant selection/provenance differs; preserve and investigate.')
        if len(state['reviews']) != len(expected):
            raise ValueError('Variant review coverage differs.')
        for review, selection in zip(state['reviews'], expected):
            keys = {str(p['id']) for p in selection['candidates']}
            if (review['number'] != selection['number'] or review['clip_id'] != selection['clip_id']
                    or set(review['decisions']) != keys or any(d not in DECISIONS for d in review['decisions'].values())):
                raise ValueError('Variant decisions/identities differ.')
            if any(d != 'pending' for d in review['decisions'].values()) and review.get('listened') is not True:
                raise ValueError('Variant decisions require explicit listening confirmation.')
        return state
    state = {'prepared_on': '2026-11-22', 'post_hoc': True, 'reviewer': '', 'source_sha256': bundle['source_sha256'],
             'selection': expected, 'history': [],
             'scope': 'Same ten preselected clips; manually accepted one-token renderings, not fuzzy/semantic matching or a corpus-wide truth classification.',
             'reviews': [{'number': e['number'], 'clip_id': e['clip_id'], 'listened': False,
                          'decisions': {str(p['id']): 'pending' for p in e['candidates']}, 'notes': ''} for e in expected]}
    save_state(ANNOTATIONS, state)
    return state


def save_decisions(bundle, number, reviewer, listened, decisions, notes=''):
    if isinstance(number, bool) or not isinstance(number, int) or not 1 <= number <= len(bundle['clips']):
        raise ValueError('Use a displayed clip number.')
    if listened is not True or not isinstance(reviewer, str) or not reviewer.strip() or not isinstance(notes, str):
        raise ValueError('Listen and provide a reviewer name; notes must be text.')
    state = load_reviews(bundle)
    record = state['reviews'][number-1]
    if not isinstance(decisions, dict):
        raise ValueError(f'Clip {number}: decisions must be a dictionary of pair IDs and choices.')
    if any(isinstance(k, bool) or not isinstance(k, int) for k in decisions):
        raise ValueError('Pair IDs must be integers without quotes, such as 1, 2, 3.')
    expected = {int(k) for k in record['decisions']}
    problems = []
    for label, ids in [('missing', expected-set(decisions)), ('unexpected', set(decisions)-expected)]:
        if ids:
            problems.append(f"{label} pair IDs: {', '.join(map(str, sorted(ids)))}")
    invalid = [f'pair {k}={v!r}' for k, v in decisions.items() if not isinstance(v, str) or v not in DECISIONS]
    if invalid:
        problems.append('unsupported choices: '+', '.join(invalid))
    if problems:
        raise ValueError(f"Clip {number}: {'; '.join(problems)}. Allowed choices: same, different, unsure, reference_issue, pending (lowercase, no extra spaces).")
    if decisions and all(v == 'pending' for v in decisions.values()) and all(v == 'pending' for v in record['decisions'].values()):
        raise ValueError('Review at least one pair before saving. You may leave other pairs pending.')
    if state['reviewer'] and state['reviewer'] != reviewer.strip():
        raise ValueError('Preserve the recorded reviewer identity.')
    if record.get('listened'):
        state['history'].append(record)
    state['reviews'][number-1] = {'number': number, 'clip_id': record['clip_id'], 'listened': True,
        'decisions': {str(k): record['decisions'][str(k)] if v == 'pending' else v for k, v in decisions.items()}, 'notes': notes.strip(),
        'reviewed_at_utc': datetime.now(timezone.utc).isoformat()}
    state['reviewer'] = reviewer.strip()
    save_state(ANNOTATIONS, state)
    return state['reviews'][number-1]


def analyze(bundle, state):
    if state['source_sha256'] != bundle['source_sha256'] or len(state['reviews']) != len(bundle['clips']):
        raise ValueError('Scoring provenance/coverage differs.')
    rows, occurrence_counts = [], {s: Counter() for s in ['local', 'whisper_api']}
    for clip, selection, review in zip(bundle['clips'], state['selection'], state['reviews']):
        if clip['clip_id'] != review['clip_id'] or candidates(clip) != selection['candidates']:
            raise ValueError('Scoring selection differs.')
        if any(d != 'pending' for d in review['decisions'].values()) and review.get('listened') is not True:
            raise ValueError('Scoring variants requires listening confirmation.')
        approved = {(p['reference'], p['output']) for p in selection['candidates'] if review['decisions'][str(p['id'])] == 'same'}
        systems = {}
        for system, hypothesis in clip['outputs'].items():
            strict = variant_counts(clip['published_reference'], hypothesis, set())
            tolerant = variant_counts(clip['published_reference'], hypothesis, approved)
            check = process_words(normalize_text(clip['published_reference']), normalize_text(hypothesis))
            if strict['word_errors'] != check.substitutions+check.deletions+check.insertions or tolerant['word_errors'] > strict['word_errors']:
                raise ValueError('Strict/variant counts are inconsistent.')
            systems[system] = {'strict': strict, 'approved_variants_only': tolerant,
                               'edit_reduction_under_approved_variants': strict['word_errors']-tolerant['word_errors']}
        for p in selection['candidates']:
            for system, count in p['occurrences'].items():
                occurrence_counts[system][review['decisions'][str(p['id'])]] += count
        rows.append({'number': clip['number'], 'clip_id': clip['clip_id'], 'systems': systems})
    totals = {}
    for system in occurrence_counts:
        scores = {}
        for condition in ['strict', 'approved_variants_only']:
            errors = sum(r['systems'][system][condition]['word_errors'] for r in rows)
            words = sum(r['systems'][system][condition]['reference_words'] for r in rows)
            scores[condition] = {'word_errors': errors, 'reference_words': words, 'wer': errors/words}
        scores['edit_reduction_under_approved_variants'] = scores['strict']['word_errors']-scores['approved_variants_only']['word_errors']
        totals[system] = scores
    decisions = Counter(d for r in state['reviews'] for d in r['decisions'].values())
    reviewed_clips = sum(r['listened'] and 'pending' not in r['decisions'].values() for r in state['reviews'])
    return {'computed_on': datetime.now(timezone(timedelta(hours=5, minutes=45))).date().isoformat(),
            'prepared_on': '2026-11-22', 'post_hoc': True, 'source_sha256': bundle['source_sha256'],
            'clips': len(rows), 'fully_reviewed_clips': reviewed_clips, 'unique_candidate_pairs': sum(decisions.values()),
            'pair_decision_counts': dict(decisions), 'review_complete': reviewed_clips == len(rows),
            'strict_alignment_substitution_occurrences': {s: dict(c) for s, c in occurrence_counts.items()},
            'systems': totals, 'per_clip': rows, 'inference_requests': 0,
            'scope': 'Same ten clips only. The approved-only score is provisional until review completion. Unreviewed/residual edits are not proven wrong spoken words. No global fuzzy or semantic equivalence.',
            'limitations': 'One-token, clip-scoped variants from a strict alignment. No automatic phonetic matching, split/merged-word variants, translations or exact corpus-wide error-cause decomposition.'}


def show_pairs(bundle, number):
    from IPython.display import HTML, display
    state = load_reviews(bundle)
    show_audio(bundle, number)
    clip = bundle['clips'][number-1]
    for s, output in clip['outputs'].items():
        print(s.upper()+':', output)
    lines = ['<table><tr><th>ID</th><th>Published word</th><th>Model word</th><th>Systems / occurrences</th><th>Saved choice</th></tr>']
    for p in state['selection'][number-1]['candidates']:
        cells = [str(p['id']), p['reference'], p['output'], str(p['occurrences']), state['reviews'][number-1]['decisions'][str(p['id'])]]
        lines.append('<tr>'+''.join('<td>'+escape(v)+'</td>' for v in cells)+'</tr>')
    display(HTML(''.join(lines)+'</table>'))
    print('same = same spoken word, written differently; different = genuinely different word; unsure = cannot judge; reference_issue = reference does not match the speech.')


def export_results(bundle):
    state = load_reviews(bundle)
    result = analyze(bundle, state)
    import hashlib
    result['variant_review_sha256'] = hashlib.sha256(ANNOTATIONS.read_bytes()).hexdigest()
    save_state(ROOT / 'results/metrics/variant_sensitivity_20261122.json', result)
    lines = [f"# Reviewed spelling and transliteration sensitivity — {result['computed_on']}", '',
        '**Post-hoc extension, not a replacement for the frozen benchmark.** Same ten preselected clips and published references; hypotheses never change. No API call or model run.', '',
        f"Review progress: {result['fully_reviewed_clips']}/{result['clips']} clips complete; {result['unique_candidate_pairs']} distinct within-clip word pairs. Decisions: `{result['pair_decision_counts']}`.", '',
        'The score uses the original normalization and word edit-distance algorithm, assigning zero substitution cost only to clip-scoped pairs explicitly judged `same` after listening. There is no automatic spelling-distance threshold, romanizer, semantic translation or transitive/global aliasing. One accepted pair applies to its occurrences within that clip, in both systems where present.', '',
        '| System, same ten clips | Strict WER | Approved-variants-only WER | Edit reduction |', '|---|---:|---|---:|']
    any_decided = any(k != 'pending' and v for k, v in result['pair_decision_counts'].items())
    for s, values in result['systems'].items():
        shown = f"{100*values['approved_variants_only']['wer']:.2f}%" if any_decided else 'Pending human pair review'
        lines.append(f"| {s} | {100*values['strict']['wer']:.2f}% | {shown} | {values['edit_reduction_under_approved_variants']} |")
    status = ('All pair decisions have been saved. These rates follow the entered reviewer labels; completion is not independent validation that every approved pair is the same lexical word.'
              if result['review_complete'] else 'Review is incomplete. Partial-review values are provisional; unreviewed variants have not been forgiven.')
    lines += ['', status+' Do not compare these ten-clip rates directly with the 1,198-clip benchmark.', '',
        f"Reference/alignment-issue pairs: {result['pair_decision_counts'].get('reference_issue', 0)}. This combined label does not prove that this many published reference words are wrong; it can reflect ambiguous word pairing or split/joined words. These pairs are not forgiven.", '',
        '## What can be counted', '',
        'The JSON separates occurrences in one minimum-edit strict substitution alignment into same/different/unsure/reference_issue/pending decisions. It also records the edit reduction after rerunning variant-aware alignment. These are different quantities: accepted equivalences can change the alignment. Neither the remaining edit count nor the score reduction is an exact corpus-wide decomposition of actual speech errors versus script errors.', '',
        'Insertions/deletions and uncertain or faulty-reference cases still require listening. This first version does not handle split/joined words or prove equivalence from phonetic similarity. Different lexical words, inflections, translations or synonyms must not be accepted solely because their meanings or spellings are close.', '',
        '## Accepted pairs for transparency', '',
        'Every `same` choice below is a reviewer judgment, not an automatic phonetic/semantic finding. Recheck suspicious numeric, inflection or misaligned pairs in full sentence/audio context before describing the score as validated spelling/transliteration tolerance. Preserve earlier decisions in history when revising.', '',
        '| Clip | Pair | Reference token | Output token | Occurrences |', '|---|---:|---|---|---|']
    for selection, review in zip(state['selection'], state['reviews']):
        for pair in selection['candidates']:
            if review['decisions'][str(pair['id'])] == 'same':
                values = [selection['number'], pair['id'], pair['reference'], pair['output'], pair['occurrences']]
                lines.append('| '+' | '.join(escape(str(v)).replace('|', '\\|') for v in values)+' |')
    lines += ['', '## Status and provenance', '',
        'Use notebook 08 or `python src/variant_sensitivity.py`. It prepares candidates and exports current reviewed results without fabricating decisions. Pair judgments live separately in `data/annotations/word_variants_20261122.json`; prior saves retain history. Notebook 07 and its qualitative notes are preserved. Frozen references, primary WER/CER, CMI analyses and uncertainty intervals remain unchanged.', '',
        'This post-hoc addition was motivated by the unexpectedly high error rates and discussion after inspecting results; it was not predeclared. Validation is limited to this single-reviewer subset. The separate notebook-07 listening records and clean release checks must also be checked before publication.', '',
        'Related methods: [PolyWER, Kadaoui et al. 2024](https://aclanthology.org/2024.findings-emnlp.356/) and [Emond et al. 2018](https://research.google/pubs/transliteration-based-approaches-to-improve-code-switched-speech-recognition-performance/). This narrow one-token reviewed-variant scorer is not an implementation of either full published framework.', '']
    (ROOT / 'reports/variant_sensitivity_20261122.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({k: result[k] for k in ['fully_reviewed_clips', 'clips', 'pair_decision_counts', 'systems']}, indent=2))
    return result


def prepare_notebook(bundle):
    import nbformat as nbf
    path = ROOT / 'notebooks/08_reviewed_variant_sensitivity.ipynb'
    if path.exists():
        return path
    state = load_reviews(bundle)
    cells = [nbf.v4.new_markdown_cell('# Same-word spelling and transliteration sensitivity\n\n'
        'Post-hoc extension on the same ten preselected clips. Original scores/notes remain unchanged. '
        'Listen and review the displayed word pairs. You only replace `pending` with `same`, `different`, `unsure` or `reference_issue`. '
        'No long note is required: the table retains the actual words. `same` means the same audible lexical word written differently, not a synonym, translation, inflection change or merely similar-looking word. '
        'For a faulty reference choose `reference_issue`; uncertain cases remain unaccepted. This cannot classify all 1,198 clips automatically.'),
        nbf.v4.new_code_cell("from pathlib import Path\nimport sys, json\n"
            "ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / 'src/variant_sensitivity.py').is_file())\n"
            "sys.path.insert(0, str(ROOT / 'src'))\nfrom variant_sensitivity import load_examples, load_reviews, show_pairs, save_decisions, export_results\n"
            "bundle = load_examples()\nreviewer = 'Sanskar Ananta Tiwari'\nstate = load_reviews(bundle)\n"
            "print('Saved pair judgments are loaded. Outputs and original references are unchanged.')")]
    for clip, selection in zip(bundle['clips'], state['selection']):
        n = clip['number']
        template = '\n'.join(f"    {p['id']}: 'pending'," for p in selection['candidates'])
        cells += [nbf.v4.new_markdown_cell(f'## Clip {n:02d}\n\nPlay the audio and inspect each numbered pair. '
            'Change only the decision words in the next cell. You may save partially with some pairs still pending. '
            'Set `listened = True` after listening. If reopening, your saved decisions appear in the table. '
            'A pending entry preserves its previously saved choice; use another explicit choice to revise it.'),
            nbf.v4.new_code_cell(f'show_pairs(bundle, {n})'),
            nbf.v4.new_code_cell("listened = False\ndecisions = {\n"+template+"\n}\nnotes = ''  # Optional context; exact word pairs are already retained.\n"
                "if listened is True:\n"
                f"    print(save_decisions(bundle, {n}, reviewer, listened, decisions, notes))\n"
                "else:\n    print('Not saved: listen and choose the word-pair decisions first.')")]
    cells += [nbf.v4.new_markdown_cell('## Export current results\n\nRun after saving pair decisions. '
        'Partial results are provisional. The remaining errors are not automatically genuine wrong spoken words. '
        'Notebook 07 still stores the broader missing/extra/reference/error observations.'),
        nbf.v4.new_code_cell('result = export_results(bundle)')]
    notebook = nbf.v4.new_notebook(cells=cells, metadata={'kernelspec': {'display_name': 'Python (.venv)', 'language': 'python', 'name': 'python3'}, 'language_info': {'name': 'python'}})
    nbf.validate(notebook)
    path.write_text(nbf.writes(notebook), encoding='utf-8')
    return path


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--saved-text-only', action='store_true',
                        help='Recompute from frozen references/outputs/reviews without private WAVs; does not revalidate audio.')
    args = parser.parse_args()
    bundle = load_examples(verify_audio=not args.saved_text_only)
    if args.saved_text_only:
        print('Saved-text-only reproduction: frozen metadata/output/review hashes checked; audio payloads and hearing are not revalidated.')
    print(prepare_notebook(bundle))
    export_results(bundle)
