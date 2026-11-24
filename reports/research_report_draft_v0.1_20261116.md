# Code Mixing and Transcription Errors in Nepali English Speech

## A paired evaluation of local and hosted Whisper

**Sanskar Ananta Tiwari** | Independent research project

Working draft v0.1 | November 16, 2026 | Not peer reviewed

**Status:** Both 1,198-clip inference runs and descriptive analyses are complete. Paired video-cluster uncertainty, listening-based error examples and final release verification remain unfinished. This document is a review draft, not the final public release.

## Abstract

This study examines whether reference code-mixing intensity is associated with transcription errors in Nepali-English speech and whether two configured Whisper systems exhibit different patterns. A frozen evaluation set contains 1,198 code-switched test clips, totaling 199.01 minutes, from 22 videos and two source channels in the saileshbro/nepali-cs-asr dataset. Local Whisper Large V2, executed through faster-whisper with CUDA FP16, and the hosted OpenAI whisper-1 service transcribe identical audio with automatic language handling. Evaluation uses corpus word error rate (WER), character error rate (CER), five fixed Code-Mixing Index (CMI) bands and descriptive Spearman associations. Against published mixed-script silver references, local WER/CER are 90.95%/69.60%, compared with 96.41%/73.39% for the hosted system. Clip-level CMI-WER associations are near zero for both systems (rho 0.0093 and 0.0109). CMI-CER associations are positive (0.2698 and 0.2514), but differ substantially by source channel. A separate, single-reviewer 50-clip audit checks reference and lexical-CMI sensitivity. These descriptive results show that the relationship depends on the error metric and source composition; they do not establish that increasing mixing causes more errors or that hosting causes system differences. Uncertainty estimation is pending.

## 1 Research question and contribution

The practical question is whether speech containing more balanced Nepali and English word use is harder for the evaluated recognizers to transcribe under a fixed mixed-script convention. The study also asks whether the observed pattern differs between a locally executed Whisper system and a hosted Whisper service. The target is an empirical comparison of existing systems, without new training, translation or application development.

The contribution is a reproducible paired benchmark on a pinned dataset revision, with explicit coverage, fixed settings, saved responses, source-aware analysis and a human-reviewed diagnostic subset. No claim of being the first Nepali-English ASR study, of improving a model, or of peer-reviewed publication is made. A weak or absent association is an informative outcome.

<!-- pagebreak -->

## 2 Background and related work

Whisper studies multilingual speech recognition using large-scale weak supervision [1]. Its multilingual scope motivates evaluation on mixed Nepali-English speech, but multilingual training alone does not establish performance on this dataset or its transcription convention.

Das and Gamback introduce a token-based code-mixing index in work on word-level language identification [2]. Gamback and Das subsequently investigate corpus-level comparisons of code-switching [3]. The present study uses a bilingual token-balance CMI, rather than treating it as a count of language alternations. It does not use the later corpus-level measure as an interchangeable definition.

Transcription conventions are particularly relevant when languages use different scripts. Emond and colleagues discuss evaluation distortions from rendering variation and propose transliteration-optimized WER [4]. PolyWER similarly studies evaluation that accepts alternative cross-script renderings [5]. These studies motivate caution in interpreting mixed-script WER. This benchmark retains its frozen WER/CER definitions; it does not implement either alternative metric or translate hypotheses to improve scores.

This report therefore separates three issues: observed recognition-system output, agreement with a particular reference spelling/script convention, and the reliability of the reference and CMI labels. The measured error rates combine these issues; a listening-based categorization has not yet quantified their individual contributions.

## 3 Dataset and evaluation population

The source is Sailesh Dahal's Nepali-English Code-Switched ASR dataset [6], default configuration, revision `dd00ca41dd38774cd6097c372c16939d7f3746df`. The pinned card describes educational STEM/CS speech from public YouTube videos, mixed-script canonical transcripts, channel-disjoint splits and predominantly silver labels. The benchmark uses published `transcription`, not the fully Devanagari or fully romanized derivatives. Current dataset revisions must not silently replace this pinned revision.

| Population property | Value |
|---|---:|
| Published test rows in the default configuration | 1,765 |
| Candidates with stored speech_type equal to cs | 1,201 |
| Excluded before inference for missing source provenance | 3 |
| Frozen eligible paired clips | 1,198 |
| Audio duration | 11,940.723 seconds / 199.01205 minutes |
| Source videos / source channels | 22 / 2 |
| Normalized reference words / characters | 28,216 / 111,262 |

No clip was removed because of its transcription score. The field `speaker_id` identifies a YouTube channel, not a verified individual speaker. The test set is narrow in domain and source coverage. Channel-disjoint dataset partitions do not establish that the pretrained models never encountered related public audio.

<!-- pagebreak -->

## 4 Experimental methods

### 4.1 Frozen paired systems

Inputs, references and protocol were frozen before held-out inference, completed November 14 locally and November 16, 2026 remotely. Both systems received identical ordered WAVs without reference hints.

| Setting | Local system | Hosted system |
|---|---|---|
| Model identifier | Systran/faster-whisper-large-v2 | OpenAI whisper-1 |
| Execution | faster-whisper / CTranslate2 | Audio transcription endpoint |
| Language handling | Automatic detection | Language parameter omitted |
| Decoding exposed to researcher | Beam 5, temperature 0 | Temperature 0, verbose_json |
| Context and prompting | No prior-text conditioning or prompt | No prompt |
| Precision and execution | CUDA FP16, batch 1 | Provider managed |
| Automatic retries | None | SDK retries 0 |

SYSTRAN documents the local implementation [7]. OpenAI describes whisper-1 as V2-based and documents temperature fallback [8]. Hosted weights, preprocessing and decoding are unavailable; this configured-system comparison cannot isolate a causal hosting effect.

The local machine has an i7-11800H, approximately 16 GB RAM and an RTX 3060 Laptop GPU with 6,144 MiB memory. The protocol/manifest record model revision, weight checksum and software pins. A checkpoint-write interruption was recovered with responses preserved; independent verification required no repeated inference.

### 4.2 Scoring

Primary corpus WER sums substitutions, deletions and insertions over total reference words. Secondary CER uses character edits. These corpus-weighted totals are not mean utterance rates. Insertions allow WER above 100%.

Normalization applies Unicode NFC, lowercasing, Devanagari-to-ASCII digits, punctuation-to-space conversion and whitespace collapse. CER excludes spaces and counts code points, not grapheme clusters. No translation or wholesale script conversion is applied. Raw case/punctuation-sensitive scores are retained.

### 4.3 CMI and analysis

For the human lexical audit, CMI = 100 x min(N_ne, N_en) / (N_ne + N_en), excluding language-independent tokens. Eight Nepali and two English tokens give CMI 20; five of each give 50. Zero indicates a single assigned language. CMI measures balance, not switch frequency or necessarily English dominance.

The full benchmark uses the source's published script-derived CMI. Five fixed bands are [0,10], (10,20], (20,30], (30,40], (40,50]. Descriptive Spearman correlations relate CMI to utterance error rates and paired local-minus-hosted WER. Positive paired differences mean more local error. Channel, video and duration summaries check composition; no causal adjustment or significance test is claimed.

<!-- pagebreak -->

## 5 Results

### 5.1 Coverage and overall errors

Both systems have 1,198 successful saved responses and complete paired coverage. The hosted run used 1,198 attempts and distinct request IDs, with no unresolved requests. Eleven local and one hosted responses are empty successful hypotheses; their deletion errors remain in the scores.

| System | Word edits | Corpus WER | Character edits | Corpus CER |
|---|---:|---:|---:|---:|
| Local Large V2 | 25,663 | 90.95% | 77,443 | 69.60% |
| Hosted whisper-1 | 27,204 | 96.41% | 81,657 | 73.39% |

The observed API-minus-local gaps are 5.46 percentage points WER and 3.79 points CER. Local has lower measured corpus errors on this pool. This is not an accuracy percentage or a population-wide superiority claim. Raw WER/CER are 93.75%/71.61% local and 98.76%/75.37% hosted. The high primary rates warrant examining recognition and reference/script agreement before assigning causes.

### 5.2 Fixed CMI bands

| CMI band | Clips | Videos | Words | Local WER | API WER | Local CER | API CER |
|---|---:|---:|---:|---:|---:|---:|---:|
| [0,10] | 199 | 15 | 4,478 | 90.22% | 93.61% | 61.03% | 63.24% |
| (10,20] | 360 | 19 | 7,975 | 90.92% | 95.15% | 64.85% | 68.32% |
| (20,30] | 286 | 20 | 7,217 | 90.91% | 94.22% | 72.14% | 72.55% |
| (30,40] | 230 | 20 | 5,843 | 90.72% | 98.22% | 74.82% | 78.82% |
| (40,50] | 123 | 22 | 2,703 | 92.86% | 106.73% | 78.16% | 93.68% |

![Corpus error rates across the five fixed published CMI bands](../results/figures/research_report_cmi_bands_20261116.png)

Figure 1. Corpus errors against published silver references. Points connect ordered bands for readability. No confidence intervals are shown. Local WER is mostly flat; hosted WER is nonmonotonic, with its highest rate in the final band. CER rises across bands for both systems.

<!-- pagebreak -->

### 5.3 Continuous associations and source composition

| Utterance-level association | Spearman rho |
|---|---:|
| CMI versus local WER | +0.0093 |
| CMI versus hosted WER | +0.0109 |
| CMI versus local-minus-hosted WER | -0.0204 |
| CMI versus local CER | +0.2698 |
| CMI versus hosted CER | +0.2514 |
| CMI versus duration | +0.0236 |
| CMI versus normalized reference-word count | +0.0533 |

The predeclared word-error associations are near zero. This does not rule out nonlinear relationships, subgroup patterns or effects hidden by noisy measurement. A higher final-band corpus rate is compatible with near-zero utterance rank correlation: corpus rates weight by reference length, while rank correlation describes ordering across individual clips.

| Source summary | Channel A | Channel B |
|---|---:|---:|
| Clips / videos | 608 / 3 | 590 / 19 |
| Mean published CMI | 16.85 | 29.50 |
| Local WER / hosted WER | 89.09% / 95.09% | 92.59% / 97.58% |
| CMI-local WER rho | -0.0169 | -0.0535 |
| CMI-hosted WER rho | -0.0080 | -0.0503 |
| CMI-local CER rho | +0.2891 | +0.0452 |
| CMI-hosted CER rho | +0.3048 | +0.0145 |

Channel A is UChx9-bynjfm6Js3k54Sf1Mg; Channel B is UCy-Q66KQYSQAUVKvdNxgKbw. The positive pooled CER associations are not uniform across sources. Channel A retains a clearer positive CER pattern, while Channel B's CER correlations are near zero. Both source composition and within-source differences matter to interpretation.

Duration has little pooled association with CMI. Duration-WER correlations are -0.0935 local and -0.1246 hosted. Descriptive duration quartiles use cutpoints 8.608, 9.872 and 11.552 seconds, with tied observations in the lower group. Shortest-quartile WER is 93.88% local / 100.93% hosted, compared with 90.19% / 92.15% in the longest quartile. These summaries are contextual checks, not adjustment for duration, source, speaker or audio quality.

The saved analysis also contains all 22 video summaries, band compositions and distribution statistics. Treating 1,198 related clips as independent draws would overstate the breadth of evidence. Paired video-cluster uncertainty is the next planned analysis, not a completed result in this draft.

<!-- pagebreak -->

### 5.4 Human reference and lexical CMI sensitivity

A frozen diagnostic subset contains 50 clips, ten per published CMI band, spanning 18 videos and both channels. One researcher listened to each selected clip, checked script-suggested language tags and saved the reference/tag decisions before held-out prediction inspection. The assistant checked validation and arithmetic, without independently listening. No inter-annotator agreement is available.

Forty-two references were retained and eight corrected. Comparing published text to the human version gives 18 normalized word edits over 979 human-reference words, or 1.84% reference-disagreement WER. This measures disagreement in the selected subset, not the dataset-wide reference error rate. The published-reference denominator for these clips is 974 words.

| Same 50 saved hypotheses | Published WER | Corrected WER | Published CER | Corrected CER |
|---|---:|---:|---:|---:|
| Local Large V2 | 100.82% | 100.41% | 76.30% | 75.83% |
| Hosted whisper-1 | 94.66% | 94.18% | 80.63% | 80.19% |

Local word edits change from 982 to 983; hosted word edits remain 922. The reference denominator increases from 974 to 979. Thus lower rates do not mean improved hypotheses or fewer edit operations. The subset's word-error ranking differs from the full pool's; its balanced selection is not population-representative and cannot replace the full benchmark.

Ten audited CMI values differ beyond a +/-0.005-point source-rounding allowance, and four clips change bands. Audited counts become 11, 8, 10, 13 and 8. CMI differences can reflect reference edits, tokenization, denominator conventions and language judgments. They must not be attributed exclusively to tag overrides.

Using published references/source CMI, subset CMI-WER rho is -0.0197 local and -0.1347 hosted. Using corrected references/lexical CMI, it is +0.0104 and -0.1669. Both definitions change together in this sensitivity comparison. The small single-reviewer subset does not identify a causal explanation or validate all remaining silver labels.

### 5.5 Timing and usage

The summed completed local transcription time is 45.57 minutes; summed hosted client request turnaround is 53.72 minutes. These scopes differ: local records materialized generation, while hosted includes network and service turnaround. Neither is complete workflow wall time; local excludes model loading and checkpoint recovery. No matched-hardware speed or total economic-cost claim follows.

Provider-reported main-run usage is 12,549 audio seconds, or 209.15 minutes. The saved November 16 rate of USD 0.006 per minute gives an estimated USD 1.25490 usage charge. Invoice, taxes, balance and unrelated account usage were not verified. Largest observed whole-device GPU memory is 5,200 MiB; one snapshot is missing and continuous model peak/energy were not measured.

<!-- pagebreak -->

## 6 Discussion and limitations

The results do not support a simple monotonic increase in utterance WER as reference CMI rises in this pool. At the same time, band-level CER increases and positive pooled CMI-CER correlations indicate a metric-dependent pattern. The hosted system's highest-CMI corpus WER is elevated, but neither the paired-difference correlation nor the source-specific summaries supports reducing the finding to a universal degradation slope.

The measured task is agreement with a mixed-script reference convention. Script-derived language labels also enter the source CMI. Language identity and writing system are not equivalent: borrowed words, names and transliteration can change string agreement without a proportionate change in how much speech meaning is recovered. Prior evaluation research [4,5] motivates this interpretation, but the current results do not quantify the share of errors attributable to script. No English-token preservation rate, transliteration-aware score or language-detection accuracy has been measured.

Several limitations bound the conclusions. First, the full benchmark uses mainly silver references; a 50-clip single-reviewer audit cannot establish gold-label quality for all 1,198 clips. Script-based tag suggestions may anchor the reviewer. Second, two source channels, uneven video contributions and educational subject matter restrict generalization. Third, the systems differ in runtime, decoding and unavailable provider internals, so their observed gap is not an isolated API-versus-local treatment effect. Fourth, CMI ignores word order, switch points, acoustic difficulty and which language is dominant. Fifth, the pretrained models' exposure to related public audio is unknown.

Finally, uncertainty estimation and listening-based error examples remain incomplete. The predeclared uncertainty procedure uses 2,000 paired source-video resamples within channels, seed 42, with 2.5th/97.5th percentiles; groups with fewer than ten represented videos are descriptive only. This draft reports no bootstrap interval or statistical-significance conclusion. Resampling videos within only two observed channels will still not support generalization to an unrestricted population of Nepali speakers.

## 7 Conclusion

On this frozen Nepali-English test pool, local Large V2 has lower corpus WER/CER than hosted whisper-1. Reference CMI has almost no monotonic association with utterance WER for either system. Character errors show a stronger pooled association, with substantial channel variation. The appropriate conclusion is therefore conditional on metric, source composition and reference/script conventions. It is not that mixing has been proven harmless, harmful or causally responsible for the system gap.

The next release should add the predeclared paired uncertainty estimates, a bounded listening-based error analysis and clean reproduction checks. Additional providers, new model training and new applications remain outside this report's completion path. The current evidence is suitable for a transparent technical report draft; it is not a claim of peer review, exhaustive novelty or population-wide superiority.

<!-- pagebreak -->

## References

[1] Alec Radford, Jong Wook Kim, Tao Xu, Greg Brockman, Christine McLeavey and Ilya Sutskever. 2023. Robust Speech Recognition via Large-Scale Weak Supervision. ICML, PMLR 202, 28492-28518. [Paper and proceedings](https://proceedings.mlr.press/v202/radford23a.html).

[2] Amitava Das and Bjorn Gamback. 2014. Identifying Languages at the Word Level in Code-Mixed Indian Social Media Text. ICON, 378-387. [ACL Anthology](https://aclanthology.org/W14-5152/).

[3] Bjorn Gamback and Amitava Das. 2016. Comparing the Level of Code-Switching in Corpora. LREC, 1850-1855. [ACL Anthology](https://aclanthology.org/L16-1292/).

[4] Jesse Emond, Bhuvana Ramabhadran, Brian Roark, Pedro Moreno and Min Ma. 2018. Transliteration based approaches to improve code-switched speech recognition performance. IEEE SLT, 448-455. [Authors' research page](https://research.google/pubs/transliteration-based-approaches-to-improve-code-switched-speech-recognition-performance/).

[5] Karima Kadaoui, Maryam Al Ali, Hawau Olamide Toyin, Ibrahim Mohammed and Hanan Aldarmaki. 2024. PolyWER: A Holistic Evaluation Framework for Code-Switched Speech Recognition. Findings of EMNLP, 6144-6153. [ACL Anthology](https://aclanthology.org/2024.findings-emnlp.356/).

[6] Sailesh Dahal. 2026. Nepali-English Code-Switched ASR. Hugging Face dataset, pinned revision dd00ca41dd38774cd6097c372c16939d7f3746df. [Pinned dataset card](https://huggingface.co/datasets/saileshbro/nepali-cs-asr/blob/dd00ca41dd38774cd6097c372c16939d7f3746df/README.md). Dataset card records CC BY-NC 4.0; source audio is not embedded in this report.

[7] SYSTRAN. faster-whisper. Software repository; evaluated package version 1.2.1. [Official repository](https://github.com/SYSTRAN/faster-whisper).

[8] OpenAI. Audio transcription API reference. Documentation checked November 16, 2026; evaluated model whisper-1. [Official API reference](https://developers.openai.com/api/reference/python/resources/audio/subresources/transcriptions/methods/create). Service documentation may change; saved requests and responses define this experiment.

## Appendix A Reproduction and release status

The repository is [SaTz010/Research-asr](https://github.com/SaTz010/Research-asr). This draft does not assert that the local artifacts have been pushed or that a public download URL is live. The editable report source is `reports/research_report_draft.md`; the generated PDF is `output/pdf/nepali_english_asr_research_report_draft.pdf`.

Frozen inputs are recorded in `data/manifests/test_cs_benchmark_20261112.json` and `configs/evaluation_protocol_20261112.json`. Raw predictions and independent verification records use the prefix `test_cs_benchmark_20261112_` under `results/predictions/` and `results/metrics/`. The reference comparison and CMI analysis are saved in dated November 16 JSON files with source checksums. To reproduce the analysis offline, install `requirements-analysis.txt` and run `src/compare_audited_references.py` followed by `src/analyze_cmi.py`. No new transcription request or API key is required to regenerate those analyses. The report builder validates its numerical tables against those results before producing the PDF. The current offline suite has 104 passing tests; a clean-environment release rehearsal is still pending.

The researcher conducted the project and listening audit. An AI coding assistant supported code, calculations, drafting and formatting; the author must review the final wording and claims. Before a public v1.0 release, complete the planned uncertainty and example listening, check reproduced numbers and citations, and verify the repository/download links. No website or LinkedIn publication has been performed as part of creating this draft.
