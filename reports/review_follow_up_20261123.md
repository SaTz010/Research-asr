# Review recovery and conservative variant sensitivity — November 23, 2026

Notebook 07 now has **10/10 saved researcher listening records**. Six questionable notebook-08 equivalences have been excluded from the tolerant score by changing `same` to `unsure`. These are assistant text-review exclusions, not new listening judgments. Original answers and previous scores are retained.

## Recovered notebook answers

The unsaved VS Code notebook contained completed answers for Example 09, but its save call was `save_example(examples, 8, ...)`. Running that cell overwrote Example 08 and left Example 09 pending. A Save As copy preserved the user buffer before any file reconciliation.

The assistant recovered the literal assignments from the cells headed Example 08 and Example 09, saved each to its intended record and corrected the Example 09 call to use `9`. The original user answers were retained verbatim:

| Example | Local categories | Hosted categories |
|---|---|---|
| 08 | wrong language output | wrong language output |
| 09 | script or spelling difference | missing speech; script or spelling difference |

Both user-entered reference assessments were `matches_audio`, with `listened = True`. This records the researcher's confirmation; the assistant did not independently hear the clips or validate the labels. Existing brief notes, including any disagreement between a category and its note, were preserved rather than silently interpreted. All other saved qualitative records remain unchanged.

The corrected notebook retains the recovered user cells and outputs plus the disk-only field guide. Stale save outputs for Examples 08/09 and final summary cells were cleared. Every example save target was checked against its section heading. The pre-recovery annotation file is retained as `data/annotations/error_examples_20261123_pre_recovery.json`; recovery metadata identifies the source cell and source-buffer checksum. Local recovery notebooks remain in ignored `.cache/`.

## Conservative handling of uncertain equivalences

The researcher confirmed that `same` means the same spoken word written differently. Text/context checks do not establish that the following six pairs meet that definition, so their zero-cost allowances were withdrawn. They remain uncertain rather than being declared definite recognition errors.

| Clip / pair | Reference → output | Text-review concern |
|---|---|---|
| 1 / 2 | service → serviced | Potential inflection difference. |
| 1 / 4 | task → tasks | Potential singular/plural difference. |
| 2 / 1 | भन्नेतर्फ → तर्फ | Partial-token or word-boundary pairing. |
| 4 / 14 | बुझिँदैन → डाईना | Same audible word is not established from text. |
| 5 / 15 | चाहिँ → थाक्के | Same audible word is not established; possible misalignment. |
| 7 / 6 | 81 → देर्पूर | The full output already contains एकासी nearby; देर्पूर may correspond to therefore elsewhere. |

Current decisions: **31 same, 47 different, 75 reference/alignment issue and 6 unsure**, across all 159 distinct within-clip candidate pairs. All ten researcher listening confirmations remain recorded. Assistant amendments have separate actor/timestamp/reason fields, and the previous records remain in history. Neither the original researcher timestamps nor other pair choices were changed.

The 75 reference/alignment labels do not establish 75 erroneous dataset words. None of those pairs, or the six uncertain pairs, receives a zero-cost substitution. The remaining 31 same-word approvals follow the researcher's judgments and have not been independently validated by another listener.

## Recomputed ten-clip sensitivity

Both systems use the same **185 normalized published-reference words**. References and hypotheses are unchanged.

| System | Strict edits / words | Strict WER | Approved-only edits / words | Approved-only WER | Reduction |
|---|---:|---:|---:|---:|---:|
| Local Large V2 | 148 / 185 | 80.00% | 128 / 185 | **69.19%** | 20 edits; 10.81 pp |
| Hosted whisper-1 | 192 / 185 | 103.78% | 166 / 185 | **89.73%** | 26 edits; 14.05 pp |

Before the conservative exclusions, the entered 37 approvals produced 67.57% local and 88.11% hosted WER. Those earlier results remain in the [original numerical snapshot report](variant_sensitivity_completed_20261123.md) and corresponding JSON/annotation snapshots. The [current generated report](variant_sensitivity_20261122.md) lists the remaining accepted pairs.

This supports a limited observation: accepting the reviewed alternative renderings lowers string-based error rates on these ten examples. It does not measure semantic accuracy, determine how many residual edits are genuinely wrong spoken words, or estimate the prevalence of spelling errors across all 1,198 clips. Split/joined words, alternative alignments, reference problems and unreviewed valid variants remain limitations. These post-hoc subset results do not replace the frozen benchmark or justify a causal conclusion about code-mixing or hosting.

## Verification and next work

- All **135 offline tests passed** after the corrections.
- A separate shortest-path alignment check reproduced all 40 strict/approved-only per-system edit counts; strict counts also agree with the existing full-pool per-clip analysis.
- Notebook 07 validates, all ten save targets match their section headings and no qualitative record is pending.
- Checksums confirm that frozen protocol, manifest, 50-clip audit, saved model predictions, primary aggregate scores, CMI analysis and uncertainty results are unchanged. Historical variant snapshots are unchanged.
- No model inference, audio upload, API request or dependency installation was performed. Numerical verification does not independently validate hearing or lexical equivalence.

Machine-readable provenance and checks: `results/metrics/review_follow_up_20261123.json`. Current annotation sources: `data/annotations/error_examples_20261120.json` and `data/annotations/word_variants_20261122.json`.

Next is a coherent main-report revision incorporating these bounded examples and sensitivity results, followed by clean-environment reproduction and release checks. The main PDF remains v0.2; no public release or LinkedIn post was made in this follow-up. Audio rechecking can resolve the six uncertain pairs later; accepting them is not required to report the conservative sensitivity.

If an older notebook-08 editor still contains unsaved `same` choices for these pairs, do not run those stale decision cells: they can explicitly restore old approvals. The current annotation JSON and current generated report are the saved result.
