"""Listen to the ten preselected examples; save judgments outside the frozen audit."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
from html import escape
import json

from jiwer import process_words

from asr_common import normalize_text
from budget import cmi_band
from check_local_environment import ROOT
from compare_audited_references import load_verified_inputs
from local_whisper_pilot import save_state
from prepare_pilot_audio import verify_payload
from prepare_validation_check import BANDS

REVIEWS = ROOT / 'data/annotations/error_examples_20261120.json'
CATEGORIES = {
    'script_or_spelling_difference': 'Same audible word appears in a different script/spelling; quote the pair.',
    'wrong_word': 'Output contains a different word from the audible speech.',
    'missing_speech': 'Clearly audible words are absent from the output.',
    'extra_or_repeated_text': 'Output adds or repeats words that are not audible; replay before choosing.',
    'wrong_language_output': 'Output is in a different language from the speech; a different script alone is not sufficient.',
    'no_clear_error': 'No clear transcription problem after listening and comparing.',
    'uncertain': 'Speech/output interpretation is unresolved; explain what you cannot determine.'}

FIELD_GUIDE = """## 2.1 Exactly what to write in the decision cell

You are answering three questions: **Does the published reference match the audio? What did local get wrong? What did the API get wrong?** You are not calculating WER or writing language tags. Leave the save/print code below your answers unchanged.

| Field | What you put here |
|---|---|
| `listened` | Change `False` to `True` after playing the full clip. No quotation marks around `True`. |
| `reference_assessment` | `'matches_audio'` if the published transcript matches what you hear; `'possible_reference_issue'` if it contains a mistake; `'unsure'` if you cannot tell. Judge the published reference, not the model output. |
| `reference_notes` | Keep `''` if the published reference matches. Otherwise quote the doubtful part and what you hear, or explain what is unclear. Do not rewrite the frozen reference. |
| `local_categories` | A list of applicable names from the category guide, such as `['wrong_word', 'missing_speech']`. If local sounds/textually agrees, use `['no_clear_error']` alone. If unresolved, use `['uncertain']`. |
| `local_notes` | A short explanation: `"I hear __; local writes __; the difference is __."` For no clear error, say that the audible words are preserved. |
| `api_categories` | The same type of list, based on the hosted output. Its categories can differ from local. |
| `api_notes` | A short explanation: `"I hear __; the API writes __; the difference is __."` |

**Practice example only - not a judgment about Example 01.** Imagine the audio and published reference both say `आज class छ`, local writes `आज क्लास छ`, and the API writes `आज छ`. Those observations would support:

```python
listened = True
reference_assessment = 'matches_audio'
reference_notes = ''
local_categories = ['script_or_spelling_difference']
local_notes = "I hear class; local writes क्लास. The same word is written in Devanagari."
api_categories = ['missing_speech']
api_notes = "I hear class between आज and छ; the API leaves class out."
```

**Do not copy these practice judgments into your real review.** Fill your actual cell from the clip you heard. The alignment's `substitute` label does not automatically mean `wrong_word`: it could be a script/spelling difference. Several errors can coexist, so select multiple categories when supported. `no_clear_error` must stand alone. After filling the real answers, run the cell and check the saved review count.
"""


def load_examples(*, verify_audio=True):
    _, audit, manifest, predictions, checksums = load_verified_inputs()
    protocol = json.loads((ROOT / manifest['protocol_config']).read_bytes())
    document = (ROOT / protocol['protocol_document']).read_bytes()
    if hashlib.sha256(document).hexdigest() != protocol['protocol_document_sha256']:
        raise ValueError('Frozen protocol document differs.')
    checksums['protocol_document'] = hashlib.sha256(document).hexdigest()
    selected = protocol['error_example_clip_ids']
    if len(selected) != 10 or len(set(selected)) != 10:
        raise ValueError('The frozen example set must contain exactly ten unique clips.')
    by_id = {e['identity']['clip_id']: e for e in manifest['clips']}
    human = {r['clip_id']: r for r in audit['reviews']}
    clips = []
    for number, key in enumerate(selected, 1):
        if key not in by_id or key not in human:
            raise ValueError('Example is outside the frozen evaluation/audit selections.')
        entry = by_id[key]
        audio_path = ROOT / entry['audio_path']
        if verify_audio:
            verify_payload(entry['identity'], audio_path.read_bytes(), entry['payload_sha256'], 'test')
        outputs = {s: predictions[s][key]['hypothesis'] for s in ['local', 'whisper_api']}
        if any(predictions[s][key]['status'] != 'received' or not isinstance(h, str) for s, h in outputs.items()):
            raise ValueError('Example is missing a successful saved output.')
        clips.append({'number': number, 'clip_id': key, 'cmi': entry['identity']['cmi'],
                      'audio_path': audio_path, 'published_reference': entry['identity']['transcription'],
                      'frozen_human_reference': human[key]['corrected_reference'], 'outputs': outputs})
    if Counter(cmi_band(c['cmi']) for c in clips) != Counter({b: 2 for b in BANDS}):
        raise ValueError('The preselected set must retain two examples per published CMI band.')
    return {'clips': clips, 'source_sha256': checksums, 'audio_integrity_checked': verify_audio}


def progress(bundle):
    identities = [(c['number'], c['clip_id']) for c in bundle['clips']]
    if REVIEWS.exists():
        state = json.loads(REVIEWS.read_bytes())
        if (state['source_sha256'] != bundle['source_sha256'] or
                [(r['number'], r['clip_id']) for r in state['reviews']] != identities):
            raise ValueError('Saved example judgments refer to different inputs; preserve and investigate.')
        return state
    state = {'prepared_on': '2026-11-20', 'reviewer': '', 'source_sha256': bundle['source_sha256'],
             'scope': 'Ten preselected qualitative examples; categories overlap and cannot estimate corpus error causes/prevalence.',
             'human_listening_independently_verified': False, 'history': [],
             'reviews': [{'number': n, 'clip_id': key, 'status': 'pending'} for n, key in identities]}
    save_state(REVIEWS, state)
    return state


def save_example(bundle, number, reviewer, listened, reference_assessment, reference_notes,
                 local_categories, local_notes, api_categories, api_notes):
    if isinstance(number, bool) or not isinstance(number, int) or not 1 <= number <= len(bundle['clips']):
        raise ValueError('Use a displayed example number from 1 to 10.')
    if listened is not True or not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError('Listen fully and provide the reviewer name before saving.')
    if reference_assessment not in {'matches_audio', 'possible_reference_issue', 'unsure'}:
        raise ValueError('Choose matches_audio, possible_reference_issue, or unsure for the published reference.')
    if not isinstance(reference_notes, str) or (reference_assessment != 'matches_audio' and not reference_notes.strip()):
        raise ValueError('Explain possible reference issues or uncertainty in reference_notes.')
    systems = {}
    for system, categories, notes in [('local', local_categories, local_notes), ('whisper_api', api_categories, api_notes)]:
        if (not isinstance(categories, list) or not categories or any(not isinstance(c, str) or c not in CATEGORIES for c in categories)
                or len(set(categories)) != len(categories)):
            raise ValueError(f'{system}: select at least one valid category, without duplicates.')
        if 'no_clear_error' in categories and len(categories) != 1:
            raise ValueError('no_clear_error cannot be combined with error/uncertain categories.')
        if not isinstance(notes, str) or not notes.strip():
            raise ValueError(f'{system}: write a short listening note quoting a concrete example, or explain uncertainty.')
        systems[system] = {'categories': categories, 'notes': notes.strip()}
    state = progress(bundle)
    if state['reviewer'] and state['reviewer'] != reviewer.strip():
        raise ValueError('Preserve the recorded reviewer identity.')
    previous = state['reviews'][number - 1]
    if previous['status'] == 'reviewed':
        state['history'].append(previous)
    record = {'number': number, 'clip_id': bundle['clips'][number-1]['clip_id'], 'status': 'reviewed',
              'listened': True, 'reference_assessment': reference_assessment, 'reference_notes': reference_notes.strip(),
              'systems': systems, 'reviewed_at_utc': datetime.now(timezone.utc).isoformat()}
    state['reviewer'] = reviewer.strip()
    state['reviews'][number-1] = record
    save_state(REVIEWS, state)
    return record


def show_audio(bundle, number):
    from IPython.display import Audio, display
    clip = bundle['clips'][number-1]
    print(f"Example {number:02d} | {clip['clip_id']} | published CMI {clip['cmi']}")
    display(Audio(filename=str(clip['audio_path'])))
    print('Published reference:', clip['published_reference'])
    print('Earlier frozen human reference:', clip['frozen_human_reference'])
    print('Saved listening judgment:', progress(bundle)['reviews'][number-1])


def show_outputs(bundle, number):
    from IPython.display import HTML, display
    clip = bundle['clips'][number-1]
    for system, hypothesis in clip['outputs'].items():
        print('\n', 'LOCAL LARGE V2' if system == 'local' else 'HOSTED WHISPER API')
        print(hypothesis or '[empty output]')
        score = process_words(normalize_text(clip['published_reference']), normalize_text(hypothesis))
        print(f'Against published reference: WER {100*score.wer:.2f}% | substitutions {score.substitutions}, deletions {score.deletions}, insertions {score.insertions}')
        lines = ['<table><tr><th>Alignment operation</th><th>Published reference</th><th>Model output</th></tr>']
        for chunk in score.alignments[0]:
            ref = ' '.join(score.references[0][chunk.ref_start_idx:chunk.ref_end_idx]) or '[no word]'
            hyp = ' '.join(score.hypotheses[0][chunk.hyp_start_idx:chunk.hyp_end_idx]) or '[no word]'
            lines.append(f'<tr><td>{escape(chunk.type)}</td><td>{escape(ref)}</td><td>{escape(hyp)}</td></tr>')
        display(HTML(''.join(lines) + '</table>'))
    print('Alignment operations are string comparisons, not verified speech-error causes. Listen before classifying.')


def summary(bundle):
    state = progress(bundle)
    reviewed = [r for r in state['reviews'] if r['status'] == 'reviewed']
    return {'saved_listening_reviews': len(reviewed), 'expected': len(bundle['clips']),
            'pending_numbers': [r['number'] for r in state['reviews'] if r['status'] == 'pending'],
            'uncertain_numbers': [r['number'] for r in reviewed if r['reference_assessment'] == 'unsure' or any(
                'uncertain' in s['categories'] for s in r['systems'].values())],
            'category_example_counts': {system: dict(Counter(c for r in reviewed for c in r['systems'][system]['categories']))
                                        for system in ['local', 'whisper_api']},
            'note': 'Overlapping qualitative example counts, not corpus error percentages. Code does not verify hearing.'}


def prepare_notebook(bundle):
    import nbformat as nbf
    path = ROOT / 'notebooks/07_preselected_error_examples.ipynb'
    if path.exists():
        print('Notebook already exists; preserving your edits:', path)
        return path
    cells = [nbf.v4.new_markdown_cell('# Listening review of ten preselected ASR examples\n\n'
        'November 21 work, prepared November 20. Use the local project kernel. No model/API run and no word-language tagging. '
        'Review every selected example, including good outputs. This is qualitative diagnosis, not an estimate of error causes across all 1,198 clips. '
        'The published references, frozen human audit and benchmark scores remain unchanged. See `reports/error_example_review_guide.md`.'),
        nbf.v4.new_markdown_cell('## 1 Setup and saved progress\n\nRun this once per kernel. Your previous listening notes are loaded; pending items are not marked reviewed automatically.'),
        nbf.v4.new_code_cell("from pathlib import Path\nimport json, sys\n"
            "ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / 'src/error_example_review.py').is_file())\n"
            "sys.path.insert(0, str(ROOT / 'src'))\n"
            "from error_example_review import load_examples, progress, show_audio, show_outputs, save_example, summary, CATEGORIES\n"
            "examples = load_examples()\nreviewer = 'Sanskar Ananta Tiwari'\n"
            "print(json.dumps(summary(examples), indent=2))\n"
            "print('Saved separately to:', ROOT / 'data/annotations/error_examples_20261120.json')"),
        nbf.v4.new_markdown_cell('## 2 Category guide\n\n' + '\n'.join(f'- `{key}`: {description}' for key, description in CATEGORIES.items()) +
            '\n\nSelect multiple categories if justified. Use `no_clear_error` by itself. Use `uncertain` when needed. '
            'Do not call repeated text a hallucination without checking the audio. A different script does not by itself establish a different spoken language. '
            'The alignment table helps locate text differences; it does not decide their cause.'),
        nbf.v4.new_markdown_cell(FIELD_GUIDE)]
    for clip in bundle['clips']:
        n = clip['number']
        cells.extend([nbf.v4.new_markdown_cell(f"## Example {n:02d} | published CMI {clip['cmi']}\n\n"
            'A. Run the audio cell and listen fully before opening the model outputs. Compare the published and earlier human reference; '
            'note any remaining reference problem separately. B. Run the output/alignment cell and replay difficult parts. '
            'C. Edit and run the decision cell. No transcript correction or token-language list is required.'),
            nbf.v4.new_code_cell(f'show_audio(examples, {n})'),
            nbf.v4.new_code_cell(f'show_outputs(examples, {n})'),
            nbf.v4.new_code_cell("# Fill these after listening. Keep text in quotes.\n"
                "listened = False\nreference_assessment = 'pending'  # matches_audio / possible_reference_issue / unsure\n"
                "reference_notes = ''  # Required for a possible reference issue or uncertainty.\n"
                "local_categories = []  # Use the exact category names from the guide.\nlocal_notes = ''  # Quote what you hear versus the output; explain the difference.\n"
                "api_categories = []\napi_notes = ''\n\n"
                "if listened is True:\n"
                f"    print(save_example(examples, {n}, reviewer, listened, reference_assessment, reference_notes, local_categories, local_notes, api_categories, api_notes))\n"
                "    print(json.dumps(summary(examples), indent=2))\n"
                "else:\n    print('Not saved. Listen fully, fill the fields, then set listened = True and rerun this cell.')")])
    cells.extend([nbf.v4.new_markdown_cell('## 3 Final progress check\n\nRun after the ten examples. '
        'Uncertainty is allowed and disclosed; never guess to clear a pending item. Notes are saved in JSON when each decision cell succeeds. '
        'Save this notebook if you want to retain edited cells/outputs too. No files need uploading for review in this shared workspace.'),
        nbf.v4.new_code_cell('print(json.dumps(summary(examples), indent=2))')])
    notebook = nbf.v4.new_notebook(cells=cells, metadata={'kernelspec': {'display_name': 'Python (.venv)', 'language': 'python', 'name': 'python3'},
                                                       'language_info': {'name': 'python'}})
    nbf.validate(notebook)
    path.write_text(nbf.writes(notebook), encoding='utf-8')
    return path


if __name__ == '__main__':
    examples = load_examples()
    progress(examples)
    print(prepare_notebook(examples))
    print(json.dumps(summary(examples), indent=2))
