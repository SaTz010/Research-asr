# Ten-example listening review prepared — November 20, 2026

November 21's scheduled qualitative review is starting early. [Notebook 07](../notebooks/07_preselected_error_examples.ipynb) is prepared with the exact ten identities selected before inference, two per published CMI band. The original 50-clip reference/CMI audit remains frozen and is not used for new saves. [Step-by-step guide](error_example_review_guide.md).

All ten cached WAV payloads, decoded waveform identities and durations passed the existing audio verifier. Frozen manifest/audit/protocol and local/API prediction provenance are checked using the existing loader. The new notebook needs no API key, download, inference run or per-word language tagging.

For each example the user runs an audio/reference cell, then an output/alignment cell, then edits a listening-decision cell. Script/spelling differences are distinct from wrong words, omissions, extra/repeated text and wrong-language output. Alignment operations are string comparisons and do not automatically diagnose speech errors. The user supplies concrete notes and may record uncertainty or a possible reference issue.

New decisions save separately to `data/annotations/error_examples_20261120.json`. Previous saved judgments are loaded on reopening; changed judgments retain a history. Missing listening confirmation, categories, notes or valid reference assessment prevents a save. Reference problems are documented without rewriting published or previously frozen human references, hypotheses or headline scores.

At preparation, **0/10 listening reviews are saved** and all categories remain unassigned. No assistant listening judgment or cause label has been fabricated. This preparation is not completion of the human review. Ten qualitative examples can illustrate mechanisms but cannot measure the fraction of all 1,198-clip errors attributable to each cause.

Added `src/error_example_review.py`, notebook 07, the guide and six tests covering safe pending/reopen behavior, invalid decisions, retained review history, provenance/reviewer drift, escaped alignment HTML and notebook syntax/edit preservation. **All 122 offline tests pass.** The generated notebook schema and every code cell compile; the two first-example alignment tables were smoke-tested without classifying speech. No new dependency or paid call was needed.

Next: researcher listens and saves example 01, then examples 02–10. The resulting notes must be interpreted before adding error examples to the report. Reproduction/release checks and final author review remain scheduled November 22–24; November 25 announcement target is unchanged.
