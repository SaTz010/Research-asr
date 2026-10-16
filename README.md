# Nepali–English code-switched ASR benchmark

Independent research project. Target completion: **November 15, 2026**, Asia/Kathmandu. One motivation is a Virginia Tech MSCS application; the research deliverable is a reproducible empirical report, including negative or inconclusive findings.

Status, October 16: project brief recorded; public dataset/model documentation checked; proposed protocol below. No audio, weights, or inference results have been downloaded or generated in this workspace. The reported preliminary Whisper behavior has not been independently reproduced.

## Question and scope

Is reference-transcript code-mixing intensity associated with transcription error, and does that association differ across the three selected checkpoints?

Use association language: this observational benchmark cannot establish that CMI causes errors. Do not assume that error must increase monotonically.

Core: `saileshbro/nepali-cs-asr`, primarily `speech_type="cs"`; three checkpoints; WER, CER, CMI analysis, inference speed, and a bounded error audit. Translation, application development, additional models, and new-model training remain outside scope until this benchmark is complete. English-token preservation is optional.

## What the public documentation changes

The [dataset card](https://huggingface.co/datasets/saileshbro/nepali-cs-asr) reports existing `cmi`, mixed-script `transcription`, provenance, and alternate-script columns. Most labels are machine generated; alternate-script labels are stale for corrected rows, and some test identities are ambiguous. Its current splits are channel-disjoint, but `speaker_id` is a channel identifier, not a verified person. The documented test split contains only two channels. Corpus language statistics use script as a language proxy. These are documentation claims to verify against the pinned files, not completed local checks.

| Checkpoint | Role and interpretation |
| --- | --- |
| [`openai/whisper-large-v3-turbo`](https://huggingface.co/openai/whisper-large-v3-turbo) | General multilingual baseline. |
| [`sumanpaudel1997/nepali-asr-whisper-turbo`](https://huggingface.co/sumanpaudel1997/nepali-asr-whisper-turbo) | Nepali fine-tune of the same base checkpoint; strongest comparison for adaptation. Its card reports read-speech fine-tuning on OpenSLR SLR54. |
| [`sumanpaudel1997/nepali-asr-indicwav2vec`](https://huggingface.co/sumanpaudel1997/nepali-asr-indicwav2vec) | Additional Nepali CTC baseline. Architecture, size, and pretraining differ, so differences cannot be attributed solely to specialization. |

The [published CTC vocabulary](https://huggingface.co/sumanpaudel1997/nepali-asr-indicwav2vec/blob/main/vocab.json) has no Latin letters. Under its standard character decoding, exact Latin-script English output is unavailable. Therefore mixed-script WER measures a script requirement as well as recognition; Latin-token preservation is not a comparable recognition-capability test for this checkpoint. Recheck the vocabulary at the chosen revision.

## Proposed evaluation protocol

1. **Freeze inputs.** Record full dataset and checkpoint commit SHAs, the `default` configuration, and package versions. Inventory actual split sizes, CS counts, audio durations/rates, missing values, and CMI distributions. Do not copy headline counts from the card into results.
2. **Audit identity.** Save original split and row index plus `video_id`, `start_ms`, `end_ms`, and channel for each clip. Check missing/duplicate provenance, overlapping segments, audio hashes, and cross-split channel/video overlap. Quarantine unresolved identities with reasons; never join corrections using an ambiguous key. Report exclusions and model failures.
3. **Separate development from evaluation.** Use validation CS clips for debugging and decoding decisions; reserve test CS clips for frozen evaluation. Do not randomly pool and resplit the corpus. Keep all three models on the same valid test manifest. Never drop difficult predictions or empty outputs because they harm scores.
4. **Check reference quality before viewing predictions.** Select up to 100 test clips using seed 42, spread across available CMI bands, channels, and videos. Listen and correct their references under a written mixed-script convention; save originals and corrections separately. Record token-language decisions for names, numerals, borrowings, and ambiguous or mixed tokens. A second reader can check 20 clips if available; otherwise disclose single-annotator judgment. Freeze this subset before model-output inspection.
5. **Keep the broad and audited evaluations distinct.** Report the full eligible test benchmark against published canonical labels as a silver-reference evaluation. Separately score every model on the same audited subset, before and after reference corrections, with audited CMI. Use the subset as a validity check, not as a population-representative replacement for the full test set.

## CMI and scoring

Use the supplied reference `cmi` for the broad benchmark, retaining its provenance. Audit its implementation if available and compare it with hand-tagged values on the reviewed subset. Never calculate the predictor from model hypotheses, or assume Latin script proves English language identity.

For hand-tagged references, use the [Das and Gambäck utterance CMI](https://aclanthology.org/W14-5152.pdf):

`CMI = 100 * (1 - max(n_ne, n_en) / (n_ne + n_en))`

This excludes language-independent tokens; define CMI as zero if no language-bearing tokens remain, and flag such clips. Write the tagging convention before annotation. Unresolved language labels stay flagged rather than silently becoming Nepali. For two languages the range is 0–50. CMI measures language balance, not switch frequency, and does not distinguish Nepali-majority from English-majority speech. Record the dominant language in the audit.

Use CMI continuously for the main association analysis. For readable plots, propose fixed bands `[0,10]`, `(10,20]`, `(20,30]`, `(30,40]`, `(40,50]`; show clip, word, video, and channel counts. Do not move boundaries after inspecting errors. Flag zero-CMI CS rows, missing/out-of-range CMI, and sparse bands; omit invalid CMI only from CMI analysis, with counts.

Primary WER/CER use canonical mixed-script references. Preserve raw references and hypotheses. Apply the same frozen normalization to both: Unicode NFC, lowercase Latin letters, map Devanagari digits to ASCII, replace Unicode punctuation with spaces, then collapse whitespace. Keep a raw-score sensitivity result because punctuation handling can affect technical terms. Do not transliterate, translate, or delete English words in primary scoring. Define WER tokens by whitespace and CER units by Unicode code points excluding whitespace; CER is not a grapheme error rate.

Aggregate WER as total substitutions + deletions + insertions divided by total reference words; aggregate CER analogously. Do not average utterance WER for the headline score. WER can exceed 100%. Log empty references as reference-quality failures and retain empty model hypotheses as deletions.

For the audited subset, classify English-word errors as plausible transliteration/script change, wrong lexical content, omission, or unclear. Mark suspected hallucinations by listening to the audio; repeated text alone does not establish hallucination. This manual analysis is the minimal script-sensitivity check. Avoid treating a mechanically transliterated score as proof of acoustic correctness.

## Decoding, comparisons, and timing

- Main runs: both Whisper checkpoints use explicit Nepali and `transcribe`; IndicWav2Vec uses greedy CTC decoding without an external language model. Use evaluation mode and deterministic decoding. Resolve and save all generation settings, token limits, dtype, and any inherited checkpoint defaults on validation. Do not truncate a clip silently.
- Diagnostic: on a fixed validation subset spanning CMI, compare automatic language detection with forced Nepali for both Whisper checkpoints. Save outputs and detected language when exposed. This tests the reported Hindi repetition/script behavior without selecting test settings by test score. The [base model card](https://huggingface.co/openai/whisper-large-v3-turbo) documents automatic language detection and explicit language conditioning; neither guarantees mixed-script preservation.
- Report each model's overall and bandwise WER/CER, plus descriptive Spearman association between continuous CMI and utterance WER. For the Whisper pair, analyze the within-clip difference `WER_finetuned - WER_base` against CMI directly; comparing two separate significance labels does not test a difference.
- Inspect channel-specific results and clip length/reference length alongside CMI. Use paired video-cluster bootstrap resampling for model differences and associations when enough videos exist, preserving all models for each sampled clip. Save seed and resampling settings. With few clusters, show descriptive uncertainty and disclose instability. Video-level uncertainty is conditional on these channels; it cannot establish population-wide speaker generalization.
- Time on the same hardware at batch size 1. Exclude downloads, loading, and warm-up. Decode/resample audio before timing; time feature extraction, device transfer, inference, and text decoding with accelerator synchronization. Report corpus RTF = summed timed seconds / summed audio seconds, hardware/software, dtype, and timing boundary. Mark differing execution devices/configurations rather than presenting them as controlled speed comparisons.

If added after the core results, English-token preservation should use aligned, manually identified English reference tokens. Report exact Latin-form retention separately from manually judged lexical preservation across scripts. State the denominator and the CTC vocabulary constraint.

## Deliverables and dates

| Target | Concrete outcome |
| --- | --- |
| October 16–20 | Pin inputs; audit metadata/CMI; freeze protocol and test manifest; check compute availability. |
| October 21–25 | Reproduce Whisper diagnostic on validation; check all three models on a small pilot; finish reference audit before inspecting test predictions. |
| October 26–November 2 | Run the frozen three-model benchmark; save raw predictions, failures, environment, and timing. |
| November 3–8 | Finish CMI plots, paired analysis, audited-reference sensitivity, and error categories. |
| November 9–12 | Write a concise report; rerun scoring from saved predictions; document exact reproduction commands and required checks. |
| November 13–15 | Verify tables/figures against saved outputs and finalize the repository/report. |

The finished repository should contain the protocol, minimal runnable inference/scoring code with meaningful self-checks, exact environment/revision records, evaluation manifests, saved predictions, and a short report. Keep large weights/audio in their source repositories or cache. Respect source attribution and license terms when sharing artifacts.

Completion means the three selected checkpoints have comparable results on a frozen manifest, reference/script limitations are visible, and another person can reproduce the tables from saved predictions. A weak, non-monotonic, or absent CMI association is a valid outcome. No claim about admissions benefit or general superiority of an entire model family follows from this study.
