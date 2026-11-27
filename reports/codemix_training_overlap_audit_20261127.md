# Training overlap audit for the code mix specialist

**November 27, 2026 · No change to the published research**

**Decision: the complete 1,198-clip result is not yet cleared as an independently held-out evaluation.** The public evidence supports held-out use for matching records, but the authors' training identities are unavailable. This audit does not demonstrate that the model trained on any of our test clips, and it does not certify their exclusion.

## What was checked

The evaluated checkpoint revision is unchanged on the Hub. The inspection covered its pinned model card/files, the authors' [November 10 preprint](https://arxiv.org/html/2611.13512v1), [official code repository](https://github.com/AI-Lab-Pvt-Ltd/nepali-codemixed-asr), both public commit trees, the available release and issues, model discussions, experiment notes and [text-only test-output dataset](https://huggingface.co/datasets/ailabpvtltd/nepali-english-codemix-asr-test-outputs). No training clip list was found in these resources. The release manifest hashes software files; the experiment notes give a dataset-manifest hash, not its underlying membership list.

## Our source dataset splits are clean for these clip identities

The cached source metadata matches the checksum frozen into our benchmark and the exact evaluated dataset revision. For our 1,198 clips, comparison against the full source splits gives:

| Source split | Rows | Exact clip overlap | Shared videos | Shared channels |
|---|---:|---:|---:|---:|
| train | 16702 | 0 | 0 | 0 |
| validation | 2338 | 0 | 0 | 0 |
| test | 1765 | 1198 | 22 | 2 |

This verifies our own dataset selection. It does **not** establish which revision, split or extra collected recordings the checkpoint actually saw. If the authors used exactly this revision and only its disjoint train split, the benchmark would be excluded from that source training split. That condition still needs confirmation.

## Matching against the authors' published held-out outputs

Their public table contains 4,610 test rows, including 1,574 lecture rows. Across our benchmark, **411 clips have one unique exact normalized-reference and duration candidate** in that lecture test table; **787 have no such exact candidate**. There are 0 ambiguous candidates under this rule.

The matching uses the existing project text normalization and a 0.001001-second duration tolerance. It uses no ASR hypotheses or fuzzy text similarity. The author IDs are aliases such as `sbc_test_000001`; the table does not supply source-video timestamps or waveform hashes. Matching text/duration is supporting evidence, not independent audio identity or proof that training contained no duplicates.

Unmatched clips are not labelled as training examples. The authors verbalized numbers and changed transcript conventions, and preparation may filter clips, so nonmatching reference text can have several explanations. The audit retains one evidence record for every one of the 1,198 clips.

## What the paper adds

Sections 3.3 and 5.1 say the inherited split assignments were kept and Whisper used the same training split. The authors also report cross-split duplicate checks. These are useful disclosures, not an independently reproduced intersection with our clip IDs. Their speaker-disjointness limitation concerns shared speakers and must not be misreported as confirmed reuse of the same audio clip. [Paper](https://arxiv.org/html/2611.13512v1).

## What would settle the question

Request the source revision/configuration, training and validation clip identities, and a mapping for changed aliases or boundaries. Check duplicate audio, overlapping portions of the same source video and augmented derivatives. Validation/checkpoint-selection exposure should be checked alongside gradient training exposure.

The [prepared identity packet](../data/manifests/codemix_overlap_request_20261127.json) contains all 1,198 canonical clip IDs, video IDs, timestamps, channel IDs, durations and waveform hashes, without audio or transcript text. It has not been sent to anyone. The packet can support an author-confirmed intersection or a local check if a training manifest is released.

Keep the 25.94% WER result as a separate exploratory result for now. Do not describe it as contaminated or as independently confirmed unseen-data performance. The main report, PDF and publication remain unchanged.

The [machine-readable audit](../results/metrics/codemix_training_overlap_audit_20261127.json) records all matches, source hashes and unresolved questions. Replay locally, without any new network/model calls:

```powershell
.\.venv\Scripts\python.exe src/audit_codemix_training_overlap.py
```
