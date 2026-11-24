# Reviewed spelling and transliteration sensitivity — 2026-11-23

**Post-hoc extension, not a replacement for the frozen benchmark.** Same ten preselected clips and published references; hypotheses never change. No API call or model run.

Review progress: 10/10 clips complete; 159 distinct within-clip word pairs. Decisions: `{'different': 47, 'unsure': 6, 'same': 31, 'reference_issue': 75}`.

The score uses the original normalization and word edit-distance algorithm, assigning zero substitution cost only to clip-scoped pairs explicitly judged `same` after listening. There is no automatic spelling-distance threshold, romanizer, semantic translation or transitive/global aliasing. One accepted pair applies to its occurrences within that clip, in both systems where present.

| System, same ten clips | Strict WER | Approved-variants-only WER | Edit reduction |
|---|---:|---|---:|
| local | 80.00% | 69.19% | 20 |
| whisper_api | 103.78% | 89.73% | 26 |

All pair decisions have been saved. These rates follow the entered reviewer labels; completion is not independent validation that every approved pair is the same lexical word. Do not compare these ten-clip rates directly with the 1,198-clip benchmark.

Reference/alignment-issue pairs: 75. This combined label does not prove that this many published reference words are wrong; it can reflect ambiguous word pairing or split/joined words. These pairs are not forgiven.

## What can be counted

The JSON separates occurrences in one minimum-edit strict substitution alignment into same/different/unsure/reference_issue/pending decisions. It also records the edit reduction after rerunning variant-aware alignment. These are different quantities: accepted equivalences can change the alignment. Neither the remaining edit count nor the score reduction is an exact corpus-wide decomposition of actual speech errors versus script errors.

Insertions/deletions and uncertain or faulty-reference cases still require listening. This first version does not handle split/joined words or prove equivalence from phonetic similarity. Different lexical words, inflections, translations or synonyms must not be accepted solely because their meanings or spellings are close.

## Accepted pairs for transparency

Every `same` choice below is a reviewer judgment, not an automatic phonetic/semantic finding. Recheck suspicious numeric, inflection or misaligned pairs in full sentence/audio context before describing the score as validated spelling/transliteration tolerance. Preserve earlier decisions in history when revising.

| Clip | Pair | Reference token | Output token | Occurrences |
|---|---:|---|---|---|
| 2 | 2 | लागौँ | लागो | {&#x27;local&#x27;: 1} |
| 2 | 4 | जहाँनिर | ज्यानिर | {&#x27;local&#x27;: 1} |
| 2 | 6 | हामी | हमें | {&#x27;local&#x27;: 1, &#x27;whisper_api&#x27;: 1} |
| 2 | 7 | देख्न | देखने | {&#x27;local&#x27;: 1} |
| 2 | 8 | सक्छौँ | सक्षुँ | {&#x27;local&#x27;: 1, &#x27;whisper_api&#x27;: 1} |
| 2 | 9 | हाम्रो | अम्रो | {&#x27;local&#x27;: 1, &#x27;whisper_api&#x27;: 1} |
| 2 | 10 | program | प्रोग्राम | {&#x27;local&#x27;: 1, &#x27;whisper_api&#x27;: 1} |
| 2 | 14 | जहाँनिर | जानीरो | {&#x27;whisper_api&#x27;: 1} |
| 2 | 15 | चाहिँ | चाहिए | {&#x27;whisper_api&#x27;: 1} |
| 2 | 16 | देख्न | देखना | {&#x27;whisper_api&#x27;: 1} |
| 2 | 17 | छ | सह | {&#x27;whisper_api&#x27;: 1} |
| 4 | 6 | त | दा | {&#x27;local&#x27;: 1, &#x27;whisper_api&#x27;: 1} |
| 4 | 13 | त | ता | {&#x27;local&#x27;: 1, &#x27;whisper_api&#x27;: 1} |
| 5 | 13 | भयो | भायो | {&#x27;local&#x27;: 1, &#x27;whisper_api&#x27;: 1} |
| 5 | 14 | यसको | इसको | {&#x27;local&#x27;: 1, &#x27;whisper_api&#x27;: 1} |
| 5 | 16 | ठिक | ठीक | {&#x27;local&#x27;: 1} |
| 5 | 20 | भने | सबने | {&#x27;whisper_api&#x27;: 1} |
| 5 | 23 | हामीले | हमने | {&#x27;whisper_api&#x27;: 1} |
| 5 | 25 | ठ्याक्कै | ठक्के | {&#x27;whisper_api&#x27;: 1} |
| 7 | 1 | भनेको | बनेको | {&#x27;local&#x27;: 1} |
| 7 | 2 | × | इंटू | {&#x27;local&#x27;: 1, &#x27;whisper_api&#x27;: 1} |
| 7 | 3 | भयो | बहयो | {&#x27;local&#x27;: 1} |
| 7 | 4 | 27 | सप्ताइस्तिया | {&#x27;local&#x27;: 1} |
| 7 | 8 | आयो | दिया | {&#x27;local&#x27;: 1, &#x27;whisper_api&#x27;: 1} |
| 7 | 9 | त | था | {&#x27;local&#x27;: 1, &#x27;whisper_api&#x27;: 1} |
| 7 | 12 | 3 | थ्री | {&#x27;whisper_api&#x27;: 1} |
| 7 | 16 | तिया | सप्ताइस्तिया | {&#x27;whisper_api&#x27;: 1} |
| 7 | 17 | 81 | एकासी | {&#x27;whisper_api&#x27;: 1} |
| 7 | 18 | therefore | देर्फूर | {&#x27;whisper_api&#x27;: 1} |
| 7 | 19 | x | एक्स | {&#x27;whisper_api&#x27;: 1} |
| 7 | 20 | value | व्यालू | {&#x27;whisper_api&#x27;: 1} |

## Status and provenance

Use notebook 08 or `python src/variant_sensitivity.py`. It prepares candidates and exports current reviewed results without fabricating decisions. Pair judgments live separately in `data/annotations/word_variants_20261122.json`; prior saves retain history. Notebook 07 and its qualitative notes are preserved. Frozen references, primary WER/CER, CMI analyses and uncertainty intervals remain unchanged.

This post-hoc addition was motivated by the unexpectedly high error rates and discussion after inspecting results; it was not predeclared. Validation is limited to this single-reviewer subset. The separate notebook-07 listening records and clean release checks must also be checked before publication.

Related methods: [PolyWER, Kadaoui et al. 2024](https://aclanthology.org/2024.findings-emnlp.356/) and [Emond et al. 2018](https://research.google/pubs/transliteration-based-approaches-to-improve-code-switched-speech-recognition-performance/). This narrow one-token reviewed-variant scorer is not an implementation of either full published framework.
