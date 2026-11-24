# Report readability and structure revision - November 24, 2026

The report is now **working draft v0.4**, with **17 pages**. The previous verified v0.3 source and PDF were preserved before editing. The [current source](research_report_draft.md), [current PDF](../output/pdf/nepali_english_asr_research_report_draft.pdf) and [dated v0.4 PDF](../output/pdf/nepali_english_asr_research_report_draft_v0.4_20261124.pdf) contain the same revised report.

## Reader-facing changes

- Dedicated cover with title, author, date, scope and study size.
- A single generated contents page with clickable entries, correct physical page numbers and PDF navigation bookmarks.
- A plain-language summary on page 3: research question, what was tested, principal findings and what high error rates do and do not mean.
- Clearer first-use explanations of ASR, CMI, reference transcripts, silver labels, word errors and video resampling.
- Exact dataset revision and source-channel identifiers moved out of the main reading flow into Appendix A, with an explanation of their purpose.
- Appendix A for exact versions and review provenance; Appendix B for reproduction and release status; Appendix C for a glossary and score-reading guidance.

The long dataset string is a revision identifier selecting the exact dataset version used. It is not a score or result. Its full value is retained for reproducibility; general readers do not need to interpret its characters. The linked dataset citation still points to that pinned version.

## What stayed the same

All v0.3 research tables and numerical findings were retained. The full 1,198-clip benchmark, 50-clip audit and ten-clip post-hoc sensitivity remain distinct. No model responses, reference annotations, variant decisions, primary analysis results or uncertainty results were changed. The report retains its single-reviewer, uncertain-pair, source-coverage and noncausal interpretation limits.

## Checks

All **141 offline tests passed**. New checks require the reader-facing structure, reject visible long hashes in the main text, and require the plain-language score table to match the full benchmark. The multi-pass PDF build supplies contents page numbers and internal links from the actual rendered headings.

All seventeen pages were rendered with Poppler and visually checked. Final automated checks cover contents destinations/printed page numbers, bookmarks, external link annotations, page bounds, missing-glyph indicators, unchanged data hashes and preserved v0.3 archives. The build and inspection record is [the readability verification](../results/metrics/report_readability_20261124_verified.json).

This improves structure and explanations but does not constitute an independent reader-comprehension study or a second listening review. Clean-environment reproduction, final author review and release/public-link checks remain pending. No inference, API call, dependency installation or publication was performed.
