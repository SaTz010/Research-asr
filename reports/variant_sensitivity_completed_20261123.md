# Saved variant review and numerical verification — November 23, 2026

**Historical snapshot before the authorized follow-up.** The [later recovery and conservative sensitivity](review_follow_up_20261123.md) restores notebook-07 records 08/09 and excludes six questionable allowances as uncertain. Its current approved-only WER is 69.19% local and 89.73% hosted. The original scores and status below describe this earlier snapshot.

Notebook 08 has **10/10 saved listening confirmations and all 159 distinct pair decisions**, with no pending choices. The researcher confirmed in chat that `same` meant the same spoken word written differently, rather than merely understandable intended meaning. The saved decisions are 37 same, 47 different and 75 reference/alignment issue. None was changed by the assistant during verification.

## Scores under the entered labels

Both systems use exactly the same ten preselected clips and 185 normalized published-reference words. These are neither the 50-clip audit scores nor the full 1,198-clip results.

| System | Strict word edits / words | Strict WER | Approved-only edits / words | Approved-only WER | Change |
|---|---:|---:|---:|---:|---:|
| Local Large V2 | 148 / 185 | 80.00% | 125 / 185 | 67.57% | -12.43 pp |
| Hosted whisper-1 | 192 / 185 | 103.78% | 163 / 185 | 88.11% | -15.68 pp |

The reductions are 23 local and 29 hosted edit operations under the supplied same-word allowances. They are not an exact count of all true script/spelling mistakes or a measure of semantic transcription accuracy. Accepted variants can change sentence alignment, and this candidate method can miss correct variants when a strict alignment pairs the wrong tokens. The remaining scores must not be called percentages of genuinely wrong spoken words.

In the strict substitution alignment, local occurrences are 22 marked same, 17 different and 52 reference/alignment issue; hosted occurrences are 27 same, 33 different and 63 reference/alignment issue. These occurrence counts can overlap across systems, differ from the number of distinct reviewed pairs and differ from the edit reduction after realignment. The 75 distinct reference/alignment-issue labels do not establish 75 inaccurate dataset words.

## Quality check before using the tolerant score as a validated result

The one-token review can propose misleading word pairs when words split, join or shift in a high-error alignment. Completion of the form does not independently validate each proposed equivalence. The full [current sensitivity report](variant_sensitivity_20261122.md) now lists every accepted pair transparently.

Priority examples to check in the complete audio and sentence context, without automatically rewriting any judgment:

| Clip / pair | Entered same-word allowance | Why check |
|---|---|---|
| 1 / 2 | service → serviced | Could be an inflection difference or reference mismatch, rather than spelling alone. |
| 1 / 4 | task → tasks | Singular/plural forms should not automatically be treated as the same rendering. |
| 2 / 1 | भन्नेतर्फ → तर्फ | A partial-word/word-boundary issue may be paired as a substitution. |
| 4 / 14 | बुझिँदैन → डाईना | Check whether this is only a fragment of an expression under a shifted alignment. |
| 5 / 15 | चाहिँ → थाक्के | Check the whole phrase before accepting this isolated pairing. |
| 7 / 6 | 81 → देर्पूर | The local sentence also contains एकासी. देर्पूर may correspond to therefore elsewhere, making this a mispaired alignment rather than a number variant. |

These are review flags, not independently listened-to speech judgments. The assistant inspected saved text but did not hear these clips. A genuinely identical spoken word written differently may retain `same`; a genuinely different word uses `different`; ambiguous or faulty pairings should use `unsure` or the existing reference/alignment-issue label. Preserve changes through the save function so earlier decisions remain in history. Scores remain provisional with respect to semantic-equivalence validity until these checks are resolved.

## Integrity and verification

The existing loader rechecked frozen data/protocol/prediction provenance and the ten WAV payloads/identities. Strict subset edit counts agree with the previous full-pool per-clip analysis. A separate shortest-path search over alignment states independently reproduced all 20 strict and all 20 approved-variant edit counts: 40 checks. Corpus aggregation retains the shared 185-word denominator. **All 135 offline tests pass**, including a new check that completed-review exports no longer display stale preparation text or turn reference/alignment labels into validated label errors.

Current exports have a correct Nepal-time computation date and an accepted-pair table. Point-in-time copies preserve `data/annotations/word_variants_20261123_snapshot.json` and `results/metrics/variant_sensitivity_completed_20261123.json`. Numerical verification and hashes are in `results/metrics/variant_sensitivity_completed_20261123_verified.json`. The earlier preparation-only verification remains a historical record of the zero-decision setup; it is not verification of the completed results. No frozen benchmark reference, hypothesis, primary result or human judgment was overwritten, and no API call, model execution or dependency installation was needed.

## What remains

Notebook 07 still has **clip 09 pending on disk**; clips 1–8 and 10 are saved. Save that listening record before calling the original qualitative review complete. Then resolve the targeted accepted-pair checks above and export notebook 08 again if labels change. The main PDF remains v0.2 until the example/supplement evidence is ready for a coherent revision. Clean-environment reproduction, final author/release review and public-link checks remain outstanding; no public release or LinkedIn post occurred here.
