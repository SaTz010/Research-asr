# Reproduce the saved-output results

The verified target is **Windows, CPython 3.13**, with a new virtual environment and no inherited system packages. Reproduction does not run Whisper, buy API calls, download the dataset or require a GPU. Original inference used separate frozen runtime files; do not use this environment to claim a repeat of those inference runs.

## Fresh setup

From the repository root in PowerShell:

```powershell
py -3.13 -m venv .cache\reproduction-env
.\.cache\reproduction-env\Scripts\python.exe -m pip install -r requirements-reproduction-lock.txt
.\.cache\reproduction-env\Scripts\python.exe src/reproduce_results.py
```

The lock records the full dependency set freshly installed for the November 24 check. `requirements-reproduction.txt` lists direct dependencies; `requirements-analysis.txt` is the smaller scoring/plotting subset. The SDK and datasets packages are present for offline mocked tests, not for live service calls or downloads. No Whisper inference runtime or weights are installed by this workflow. Installation needs PyPI access; the actual replay blocks socket connections and sets the Hugging Face offline flags.

The PDF builder currently uses the Windows Arial font family. Other operating systems and Python versions were not validated in this check. The new environment still uses this host's Python runtime, fonts and operating system; this was a fresh environment, not a separate VM or independent machine.

## One command, isolated outputs

`src/reproduce_results.py` copies the needed repository files into a new ignored `.cache/reproduction-*` directory. It does not copy `.env`, cached audio/video, model weights or the existing virtual environment. It strips inherited API-key/token variables from child processes and blocks network socket connections during replay. Canonical predictions, annotations and analysis outputs in the original project are not overwritten.

It runs:

1. Dependency consistency check and the full offline unit-test suite.
2. The frozen 50-clip published/corrected-reference sensitivity.
3. Full 1,198-clip CMI analysis and its channel/video/duration checks.
4. The 2,000-draw paired video-bootstrap analysis.
5. Ten-clip reviewed-variant scoring with `--saved-text-only`.
6. The forced-Nepali paired language-setting comparison.
7. The specialist comparison using `--saved-text-only`, preserving the original audio-verification receipt.
8. The revised research PDF build.

The six regenerated result JSONs must match the saved results recursively, including their counts, denominators, coverage, provenance, resample weights and decisions. Floating-point comparisons allow absolute roundoff of `1e-12`; the variant result's computation date and the two follow-up results' computation timestamps are ignored. All other counts, settings, source hashes and resample weights must match. The PDF must have identical text and page count. Input/prediction/annotation hashes must remain unchanged, and no network connection attempt may occur.

Seven analysis charts are regenerated as PNG/SVG. The revised PDF embeds the specialist CMI chart and the included original uncertainty report-chart asset; the latter is not recreated from scratch. The overlap audit is checked as a saved evidence record, not rerun against the authors' private training data. Public evidence collection requires separate source access and does not certify training exclusion. PDF binary hashes and SVG metadata are not expected to be identical because generated timestamps/IDs can differ.

## Inspect the evidence

By default, logs and `verification.json` are written under ignored `output/reproduction/`. A different destination can be selected with `--output-dir`. Every stage must have exit code zero and the final JSON must say `passed: true`. The record identifies the Python executable, packages, stage timings, result comparisons, PDF check and input hashes. A failed stage writes evidence and stops; it does not substitute a smaller test pool or request new predictions.

The November 27 v0.6 revision/replay is recorded in `results/metrics/report_revision_v06_20261127_verified.json`. Its replay uses the previously created clean environment and a new isolated working copy; it is not a second fresh installation or a cross-machine test. The historical November 24 publication check is summarized in `results/metrics/clean_reproduction_20261124.json`, with release checks in `results/metrics/publication_readiness_20261124.json`.

## Audio review is separate

For numerical replay, use:

```powershell
.\.cache\reproduction-env\Scripts\python.exe src/variant_sensitivity.py --saved-text-only
```

Run that individual command only in a disposable copy if you want to preserve the checked-in export's computation date. The one-command runner already handles this isolation.

This reuses the researcher's saved judgments; it does not hear speech, independently validate same-word equivalences or recheck WAV payloads. Normal notebook playback/review retains default audio-integrity verification and requires separately obtained, manifest-matched source audio. Source licensing is documented in [DATA_SOURCES.md](DATA_SOURCES.md).
