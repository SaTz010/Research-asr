# November 20 report revision completed early on November 19

The main research report is now **working draft v0.2**, dated November 19, 2026, under Sanskar Ananta Tiwari's name. This completes the scheduled November 20 report-revision objective early. The current PDF has nine pages and two figures; all nine rendered pages were visually inspected. The preceding eight-page November 16 source and PDF are preserved as `research_report_draft_v0.1_20261116.md` and `nepali_english_asr_research_report_draft_v0.1_20261116.pdf`.

## What changed

- Revised the abstract, overall results, discussion and conclusion to include the verified paired uncertainty findings.
- Added Section 5.3 with the frozen bootstrap procedure, full-pool/five-band WER/CER gap table, exploratory 95% intervals and a report-sized uncertainty figure. The sign is consistently local minus hosted, so negative values mean lower local error.
- Added the video-removal ranges, source-channel caveats, paired clip descriptions and the wide same-50 reference-sensitivity intervals. The report does not infer significance, causation, a reliable opposite audit ranking or a degradation-slope difference from separate band intervals.
- Replaced outdated statements that uncertainty is pending. Listening-based example analysis, clean reproduction and public-release checks are still explicitly unfinished.
- Updated reproduction instructions to include `src/analyze_uncertainty.py`; preserved the eight previously checked references without changing the literature scope.

The full-pool WER gap is -5.46 pp, exploratory interval [-9.79, -2.31]; CER gap -3.79 pp, interval [-8.74, -0.38]. Neither one-video removal nor one-channel removal reverses the overall point direction. Higher-CMI comparisons remain imprecise, and two channels plus fixed silver labels restrict inference. These measurements were taken from the saved analysis, not from a fresh ASR run.

## Checks

The report builder now rejects uncertainty/reference-comparison/CMI files whose hashes differ from independent verification. It checks all six uncertainty-table rows, their signs/intervals, both audit WER intervals and the video-influence ranges, in addition to its existing corpus-score/CMI-band checks. ReportLab imports are confined to PDF rendering so numerical checks run without adding a PDF dependency to the ASR environment.

Five new tests cover the current report, altered interval/sign, altered audit interval, altered band score and stale result hash. The full offline suite passed **116 tests**. PDF rendering also checks figure bounds; visual inspection caught and corrected lazy image-dimension scaling before delivery. Final PDF checks cover nine substantive pages, author metadata, v0.2/date footers, expected interval text, two figures and clickable references. A dated verification JSON records source/result/PDF hashes.

The main report and builder were updated; frozen references, predictions, protocol, analysis JSON and independent uncertainty results were not modified. No dependency installation, credential access, new inference, audio upload, paid API request, commit, push or public post was needed.

## Next session

The next scheduled research work is November 21's review of the ten examples selected before inference. The researcher should listen before assigning speech-level error categories. November 22–24 remain clean reproduction, final author review and release/link checks; the November 25 announcement target is unchanged. Version 0.2 remains a working draft, not a final or peer-reviewed publication.
