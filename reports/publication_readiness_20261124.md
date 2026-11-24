# Publication readiness - November 24, 2026

**Verdict: the local package is technically ready as a release candidate.** Clean saved-output reproduction passed. Final author review and publication/public-download checks remain; nothing was pushed or posted by this check. The public GitHub repository was read-only checked and still contains the earlier scaffold.

## Clean-environment result

A new CPython 3.13 virtual environment was created under ignored `.cache/`, without inherited system site-packages. Dependencies were freshly downloaded from PyPI. The resolved set is pinned in `requirements-reproduction-lock.txt`; the dependency consistency check found no broken requirements. The separate original inference environment was preserved.

`src/reproduce_results.py` ran in a second, isolated repository copy, without source audio, model weights, `.env` or API credentials. Child-process socket connections were blocked. Every stage completed successfully:

| Check | Result |
|---|---|
| Full offline suite | 145 tests passed |
| Frozen 50-clip reference sensitivity | Regenerated JSON matched |
| Full 1,198-clip CMI/source/duration analysis | Regenerated JSON matched |
| Paired 2,000-draw video-bootstrap analysis | Regenerated JSON and resample weights matched |
| Ten-clip reviewed-variant scoring | Matched without private WAVs |
| PDF rebuild | Identical text and 17-page count |
| Input/prediction/annotation checksums | Unchanged in source and replay copy |
| Network connection attempts during replay | Zero |
| New model inference / paid API requests | Zero |

The comparisons retain exact counts, denominators and coverage, with absolute floating-point tolerance `1e-12`. Only the variant export's computation date may change. Five analysis charts are regenerated as PNG/SVG; the PDF uses its two included report-chart assets. This is a same-platform saved-output reproduction, not a new inference run, a separate-machine study, independent hearing validation or cross-platform bitwise guarantee.

Evidence: [clean replay](../results/metrics/clean_reproduction_20261124.json), [release checks](../results/metrics/publication_readiness_20261124.json), and [reproduction instructions](../REPRODUCING.md).

## Release gaps fixed

- Split analysis requirements from model inference requirements and added the tested full reproduction lock.
- Added `--saved-text-only` replay while keeping default audio verification in listening workflows.
- Allowed a legitimate variant computation-date change during PDF verification without relaxing numerical/provenance checks.
- Added tests for text-only replay, stale-score rejection and nested result comparison.
- Removed embedded playback outputs from four notebooks after retaining exact original backups locally. Current review decisions remain in the annotation JSONs. Notebook 08 now shows the conservative saved choices with listening confirmation disabled, preventing stale approvals from being silently resubmitted by running all cells.
- Added the author-selected MIT code license and CC BY 4.0 license for original report/figures, with explicit exceptions for dataset-derived material. Dataset attribution and its CC BY-NC 4.0 terms remain recorded.
- Added citation metadata and a concise publication README. The previous long README and original notebook outputs remain backed up in the ignored local cache.
- Updated the report to working draft v0.5 with reproduction status and license scope; prior source/PDF versions remain preserved.

## Publication checks and limits

The release check scans candidate files and nested pilot ZIP members for common credential patterns, excludes `.env`, caches, source audio/video and weights, validates notebook output cleanup, checks local documentation links and confirms no oversized GitHub file. No credential pattern was found; this is a targeted scan, not a mathematical guarantee of absence. All twelve public bibliography/dataset/license/repository URLs returned HTTP 200. HTTP availability does not independently verify every claim in a cited source.

The 17-page PDF was rendered for visual QA; changed pages and navigation were checked while unchanged page bodies matched the previously inspected version. Numerical tables remain unchanged. The PDF still clearly states its single-reviewer, two-channel, silver-reference, uncertain-pair and noncausal limits. No novelty, peer-review or institutional endorsement claim was added.

The local ZIP under ignored `output/release/` is a publication candidate with a detached SHA-256 receipt. It does not include the private backups or replay environment. Final publication will require committing/pushing the checked files or otherwise uploading the package, then testing the resulting public PDF/download links. Existing public repository availability is not evidence that the new report is already online.

## Remaining author actions

Read the v0.5 report once for author name, interpretation and wording; keep the six uncertain pairs explicitly unresolved. Then publish the reviewed package and verify the public report/download links before the LinkedIn announcement. New providers, training, translation and app development are not required for this release.
