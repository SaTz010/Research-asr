# Listen to the ten preselected examples

Open `notebooks/07_preselected_error_examples.ipynb` in VS Code and select `.venv/Scripts/python.exe` as kernel. This starts November 21's planned example review early on November 20. Keep notebook 06 and its frozen reference/CMI decisions unchanged. No ASR/API run or API key is required.

## One-time setup

Run the setup cell under section 1. It validates the frozen ten IDs, saved predictions and cached WAV payload/waveform hashes. It displays pending/saved review numbers. All clips are the examples selected before inference: two per published CMI band, not the ten worst predictions. Missing input evidence stops preparation rather than downloading or replacing a clip.

## For example 01

1. Run `show_audio(examples, 1)`. Play the complete audio, then replay as necessary. The cell shows the published reference and your earlier frozen human reference. Decide whether the **published** text agrees with the audio. Keep a possible remaining reference problem separate from model problems.
2. Run `show_outputs(examples, 1)`. Read both saved outputs and replay difficult parts. Under each output, the notebook shows normalized WER and an edit-alignment table. `substitute` means the written words differ, `delete` means a reference word is absent, and `insert` means an output word has no aligned reference word. These labels are mechanical, not verified explanations of the speech.
3. In that example's decision cell, set `reference_assessment` to `matches_audio`, `possible_reference_issue` or `unsure`. Fill `reference_notes` if there is a possible issue or uncertainty. You do not need to rewrite the full transcript or supply language tags.
4. Choose categories separately in `local_categories` and `api_categories`. Copy exact names from the notebook guide. Multiple categories are allowed; `no_clear_error` must stand alone. Do not choose a category merely because it explains a high number. Use `uncertain` if you cannot judge.
5. Write short `local_notes` and `api_notes`, quoting concrete word pairs or missing/extra spoken text. For example, **only if you actually hear it**, `"He says class; the output writes क्लास. Same word, different script."` supports `['script_or_spelling_difference']`. This illustration is not a judgment about example 01. Use other categories for genuinely changed words, omissions or unspoken additions. Different script alone does not prove wrong language.
6. Change `listened = False` to `listened = True` only after listening and checking the fields. Run the decision cell. It should print the saved record and `saved_listening_reviews: 1`. Blank categories/notes, `pending` references and inconsistent reviewer names are rejected rather than silently saved.

## Exactly what to write in the decision cell

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

## Continue and finish

Repeat A/audio, B/outputs and C/decision for examples 02–10. Allow roughly 5–10 minutes each, with a break after five. Take longer for difficult audio instead of guessing. Each successful decision is written immediately to `data/annotations/error_examples_20261120.json`. Rerunning setup reloads saved progress. Revisions to saved judgments preserve the previous record in the JSON history.

Run the final progress cell. All ten should have listening records; unresolved cases remain explicitly listed as uncertain. Save the notebook with Ctrl+S to retain edited cells/visible outputs as well. JSON decisions persist separately even if you close the notebook without saving its cells.

These examples can illustrate why individual WERs are high, including real recognition failures, script/spelling differences and reference issues. Ten preselected qualitative examples cannot quantify what fraction of all corpus errors each cause explains. We will interpret the listening notes before updating the report's examples/discussion, without rewriting frozen benchmark labels or silently rescoring the main experiment.
