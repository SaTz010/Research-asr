# Nepali-English code-switched ASR: general and specialized Whisper systems

An independent empirical study by **Sanskar Ananta Tiwari**. The question is whether more balanced Nepali-English mixing is associated with transcription errors, and how three configured Whisper systems compare on exactly the same audio.

**Revised report v0.6 (November 27):** [Download the PDF](output/pdf/nepali_english_asr_research_report_draft.pdf) or read the [editable report](reports/research_report_draft.md). The report has a cover, clickable contents, plain-language summary, references and three appendices. Start on page 3 for the general-reader explanation. This is a working technical report, not a peer-reviewed publication.

**Publication status:** v0.5 was published on GitHub November 24, 2026 ([historical verification](reports/github_publication_20261124.md)). The expanded v0.6 report is a local revision; it has not been pushed by this revision workflow. The [dated v0.5 PDF](output/pdf/nepali_english_asr_research_report_draft_v0.5_20261124.pdf) and [source](reports/research_report_draft_v0.5_20261124.md) are preserved.

## Main results

All three primary systems completed all **1,198 frozen code-switched test clips**: 199.01 minutes, 22 videos and two source channels from [Sailesh Dahal's Nepali-English Code-Switched ASR dataset](https://huggingface.co/datasets/saileshbro/nepali-cs-asr). Exact revision, source attribution and license are in [DATA_SOURCES.md](DATA_SOURCES.md).

| System | Corpus WER | Corpus CER |
|---|---:|---:|
| Local Whisper Large V2, faster-whisper CUDA FP16 | 90.95% | 69.60% |
| Hosted OpenAI whisper-1, automatic language | 96.41% | 73.39% |
| Code-mix-specialized Large V3 Turbo, Nepali specified | 25.94% | 18.42% |

Lower is better. WER/CER measure agreement with published mixed-script silver references, not semantic accuracy. WER counts changed, missing and added words and can exceed 100%.

- **CMI versus utterance WER is nearly unassociated:** Spearman rho +0.0093 local, +0.0109 hosted and -0.0277 specialist. The results do not confirm a simple steady increase in word errors with mixing intensity.
- **Character errors show a stronger pooled association:** rho +0.2698 local and +0.2514 hosted, with substantial channel variation. The specialist association is near zero (+0.0066).
- **The local-minus-hosted corpus gap is -5.46 percentage points WER**, exploratory paired video-bootstrap interval [-9.79, -2.31]. Higher-CMI comparisons have wider intervals. These are conditional summaries of the observed sources, not causal hosting effects or universal model rankings.
- **Large observed specialist advantage:** WER is 65.01 percentage points below original local (paired interval [-68.77, -59.76]) and 70.47 below hosted ([-73.31, -67.05]). Training exclusion remains unverified: the result is exploratory, not confirmed unseen-data superiority or an isolated fine-tuning effect. The original local/API systems share a Large V2 foundation.
- **A separate 50-clip reference audit** retained 42 references and corrected eight. Its population, denominators and sensitivity results remain separate from the main benchmark.
- **A post-hoc ten-clip variant analysis** reduces WER from 80.00% to 69.19% local and 103.78% to 89.73% hosted under 31 reviewed same-word allowances. Six doubtful equivalences are excluded. It does not estimate corpus-wide spelling-error prevalence or the percentage of genuinely wrong spoken words.

Full tables, uncertainty, timing/cost scopes, single-reviewer limits and references are in the report. The project compares configured general and specialized systems. It performs no model training or translation and does not identify a causal hosting or fine-tuning effect. The [overlap audit](reports/codemix_training_overlap_audit_20261127.md) records clean source splits, 411 candidate matches to the authors' public test outputs and unresolved actual training membership.

## Reproduce without audio, keys or paid calls

**Forced-Nepali follow-up (November 24):** Both systems completed and independently verified all 1,198 clips with `language="ne"`, reusing the automatic outputs above. Local WER changes from 90.95% to 91.13%; API WER from 96.41% to 97.12%. Both paired overall WER intervals span zero, so these small observed increases do not establish a reliable direction of change. See the [separate comparison, CMI groups and uncertainty](reports/forced_ne_comparison_20261124.md) and [frozen follow-up protocol](reports/protocol_forced_ne_20261124.md). The original v0.5 PDF remains archived. Version 0.6 includes this language-setting sensitivity and the specialist results, without inventing new listening judgments or tolerant allowances.

The expanded saved-output check replays six analysis JSONs, offline tests and the revised PDF from saved records in an isolated working copy. See [REPRODUCING.md](REPRODUCING.md) for the verified environment, commands and limits.

```powershell
py -3.13 -m venv .cache\reproduction-env
.\.cache\reproduction-env\Scripts\python.exe -m pip install -r requirements-reproduction-lock.txt
.\.cache\reproduction-env\Scripts\python.exe src/reproduce_results.py
```

Installation needs package-index access; replay itself blocks network connections. It requires neither source WAVs nor model weights. The verified target is Windows/CPython 3.13; report rendering uses Windows Arial. This is a saved-output reproduction, not a rerun of the local/API inference or an independent listening audit. The PDF uses the regenerated specialist CMI chart and an included original uncertainty chart; the analysis charts are regenerated.

Evidence for the original publication remains in the [November 24 fresh-environment check](results/metrics/clean_reproduction_20261124.json). The revised report's checks are recorded separately in [v0.6 verification](results/metrics/report_revision_v06_20261127_verified.json); historical v0.5 publication checks do not certify v0.6 release or training exclusion.

## Repository guide

| Location | Contents |
|---|---|
| `configs/` | Frozen settings, protocol and dated rates. |
| `data/manifests/` | Clip identities, references, source version and input checksums. |
| `data/annotations/` | Frozen 50-clip audit, ten-example reviews and variant decisions/history. |
| `results/predictions/` | Saved model responses and historical development-pilot exports. |
| `results/metrics/` and `results/figures/` | Scores, paired uncertainty, figures and verification records. |
| `src/` and `tests/` | Inference, review, analysis, report and offline-reproduction code/tests. |
| `notebooks/` | Development and listening-review workflows; embedded playback outputs removed. |
| `reports/` and `output/pdf/` | Current report, dated prior versions, protocol and progress records. |

The original benchmark uses Large V2 and whisper-1; the exploratory extension uses `ailabpvtltd/whisper-large-v3-turbo-nepali-english-codemix-asr`. Earlier Turbo/precision/Google pilot exports are historical development evidence and are not pooled with the held-out benchmark. The original inference environment remains specified in `requirements-local*.txt` and `requirements-api.txt`; the reproduction environment does not replace those frozen inference pins. `.env`, private caches, audio/video and downloaded weights are excluded. Original notebook outputs were backed up locally before publication cleanup; saved human judgments remain in the annotation JSONs.

## Scope, status and credit

The source is narrow educational speech from two channels; references are mainly silver labels and review uses one researcher. Code-mixing balance is not switch frequency, and script-derived source CMI is an imperfect language-identity measure. All six uncertain word equivalences remain explicit. No peer review, DOI, institutional endorsement or exhaustive novelty claim is implied.

This repository provides the checked research package, saved-output reproduction instructions and a revised v0.6 working report with its archived v0.5 predecessor. The report is not peer reviewed; its preparation-stage status notes are retained as part of the research record. The author supplied the research and listening/reference/language judgments; an AI coding assistant supported implementation, arithmetic checks, drafting and formatting, without independently hearing the audio.

Original code is [MIT-licensed](LICENSE); original report text and figures are [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), as selected by the author. Dataset-derived transcripts retain CC BY-NC 4.0 terms and are excluded from those grants. See [LICENSING.md](LICENSING.md), [DATA_SOURCES.md](DATA_SOURCES.md) and [CITATION.cff](CITATION.cff).
