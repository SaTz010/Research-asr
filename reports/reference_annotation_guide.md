# Reference and CMI review rules — fixed before test inference

**Audit frozen November 12:** all 50 saved records are complete; see [the freeze checkpoint](progress_20261112.md). The instructions below document the completed process. Do not rerun notebook save cells against the frozen annotation file. Preserve its snapshot and exact pre-freeze backup; any later correction needs a documented amendment and new snapshot.

Review 50 items from the frozen evaluation pool before inspecting any held-out ASR output. The published mixed-script `transcription` remains the primary reference for the full benchmark. Your corrections and language judgments are stored separately, for an explicitly labelled sensitivity analysis. This audit does not establish that all unreviewed references are accurate.

## What to open

Open `notebooks/06_reference_cmi_audit_assisted.ipynb` in VS Code, select the project Python environment, and run setup. It reads only the selected references and cached WAVs; it does not run any ASR system. Under the revised November 10 schedule, review items 1–25 on November 11 and 26–50 on November 12. Each session contains five items from each published CMI band. Each item has audio, an editable transcript/tag-draft cell, and a separate confirmation/save cell. The notebook can be used locally; Colab would require transferring the same cache and project helpers first.

The original `05_reference_cmi_audit.ipynb` remains available for fully manual entry, with its historical date headings and checksum preserved. Both notebooks use the same saved review file. Switching notebooks does not automatically overwrite any answer; check the displayed saved review before deciding whether to revise it.

Set the `reviewer` field in `data/annotations/reference_audit_20261105.json` to a consistent name or pseudonym. Keep the same person for all 50 unless another reviewer is explicitly documented. Do not claim inter-annotator agreement with one reviewer.

## Listen before answering

1. Play the audio fully, then replay difficult parts. Keep the spoken languages: Nepali words in Devanagari and clearly English words in Latin script. Do not translate or improve grammar, and do not add unspoken words to make the sentence sensible.
2. Set `corrected_reference` to the full words you hear. If the published text is correct, copy it exactly and choose `verdict = 'match'`. If you alter spelling, words or script, choose `corrected` and explain the substantive change in `notes`. Use `unsure` for unresolved speech/reference judgments, with notes; do not invent inaudible content or silently delete it.
3. Retain repetitions, false starts and fillers that are audible and identifiable. Use ordinary spelling consistently. Do not expand abbreviations into words that were not spoken. Note proper names or technical terms whose spelling you cannot resolve. Do not use an ASR-generated transcript to settle a disputed reference.
4. Generate the suggestions and check every word/tag as described below, then run the confirmation cell to save. `pending` saves nothing. Re-running setup shows current progress; saved annotations, rather than notebook execution counts, determine completion. Revisions retain the preceding saved decision in `previous_reviews`. In the original manual notebook, fill the full tag list directly and run its answer cell.

The helper normalizes the corrected text using the exact evaluation rule: NFC, lowercase, Devanagari digits mapped to ASCII, Unicode punctuation replaced by spaces, then whitespace collapsed. For example, `online-class` becomes two tokens. Provide one language tag per resulting token; a count mismatch prints the token list so you can fix it. Normalization does not translate or transliterate words.

## Automatic suggestions, followed by human checking

This workflow was added November 10, before any held-out inference. It changes the typing workflow, not the lexical-language annotation rules below.

1. In the draft cell, edit the quoted `corrected_reference` after listening. Its initial text is copied from the published reference for convenience; that is not a listening judgment. Run the cell to print numbered normalized words and suggested tags.
2. Check every suggestion. The local helper suggests `ne` for Devanagari-letter tokens and `en` for Latin-letter tokens. Tokens without letters receive `other`; mixed or unsupported letter scripts receive `ambiguous`. It is a transparent script heuristic, not a trained language detector. Nepali written in Latin, English written in Devanagari, Hindi, proper names, borrowings and abbreviations need special attention.
3. In the next cell, leave `tag_overrides = {}` if all tags are correct, or enter only the corrections using the displayed **1-based word numbers**. For example, `{4: 'en', 9: 'other'}` changes words 4 and 9. If you change the transcript, rerun the draft and recheck the word numbers before saving.
4. Set `tags_reviewed = True` only after checking all tags, choose `match`, `corrected` or `unsure`, and add notes. Run this save cell. It refuses to save a non-pending verdict without the confirmation. A confirmed review records both the script suggestions and the final human tags with `tagging_method = 'script_suggestions_human_checked'`.

Do not bulk-accept the suggestions as human labels. They inherit the same script assumptions that the lexical audit is intended to examine. State the assistance method in the final report and disclose that it can influence an annotator's decisions. Prior manually entered records remain valid and are preserved separately in revision history if updated. No API calls, extra model downloads or additional dependencies are needed.

## Language tags and audited CMI

- `ne`: Nepali lexical material, including Nepali grammatical words and identifiable Nepali fillers. Roman script alone does not make a Nepali word English.
- `en`: clearly English lexical material, including English technical vocabulary and acronyms spoken as English. An English word written in Devanagari is still English for this human lexical audit. Write it in its ordinary Latin spelling in the corrected mixed-script reference when identifiable, and note the script correction.
- `other`: language-independent numerals/symbols, identifiable proper names without an assignable language, or clear third-language material. Explain nontrivial cases in notes. This category is excluded from the bilingual denominator.
- `ambiguous`: unresolved borrowing, mixed morphology inside a single normalized token, unclear acronym/name, or genuinely uncertain language identity. Do not split a word merely to obtain a preferred CMI. Any ambiguous token leaves audited CMI unavailable until resolution; a missing CMI is not zero.

Use lexical meaning and what was spoken, rather than automatic script labels. A shared borrowing should be `ambiguous` unless its language is clear under the written rule; record the difficulty. Maintain a short decisions log in your notes for repeated terminology and apply decisions consistently. These conventions are an operational definition, not a claim that every borrowing has an objectively unique language.

Let `N_ne` and `N_en` be counts of unambiguous Nepali and English tokens after normalization. Then:

`CMI = 100 × min(N_ne, N_en) / (N_ne + N_en)`

This is 0 for a monolingual reference and 50 for equal token counts. If no assignable bilingual tokens remain, or any token is ambiguous, store no audited CMI. `other` tokens do not enter the denominator. CMI measures language balance; it does not count how often the speaker switches languages.

Example: `म आज online class मा छु 25` → tags `['ne', 'ne', 'en', 'en', 'ne', 'ne', 'other']` → 4 Nepali, 2 English, 1 excluded → CMI 33.33. Keep the full precision in the saved result; round only when presenting it.

The source dataset uses script-based token-language labels. This lexical audit can therefore differ for both corrected words and language assignments. Report the two definitions separately. Corrected-reference WER/CER and audited CMI are sensitivity results on these same 50 clips, not replacements for all published labels or a claim of a representative population estimate.

## Freeze and use

The selection is seed-42, 10 clips per published CMI band, balancing source channels then videos within each band. Selection uses no model predictions. The equal-band audit is intentionally different from the full dataset distribution. Clips may move between bands after human correction; retain the original selection band and do not replace inconvenient examples.

Resolve `unsure`/`ambiguous` items when possible. Remaining uncertainty must receive an explicit inclusion/exclusion rule in the November 13 protocol, with counts disclosed; completing a listening decision is not the same as resolving its reference. Before inference, validate all 50 records, record the reviewer/conventions and freeze their checksum. Save a new inference-ready manifest referencing the frozen pool and review checksum; preserve today's blocked manifest and its selection checksum. Neither this guide nor a readiness flag proves that listening occurred.

No manual listening decisions have been made by the preparation script. Do not change the pending labels without listening. Source WAVs and downloaded Parquet files remain in the ignored cache; annotation metadata and corrected references need the dataset's attribution and noncommercial licence when shared. Current repository publication is a later task.
