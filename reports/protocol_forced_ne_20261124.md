# Frozen follow-up protocol: forced Nepali only

Prepared November 24, 2026, after publication/inspection of the automatic-language benchmark and before any new forced-Nepali run. The author selected reuse of all completed automatic outputs and a full 1,198-clip forced-Nepali comparison, with a reported USD 2.29 API balance. This is an exploratory follow-up, not a replacement of the original frozen experiment.

## Fixed inputs and comparisons

Reuse the exact 1,198 clips, WAV payloads, decoded identities, canonical mixed-script references and CMI values from `data/manifests/test_cs_benchmark_20261112.json`. Reuse the two verified automatic prediction files unchanged. Keep the frozen 50-clip reference audit and the ten selected examples. No new automatic inference, reference rewriting, outcome-based exclusions, model training or provider substitution is planned.

Two new main runs: local Large V2 with `language="ne"`, and hosted `whisper-1` with `language="ne"`. Otherwise preserve the original exposed inference settings, model weights/revision and package pins. Task remains transcription. No translation, transcript prompt, vocabulary hint, previous-clip context or output post-editing. Forced-language metadata is not an independently measured language-detection confidence/accuracy.

The machine-readable companion pins both source manifests, both automatic outputs, verification receipts, original protocol/audit, the five-clip pilot archive and this document. Separate forced-Nepali manifests/configuration fingerprints/output names prevent mixing conditions or overwriting automatic runs. Current automatic inputs/settings remain the default in the original runner.

## Technical validation and execution

First use 20 existing validation clips (the original five plus the fifteen additional clips), forced Nepali only in both systems. Validation success checks audio identity, parameter serialization, usable hardware/access and complete response records, not a desired accuracy improvement. Reuse any successful forced pilot response on resume; never silently repeat an uncertain request. Then run all 1,198 test clips in their original fixed order. Do not reduce the test set based on output errors.

Save raw output, condition/configuration, source hashes, dates, request IDs, timings, failures and coverage. Keep lock files during active runs. Persist pending requests before transmission; stop on unresolved or malformed responses and require investigation before any retry. SDK retries remain zero; failed/pending paid requests are not automatically resubmitted. Successful empty transcripts count as deletions, not failed requests. Report failures explicitly and do not create a headline complete-corpus score until coverage is complete.

New paid requests are capped at 20 for the validation manifest and 1,198 for the test manifest, with no repeat of completed clips. At the checked USD 0.006/minute rate and per-clip upward-second planning, main use is USD 1.2556 and pilot use USD 0.0190; USD 1.53 includes 20% reserve and rounding. The balance is user-reported, not independently verified. Request caps are not a monetary guarantee or permission for additional retries. Confirm current model access, credits and quotas before paid execution. Hosted availability is documented through the scheduled February 26, 2027 shutdown, not guaranteed for this account by this protocol.

## Scoring and analysis

Primary: corpus WER; secondary: corpus CER, using the unchanged NFC/lowercase/digit/punctuation/whitespace normalization. Keep raw-score sensitivity and original word/character denominators. Compare each new forced condition with its corresponding saved automatic outputs on identical clip IDs; report forced-minus-auto differences, so negative is lower forced error. Never compare a subset's rate with a different population's rate.

Use the original five CMI bands and descriptive continuous CMI context. For exploratory paired uncertainty use 2,000 source-video resamples within each channel, seed 42, keeping all system/condition observations of a sampled video together. Report counts/denominators, interval scope and high-CMI uncertainty. Estimate the between-system difference in the observed forced-minus-auto change directly; different individual interval labels alone are not evidence of an interaction. Use the same 50-clip published/corrected-reference sensitivity if feasible. No new confirmatory causal hypothesis or population-generalization claim is made.

Review the same ten preselected examples for changed English rendering, missing words, repetition and perceived language mismatch. Keep strict metrics primary. New tolerant equivalences require separately documented listening and cannot be invented from spelling similarity; expanded tolerant scoring is optional, not a prerequisite for this extension.

## Limits and release

Automatic and forced API runs occur on different dates; observed hosted changes may include provider/service variability as well as the language parameter. Record this rather than claim that every difference is caused solely by forcing Nepali. Local execution can also vary despite fixed parameters. Prior five-clip API outputs were identical across settings, so improvement is not guaranteed; null, mixed and worse results remain publishable.

Keep the original v0.5 report and all baseline artifacts intact. New results, paired analysis and any report revision receive separate dated/versioned records. Reproduce from saved outputs and review the final PDF before another public update. Writing this protocol performs no model inference, authentication or paid request.
