# Main-report revision - November 24, 2026

**Historical v0.3 revision record.** The [later v0.4 readability revision](progress_report_readability_20261124.md) adds the cover, linked contents, plain-language summary and three appendices while retaining these research findings.

The main report is now **working draft v0.3**, dated November 24 and authored by **Sanskar Ananta Tiwari**. The [editable source](research_report_draft.md) and [twelve-page PDF](../output/pdf/nepali_english_asr_research_report_draft.pdf) incorporate the current research findings. This is a report revision, not completion of the public release.

## Included findings

- The unchanged paired benchmark: 1,198 clips, 22 videos, two channels, complete local/hosted coverage, strict WER/CER and fixed CMI bands.
- Continuous CMI associations, channel/video/duration context, the frozen 50-clip reference and lexical-CMI sensitivity, timing and usage.
- Paired video-bootstrap uncertainty and influence checks, with source and interpretation limits.
- All ten researcher qualitative listening records, category counts, illustrative notes, category/note inconsistencies and the Example 08/09 recovery.
- Conservative post-hoc variant sensitivity on ten clips and 185 reference words: local WER 80.00% to 69.19%; hosted 103.78% to 89.73%. The six uncertain allowances are excluded, original judgments retained and assistant text-review amendments separately attributed. This is not semantic accuracy or a corpus-wide error decomposition.
- Updated abstract, discussion, conclusion, attribution and reproduction/release status. The main outcome remains weak CMI-WER association and lower local corpus error under the observed conditions, not proof that mixing causes errors or hosting causes the system gap.

## Preservation and validation

Before editing, the v0.2 source/PDF were matched to the November 19 verification hashes and preserved as `research_report_draft_v0.2_20261119.md` and `nepali_english_asr_research_report_draft_v0.2_20261119.pdf`. Version 0.1 remains preserved. No diagnostic annotations, frozen inputs, predictions, primary results or uncertainty results were changed for this revision.

The report builder now also refuses diagnostic inputs that differ from the saved follow-up verification, and checks qualitative counts, variant decision counts and the conservative score table. Three added tests cover stale annotations and incorrect reported counts/scores. All **138 offline tests passed**. The PDF was built with the bundled ReportLab runtime, rendered with Poppler and visually inspected on all twelve pages. An initial discussion overflow was removed before final inspection; tables, figures, headers, footers and page numbering were checked.

Numerical/build provenance, artifact checksums and visual-QA coverage are recorded in [the revision verification](../results/metrics/report_revision_20261124_verified.json). No new ASR inference, API request, audio upload, dependency installation or publication was performed.

## Still outstanding

Clean-environment reproduction, final author review and release/public-link checks remain. Numerical and layout checks do not independently validate hearing or the remaining same-word approvals. Six uncertain pairs may remain explicitly unresolved in the report; their exclusion is deliberate. No public release, website upload or LinkedIn post was made.
