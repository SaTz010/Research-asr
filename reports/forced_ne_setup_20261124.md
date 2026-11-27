# Running the forced-Nepali follow-up

Prepared November 24, 2026. Setup is complete; the new inference runs have not started. The published automatic-language results and report v0.5 are preserved.

## What changes

Both systems receive `language="ne"`. Everything else stays at the original pinned settings: local Whisper Large V2 with faster-whisper/CUDA FP16, and hosted OpenAI `whisper-1`. Both new main runs use the exact same 1,198 test clips, audio bytes, references and CMI values as before. The two automatic prediction files are reused; do not run automatic inference again.

The frozen follow-up is [described here](protocol_forced_ne_20261124.md), with settings in [its configuration](../configs/forced_ne_protocol_20261124.json). The dated manifests have separate output names, so they cannot silently overwrite the automatic checkpoints. This is an exploratory extension; API runs on different dates can include service variability as well as language-setting differences.

## Checks completed

- All 1,198 test WAV payloads, decoded identities and references validated for both systems.
- Twenty existing, disjoint validation clips validated for both systems; no new automatic pilot is needed.
- Original automatic predictions, source protocol and reference audit match their pinned checksums.
- Local software/GPU checks and the cached model-weight checksum pass.
- The offline tests include checking the actual API request's `language=ne`, preventing incompatible checkpoint reuse and preventing completed API calls from being resubmitted.
- The saved API credential failed the metadata-only access check with HTTP 401. No audio was uploaded and no transcription requested. Replace the key before API execution. Model-access success alone does not verify remaining credits or transcription permissions.

The [setup receipt](../results/metrics/forced_ne_setup_20261124.json) records the verification scope. No forced-language scores exist yet.

## Budget and time

The 1,198 forced API calls are estimated at **$1.2556**, using $0.006/minute and each clip's duration rounded upward to a second. The additional twenty validation calls are estimated at **$0.0190**. Plan **$1.53 including a 20% reserve**, within the user-reported $2.29 balance. These are estimates, not a hard billing cap. No automatic rerun is included.

Reserve roughly one to two hours for each full run, based on the previous run's approximately 46 minutes of local generation and 54 minutes of API request time, plus setup, saving and checks. Actual elapsed time can differ. Run one at a time and keep the computer awake and connected to power.

## 1. Open the existing environment

Open the project in VS Code and open its PowerShell terminal. Run the following commands from the project root. They use the existing pinned inference environment directly; no activation or package installation is needed.

## 2. Run the local twenty-clip check

```powershell
.\.venv\Scripts\python.exe src/run_evaluation.py --manifest data/manifests/validation_forced_ne_20261124.json --system local --condition forced_ne --execute
```

Wait for `successful_clips: 20` and `complete: true`. This confirms the local execution path; an accuracy improvement is not required to proceed.

## 3. Fix and check API access

In VS Code, open the existing project-root `.env` file. Replace only the value after `OPENAI_API_KEY=` with the complete valid key and save. Keep the key out of chat and source files. The project already excludes this file from Git; the file remains subject to the folder's existing OneDrive synchronization.

```powershell
.\.venv\Scripts\python.exe src/check_api_auth.py
```

Proceed when it reports `model_metadata_access_succeeded`. Also check the account's usable balance. This command retrieves model information; it does not upload audio or request a transcription. If it still returns 401, resolve the credential/account issue before running the next command.

## 4. Run the API twenty-clip check

```powershell
.\.venv\Scripts\python.exe src/run_evaluation.py --manifest data/manifests/validation_forced_ne_20261124.json --system whisper_api --condition forced_ne --execute --max-requests 20
```

This makes paid transcription calls. Wait for twenty successful clips and complete coverage. The API client has automatic retries disabled. The request limit bounds new calls in this invocation; it does not guarantee a dollar limit.

## 5. Run the full local condition

```powershell
.\.venv\Scripts\python.exe src/run_evaluation.py --manifest data/manifests/test_cs_forced_ne_20261124.json --system local --condition forced_ne --execute
```

Wait for 1,198 successful clips and complete coverage.

## 6. Run the full API condition

```powershell
.\.venv\Scripts\python.exe src/run_evaluation.py --manifest data/manifests/test_cs_forced_ne_20261124.json --system whisper_api --condition forced_ne --execute --max-requests 1198
```

Wait for 1,198 successful clips and complete coverage. The automatic outputs are not submitted again.

## 7. Verify the two completed main runs

```powershell
.\.venv\Scripts\python.exe src/verify_evaluation.py --manifest data/manifests/test_cs_forced_ne_20261124.json --predictions results/predictions/test_cs_forced_ne_20261124_local.json
.\.venv\Scripts\python.exe src/verify_evaluation.py --manifest data/manifests/test_cs_forced_ne_20261124.json --predictions results/predictions/test_cs_forced_ne_20261124_whisper_api.json
```

These commands make no inference or API calls. They independently recompute edit counts and scores and check saved inputs/settings. Use the same commands with the validation manifest and its matching prediction filenames to verify the pilot if needed.

## Outputs, resume and next analysis

Predictions go to `results/predictions/<manifest name>_<system>.json`. Metrics use the same filename in `results/metrics/`; independent verification adds `_verified.json`. The main names start with `test_cs_forced_ne_20261124`, while the pilot names start with `validation_forced_ne_20261124`.

After an ordinary stop between completed clips, rerun the exact same command to reuse successful responses and continue. If the runner reports a pending, failed or unresolved attempt, stop and investigate the saved record. Do not delete a checkpoint, rename a manifest or remove a lock just to bypass this check: an interrupted paid request might already have been processed. No automatic retry is enabled.

After both main runs are complete and independently verified, the next work is paired forced-minus-automatic WER/CER, the original CMI groups and video-level uncertainty, followed by the same ten-example review and a separately versioned report update. The paired follow-up analysis and report update are not produced by this setup. Lower forced-minus-automatic error means forcing Nepali helped on this dataset; worse or unchanged results are equally reportable.
