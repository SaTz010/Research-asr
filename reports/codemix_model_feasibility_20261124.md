# Feasibility of a Nepali English code mixed Whisper model

**Sanskar Ananta Tiwari · November 24, 2026 · Separate exploratory study**

The proposed model is a plausible candidate for a small local pilot on this laptop. A full accuracy benchmark should follow only after its training split is checked against our evaluation clips. The published research, PDF and GitHub remain unchanged.

## Model and relevance

The exact repository is [ailabpvtltd/whisper-large-v3-turbo-nepali-english-codemix-asr](https://huggingface.co/ailabpvtltd/whisper-large-v3-turbo-nepali-english-codemix-asr). Its authors fine-tuned Whisper Large V3 Turbo for mixed Nepali-English transcription. It targets Devanagari Nepali with Latin English, unlike the English transliteration we observed in earlier pilots. The authors report 16.4% WER versus 121.5% for their base Turbo model on their own evaluation. These are external results, not predictions for our 1,198 clips. The release is CC BY-NC 4.0. [Pinned model card](https://huggingface.co/ailabpvtltd/whisper-large-v3-turbo-nepali-english-codemix-asr/blob/8eff5c489628694a9f3ff2a02f3225ccfd6c6046/README.md).

## Hardware and software

| Item | Checked finding | Implication |
|---|---|---|
| Model weights | 808,878,080 parameters; BF16 safetensors; 1,617,825,448 bytes, about 1.51 GiB | Download is substantially smaller than the cached Large V2 weights. Weight size alone does not establish peak GPU memory. |
| Architecture | Standard Whisper, 32 encoder layers, four decoder layers, 128 mel bins | A supported Whisper inference path is appropriate; avoid mixing in the Large V2 feature-extraction settings. |
| GPU | RTX 3060 Laptop, 6 GiB VRAM; about 4.42 GiB free at the check | Batch-one inference in a 16-bit format is plausible. Actual peak memory and numerical stability require a pilot. |
| Disk | About 115.8 GiB free | Adequate for a separate environment, weights and a converted copy if needed. |
| Existing environment | faster-whisper 1.2.1 and CTranslate2 4.8.5; no PyTorch, Transformers, Accelerate or safetensors | Preserve this environment. Install any new dependencies in a separate environment. |
| Existing audio | All 1,198 clips are 16 kHz; longest is 14 seconds | The existing WAV inputs fit a short-form pilot; no new segmentation is needed. |

Sizes, architecture and stored tensor types come from the [Hub metadata](https://huggingface.co/api/models/ailabpvtltd/whisper-large-v3-turbo-nepali-english-codemix-asr?blobs=true) and [pinned configuration](https://huggingface.co/ailabpvtltd/whisper-large-v3-turbo-nepali-english-codemix-asr/blob/8eff5c489628694a9f3ff2a02f3225ccfd6c6046/config.json). Hardware and installed-package observations are recorded in the [local feasibility receipt](../results/metrics/codemix_model_feasibility_20261124.json).

The saved model configuration declares float32 although the stored weights are BF16. Choose the inference dtype explicitly rather than assuming the default will use half precision. Start with FP16 batch one, record the actual dtype, and inspect for invalid/repetitive outputs. If that proves unstable, investigate BF16 support in the selected backend. The configured `use_cache` is false; any inference override should be recorded and applied consistently to both models.

The simplest initial path is the standard [Transformers Whisper implementation](https://huggingface.co/docs/transformers/model_doc/whisper), loading only safetensors and keeping remote custom-code execution disabled. Pin the processor, tokenizer and weights to the same revision. A second option is conversion to CTranslate2 followed by faster-whisper; both projects document Whisper conversion, but this exact checkpoint has not been converted or tested here. Conversion adds a parity check and should not be assumed to reproduce Transformers output exactly. [CTranslate2 conversion](https://opennmt.net/CTranslate2/guides/transformers.html#whisper), [faster-whisper conversion](https://github.com/SYSTRAN/faster-whisper#model-conversion).

## The main scientific condition

The authors list 44.5 training hours from **saileshbro/nepali-cs-asr**, our source dataset. Their training records are not released with this checkpoint, and they note that their own test split is not guaranteed to be speaker-disjoint. [Training and limitations](https://huggingface.co/ailabpvtltd/whisper-large-v3-turbo-nepali-english-codemix-asr#training-data).

Using the same dataset for training and evaluation is legitimate when the splits are disjoint. The shared name is therefore a reason to investigate, not proof of leakage. We need the dataset revision/configuration and training clip IDs or source-video/channel IDs, including any augmented derivatives. Compare them with our exact 1,198 identities and 22 videos. The source dataset's documented split rules alone do not establish which revision or split this model's authors used. [Source dataset evaluation protocol](https://huggingface.co/datasets/saileshbro/nepali-cs-asr#evaluation-protocol-v2).

If disjointness is confirmed, the existing benchmark can support an additional held-out comparison. If overlap remains unresolved, a pilot can still demonstrate whether the model runs and how it formats output, but label its scores as exploratory with unknown training overlap. A stronger generalization study would need independently collected or demonstrably excluded recordings. Do not discard difficult clips or change the original test population after seeing results.

## Comparison design

Keep all current Large V2 and whisper-1 outputs unchanged as contextual baselines. For an interpretable specialization comparison, also run **the unfine-tuned OpenAI Large V3 Turbo** using the same backend, precision, audio, decoding and reference handling as the proposed model. A comparison only with Large V2 would mix a model-generation change with fine-tuning and implementation changes.

Use a separately dated protocol and separate outputs. Start with Nepali specified, transcription task, deterministic greedy decoding, no transcript prompts and one clip at a time, matching settings across the two Turbo systems. Retain raw outputs, token/configuration choices, runtime, peak memory, failures and checksums. This settings choice belongs to the new experiment and must not replace the old benchmark's beam-five setup.

Score the original references with the existing primary WER/CER normalization and fixed CMI bands. Preserve raw-score sensitivity and the audited 50-clip comparison. The proposed model spells numbers and symbols as words and uses NFKC text normalization, so differences from the existing reference convention need inspection rather than silently rewriting the primary labels. [Output convention](https://huggingface.co/ailabpvtltd/whisper-large-v3-turbo-nepali-english-codemix-asr#output-format).

Freeze the design before new inference, report corpus edits and denominators, and use paired video resampling within channels. Better script agreement would be useful, but it would not by itself prove better understanding, a causal hosting effect or a universal CMI trend.

## Suggested pilot and effort

1. **First morning, about two to three hours:** verify split provenance where possible, create the separate environment, pin both Turbo revisions and download only required files. Run five validation clips to check loading, precision, language handling and output preservation. Installation/download time depends on connectivity.
2. **Second morning, about two to three hours:** finish the existing twenty-clip validation pilot for both Turbo systems. Inspect mixed-script output against audio, measure peak VRAM and real-time factor, and lock settings. A low WER is not a requirement for reporting the pilot.
3. **Third morning, about two to three hours if the pilot and provenance permit:** run the full fixed test set, verify coverage/counts, then produce the CMI and paired uncertainty comparison. Report preparation or unresolved provenance can extend this schedule.

These are planning allowances, not measured runtimes. The corpus contains 199.01 minutes of audio. A measured real-time factor of 0.1, 0.2 or 0.5 would imply about 20, 40 or 100 minutes of inference **per model**, before loading, saving and verification. Measure this in the pilot rather than assuming Turbo will match a published speed claim.

Local execution needs no OpenAI API credit or paid transcription calls. Downloads, electricity and hardware use remain local costs. No weights, package installations, conversion or inference were performed for this feasibility study; the downloaded files were small public metadata/configuration files only.

**Decision:** proceed with a separate technical pilot if desired. The machine looks capable; the unresolved training/evaluation relationship is the main condition for a defensible accuracy claim. Keep this experiment outside the published research until that condition and the pilot are resolved.
