# Version 1 design — local versus hosted Whisper

Decision date: November 3, 2026. Research package target: November 24; LinkedIn announcement: November 25. This scope supersedes the earlier API-only proposal. Google is an optional later extension, not a dependency for version 1. Historical outputs remain unchanged.

## Research question

How is reference code-mixing intensity associated with transcription errors in a local OpenAI Whisper deployment and the hosted OpenAI Whisper API on the same Nepali–English speech clips? What practical accuracy, request-turnaround, hardware and usage-cost tradeoffs are observed?

This is a system comparison. It cannot isolate hosting as the cause of accuracy differences, establish that CMI causes errors, or claim to compare identical full decoding pipelines.

## Systems

| Priority | System | Role |
|---|---|---|
| Required | Local Whisper `large-v2`, using the faster-whisper/CTranslate2 runtime | OpenAI model weights executed on this laptop. Start validation with FP16 and batch size one; measure actual memory/runtime. Pin model revision, runtime and dependencies before test inference. |
| Required | OpenAI API `whisper-1` | Hosted Whisper V2-family comparator. Existing five-clip API pilot can be reused if the exact request settings and submitted audio are retained. |
| Optional | OpenAI API `gpt-transcribe` | A distinct modern hosted-system comparison only after the two-system core is feasible. Include in the main evaluation only if piloted and selected before inspecting test outputs; otherwise use a separately labelled follow-up. |
| Deferred | Google `chirp_3` | Preserve the partial pilot and errors; revisit after the core package is complete. It is not required for the November 25 announcement. |

[Official OpenAI documentation](https://developers.openai.com/api/reference/resources/audio/subresources/transcriptions/methods/create) identifies `whisper-1` as powered by open-source Whisper V2. Local `large-v2` is therefore the proposed closest published generation/family match, rather than assuming the previous V3 Turbo is the API's checkpoint. Exact API weights/revision, preprocessing and decoding are not exposed. Faster-whisper is a separate implementation of Whisper, not a different model creator; implementation and precision remain possible confounders. The [API reference](https://developers.openai.com/api/reference/resources/audio/subresources/transcriptions/methods/create) lists a February 26, 2027 shutdown date for `whisper-1`; retain dated raw responses and disclose that future API reruns may be unavailable.

The [GPT-Transcribe model page](https://developers.openai.com/api/docs/models/gpt-transcribe) documents the optional hosted model; it is not a downloadable equivalent of the proposed local Whisper model. Do not label a GPT-versus-Whisper result as the same model running in two places.

## Hardware checked on November 3

- Laptop: HP OMEN 16-b0xxx.
- Processor: Intel Core i7-11800H, 8 cores / 16 logical processors.
- Installed RAM: approximately 16 GB.
- GPU: NVIDIA GeForce RTX 3060 Laptop GPU, **6144 MiB VRAM**, confirmed by `nvidia-smi`; do not use the truncated Windows AdapterRAM field to infer capacity.
- NVIDIA driver: 592.27.
- C: free space at inspection: approximately 121 GiB; this can change.

Hardware suggests feasibility, not a completed benchmark. The [faster-whisper project](https://github.com/SYSTRAN/faster-whisper) reports lower-memory Whisper execution and supports GPU FP16 and INT8. Its published memory measurements use a different GPU and do not guarantee this laptop's memory use or speed. Check CUDA/cuDNN runtime requirements in the isolated project environment. Do not replace system drivers or global Python to make the experiment work.

If batch-one FP16 cannot run reliably, test a documented INT8 configuration on validation; record quantization as part of the local system and freeze it before test inference. If local setup remains blocked by November 6, use a clearly disclosed GPU execution environment such as Colab for the downloadable-model condition, or revise sample size. Colab execution is not evidence of this laptop's performance. Hardware/software substitutions must be decided before test outputs, not chosen for better scores.

## Minimum reproducible experiment

1. Install an isolated local runtime and recover the same five original validation clips. Verify identity and hashes; preserve original API outputs. Measure model load time, peak GPU memory, elapsed transcription time and failures. Test both ordinary output and empty/failed-output handling.
2. Freeze the local model/revision, runtime/precision, and decoding fields. Primary language handling remains automatic with no reference-derived prompt. Use independent clips, transcription rather than translation, and no hypothesis post-editing. Optional forced-Nepali checks are validation diagnostics; do not add an unplanned full-set condition.
3. Keep the existing eligibility/manifest plan: prefer all eligible CS test clips; choose any deterministic fallback before inference. Review 50 reference/CMI examples before seeing test predictions. Save canonical and corrected references separately.
4. Run the two required systems on the identical frozen audio set. Retain raw hypotheses, request/configuration metadata, audio/payload hashes, failures, checkpoints and API usage. A successful empty transcript counts as deletions; an API/compute failure is a separate coverage event, not an invented 100% WER score.
5. Recompute corpus WER/CER with the same frozen mixed-script normalization; analyse continuous CMI and the five fixed bands, with counts and paired model differences. Report published-reference results and audited-reference sensitivity separately. Include length/channel/video limitations and bounded script-error examples.
6. Measure local model-load time separately from transcription latency. Record completed local transcription time and API request turnaround from the same client machine; API time includes upload/network/queue/service/transfer. These are deployment measurements, not matched GPU compute benchmarks. Synchronize GPU timing where needed and materialize streamed/generator outputs before stopping the clock.
7. Report API usage charges alongside local hardware/runtime requirements. Local inference has no per-request API fee but is not zero-cost: electricity, hardware, setup and model download are not included unless actually measured. No unsupported energy or total-cost claims.

## Earlier work and release boundaries

The V3 Turbo/precision ZIPs remain valid historical development evidence and are not re-labelled as local Large V2 results. Their audio was processed in Colab, not on this laptop. The Whisper API ZIP stays useful for the new five-clip local validation pairing; no extra API request is needed merely to compare the saved hypotheses. Google pilot outputs and both failures remain archived rather than being removed because they were inconvenient.

Version 1 is complete when the local-versus-Whisper-API comparison has frozen inputs/settings, transparent coverage, verified WER/CER and CMI analyses, reviewed references, a concise report and a reproducible repository. A later Google study should preserve version 1 and document its new run date, configuration and any added analysis; it must not silently change the original results.

The initial design/hardware check did not install a model or make paid calls. Subsequent work on November 3 completed the real five-clip FP16 GPU pilot; see the [progress log](progress_20261103.md) and [independent scores](../results/metrics/local_whisper_large_v2_pilot_verified.json). Wider validation/full-test feasibility and current API credits still require checks. Google remains deferred, and no new paid API request was needed for the local pilot.
