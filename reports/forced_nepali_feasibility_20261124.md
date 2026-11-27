# Forced-Nepali follow-up: revised plan

**Sanskar Ananta Tiwari** | November 24, 2026 | Planning only

## Selected approach

**Reuse the completed automatic-language outputs. Run only forced Nepali on all 1,198 clips, once locally and once through the API.** No new automatic inference is planned, and no smaller test subset is needed for this design. This supersedes the earlier suggestion to refresh both settings.

The question is straightforward: do the saved automatic transcripts and the new Nepali-specified transcripts differ in word errors, character errors and behavior across CMI bands? The dataset audio, references and clip IDs stay identical.

| System | Existing baseline, reused | Only new main run |
|---|---|---|
| Local Whisper Large V2 | 1,198 automatic outputs | 1,198 outputs with language="ne" |
| Hosted whisper-1 | 1,198 automatic outputs | 1,198 outputs with language="ne" |

The local setting bypasses automatic language selection. The API accepts the input-language parameter language="ne" [1,2]. Both remain transcription tasks: English reference words are neither translated into Nepali nor rewritten to make the score better. All other exposed decoding, prompt and normalization settings stay fixed.

## Budget within the reported $2.29 balance

The checked rate is $0.006 per audio minute [3]. Planning rounds each clip upward to whole seconds; actual provider usage can differ. The pilot is forced Nepali only as well.

| Item | New API requests | Estimated API usage charge |
|---|---:|---:|
| Technical pilot on the existing 20 validation clips | 20 | $0.0190 |
| Forced Nepali on all 1,198 test clips | 1,198 | $1.2556 |
| Total before reserve | 1,218 | $1.2746 |

Adding 20% reserve and rounding upward gives a **$1.53 planning budget**, leaving **$0.76 unallocated** from the user-reported $2.29. The same pilot/main split requires 1,218 new local transcriptions, with no per-request API charge; electricity/hardware costs are not measured. No additional credit is needed at these assumptions. The reserve is not permission to retry uncertain paid requests, and a request cap is not a guaranteed monetary cap.

Current account balance/access/quotas still require preflight; the reported balance was not independently inspected. All 1,198 WAV paths and the cached local model file are present, but payload checksums and GPU readiness were not revalidated in this feasibility task.

## Scientific interpretation

This answers the practical comparison requested. The hosted automatic baseline was collected earlier, so any observed hosted difference could include service/date variability as well as the language setting. Record both dates and keep that limitation in the report. It does not prevent the comparison, require repeating automatic mode, or invalidate the published benchmark. Different scripts alone do not establish different spoken words.

A previous five-clip API pilot already produced identical automatic/Nepali transcripts, with WER 72.97% and CER 48.76% in both modes. A full-set gain is therefore not guaranteed. Identical, worse or mixed outcomes are all reportable; do not stop because results fail to improve.

<!-- pagebreak -->

## What needs to be done

**1. Prepare a separate follow-up protocol and runner condition.** Preserve the original frozen settings, manifests and automatic outputs. New condition-aware fingerprints, output names and checkpoints must identify forced Nepali explicitly. The current runner correctly rejects settings that differ from the original frozen specification; do not bypass those safeguards by editing the old configuration in place.

**2. Pilot, then run forced Nepali only.** Check the existing 20 validation clips in both systems for valid parameters, intact audio and complete saved responses. Then run the fixed 1,198 test clips in both systems with language="ne". Preserve raw responses, request IDs, settings, timing, costs and failures. Set explicit paid request limits and zero automatic retries.

**3. Compare against the saved automatic outputs.** Match by clip ID and reference/audio checksums. Compute corpus WER/CER and forced-minus-auto differences within each system; negative values mean lower error with Nepali specified. Reuse the fixed CMI bands and source-video-within-channel paired bootstrap structure, keeping conditions paired in every draw. Review source composition and show any system difference in the observed setting effect directly. Keep conclusions exploratory because the follow-up was chosen after seeing the original results.

**4. Review examples and publish a versioned addition.** Revisit the same ten preselected clips for omitted words, English rendering, repetition and language mismatch. Keep strict scores primary; old same-word approvals do not automatically validate new candidate word pairs. Add the bounded findings to a new report version, retain the original automatic results and repeat saved-output reproduction/PDF checks before publication.

## Proposed working schedule

Use **6:00-9:00 AM Nepal time**. Plan four sessions, approximately **8-12 hands-on hours**; keep November 29 as buffer. This is a proposed schedule, not a claim that future work is already completed.

| Date | Main work | Deliverable |
|---|---|---|
| Nov 25 | Freeze follow-up design, add safe condition support and offline tests; preflight inputs, credit/access and quotas. | Separate forced-Nepali configuration and validated run plan. |
| Nov 26 | Run the forced-only validation pilot, then forced Nepali locally and through the API on all 1,198 test clips. | Two new complete output sets, or an accounted-for checkpoint. |
| Nov 27 | Verify pairing; compute errors, CMI patterns and uncertainty; review the fixed examples. | Verified comparison tables, figure and bounded notes. |
| Nov 28 | Update the research report/PDF, reproduce the revised analyses and publish the addition. | Versioned revised report and verified public links. |

Previously, one local full run took about 46 minutes of summed generation and one API run about 54 minutes of summed client turnaround. Those are planning references, excluding setup/recovery; forced-language speed and current service limits may differ. Confirm a daily allowance for about 1,200 main API requests, or split the run and use the buffer.

A combined announcement can target **November 28**, three days later than November 25, with November 29 contingency. The already published first phase can still be announced November 25 if preferred.

## Availability and status

Whisper-1 is documented as deprecated, with shutdown scheduled for February 26, 2027 [4]. Account-level availability still needs a preflight check. If access fails, resolve it before changing providers or altering the comparison. No new inference, authentication, paid request, main-report edit or public push was made for this revised plan.

[1] [OpenAI transcription language parameter](https://developers.openai.com/api/reference/python/resources/audio/subresources/transcriptions/methods/create). [2] [faster-whisper v1.2.1 language handling](https://raw.githubusercontent.com/SYSTRAN/faster-whisper/v1.2.1/faster_whisper/transcribe.py). [3] [Whisper pricing](https://developers.openai.com/api/docs/models/whisper-1). [4] [OpenAI deprecations](https://developers.openai.com/api/docs/deprecations). Sources checked November 24, 2026. Calculations and source hashes are retained in results/metrics/forced_nepali_feasibility_20261124.json.
