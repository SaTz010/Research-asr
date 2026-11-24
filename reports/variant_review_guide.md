# Review same-word spelling and transliteration pairs

This is a post-hoc addition requested November 22, after the original benchmark was scored. It adds **review-approved variant WER** on the same ten preselected clips. Primary WER/CER and the full 1,198-clip results remain unchanged. The scorer does not use fuzzy edit-distance thresholds, automatic phonetic similarity, synonyms or translation to declare two words equivalent.

## What to do

1. Open `notebooks/08_reviewed_variant_sensitivity.ipynb` in VS Code with the project `.venv` kernel. Run setup once. Your notebook-07 listening notes remain separate and preserved.
2. Under clip 01, run `show_pairs(bundle, 1)`. Play/replay the audio. The table shows a number, published word, model word, affected system(s) and saved decision for each candidate pair. These are pairs from one strict minimum-edit alignment, not automatic diagnoses.
3. In that clip's decision cell, replace each `'pending'` with one of the four choices below. Keep the numbers and quote marks. Set `listened = True` after listening, then run the cell. You do not have to type the word pairs or long notes; the table retains them. `notes` is optional.
4. Continue through the same ten clips. Partial saves are allowed. Pending entries preserve a previously saved choice; use another explicit choice to revise it. Earlier saves are retained in history. If a clip has no candidate pairs, listen and save its empty dictionary to confirm review.
5. Run the final export cell. It writes the current score and coverage to `results/metrics/variant_sensitivity_20261122.json` and `reports/variant_sensitivity_20261122.md`. Partial values are provisional. Complete means every pair has a decision and each clip has listening confirmation; unsure/reference-issue cases still remain unaccepted and unresolved as error causes.

| Choice | Meaning |
|---|---|
| `'same'` | The same lexical word is audible, but written with a different spelling or script. Accept only if listening supports both as renderings of that word. |
| `'different'` | The output represents a genuinely different word from the audible word represented by the reference. |
| `'unsure'` | You cannot confidently judge the pair; the score will not forgive it. |
| `'reference_issue'` | The reference token itself does not match the audio, or the alignment pairs the wrong words. Do not approve it as a same-word variant. |

For a hypothetical pair `class` / `क्लास`, choose `'same'` only if the spoken English word is class and these are its alternative renderings. `cat` / `cut` is not automatically accepted merely because one letter differs. A plural/inflection change is not automatically a spelling variant. Synonyms and translations are also different spoken words for this task.

## How the score works

Exact normalized words still match as before. Explicitly approved pairs get zero substitution cost within that clip; both systems receive the same allowance wherever that pair occurs there. All other edits keep their original costs. The algorithm realigns the full sentence, so reduced edit count is not necessarily the number of approved candidate occurrences. No variant approval transfers to another clip without review, and no transitive aliasing is inferred.

The export separates reviewed same/different/unsure/reference-issue/pending substitution occurrences and remaining edits. **Remaining edits are not automatically genuinely wrong spoken words.** Reference problems, alignment ambiguity and unreviewed variants remain possible. Insertions/deletions still require notebook 07's broader listening judgments.

## Limits

The first version handles one-token pairs proposed by a strict alignment. It can miss valid alternatives when that alignment pairs different words or when words are split/joined differently. This is not a complete transliteration engine, acoustic evaluator or implementation of full PolyWER. The reviewer can flag a questionable pairing as a reference/alignment issue rather than approving a false equivalence.

These ten examples cannot establish the fraction of all 1,198-clip errors due to spelling, nor can the remaining score be called true semantic error rate. Annotation is single-reviewer and informed by already seen outputs. Report it as a post-hoc, limited sensitivity analysis. The original listening review and clean release checks still need finishing.

## If a decision cell fails to save

The error identifies missing/unexpected pair IDs or the exact pair with an unsupported choice. Keep the displayed integer IDs and use lowercase `same`, `different`, `unsure`, `reference_issue` or `pending`, without extra spaces. Invalid input does not overwrite saved judgments. A repeated dictionary key can hide another pair; the missing-ID message helps locate this.

If an already-open kernel still shows the older generic error after the helper was updated, run this once in a separate cell, then rerun your existing decision cell without discarding its answers:

```python
import importlib
import variant_sensitivity
importlib.reload(variant_sensitivity)
from variant_sensitivity import save_decisions
```
