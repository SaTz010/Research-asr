# November 13 preflight — preparation performed November 12

**Completed November 12:** metadata authentication and one real validation transcription succeeded. Use [the completion checkpoint](progress_preflight_completed_20261112.md) and [ready manifest](../data/manifests/test_cs_benchmark_20261112.json). The earlier pending status and authentication troubleshooting below are retained as history; the original failures are preserved. The main benchmark has not started.

**Current credential location, by the researcher's later request:** use `.env` beside `README.md` in the project root. Both scripts read this file first; the earlier AppData location below is historical and no longer read. The root file is Git-ignored, but the researcher accepts that the OneDrive project folder may sync it. Save the key after `OPENAI_API_KEY=`, then run the authentication diagnostic. Do not print or share the file. No live authentication success has yet been verified.

The researcher requested starting the November 13 work early. The technical protocol, frozen runtime settings, budget calculation and offline input checks are complete. **Live API access is still pending.** No new transcription/API call has been made during this preparation, and held-out inference remains blocked.

## Completed

- Saved [the written protocol](protocol_20261112.md) and [its machine-readable companion](../configs/evaluation_protocol_20261112.json) before test predictions. They specify the two unchanged systems, WER/CER normalization, source/audited CMI analyses, coverage/failure policy, exploratory paired video-cluster uncertainty and ten predefined error examples.
- Revalidated the frozen 50-review audit and unchanged 1,198-clip pool, and prepared [the shared test-run manifest](../data/manifests/test_cs_preflight_20261112.json). Its readiness flag remains false until the validation-only access check. The original November 5 pool is preserved.
- Bound the run manifest to exact local/API settings and relevant package versions. The runner now rejects drift before inference; its regression check passed.
- The local setup check loaded the isolated CUDA libraries and reported one CUDA device with FP16 support. It made no model inference/download or paid call.
- Both local and API dry-runs verified the same 1,198 clips / 11,940.723 seconds. The access-check dry-run verified one 3.76-second validation clip. All reported zero attempted predictions and no authentication/inference.
- **80 offline tests passed.** No new dependencies were added.

## Dated cost/access record

[Official OpenAI pricing](https://developers.openai.com/api/docs/models/whisper-1), fetched November 12, lists $0.006 per audio minute. At conservative per-clip whole-second rounding, the test pass plans $1.2556. Including the one short access request gives $1.2560 before reserve, and **$1.51 including 20% reserve rounded upward**. Billing rounding is a planning assumption, not a guaranteed invoice or enforced dollar cap. Returned usage and actual account records remain the billing evidence.

The researcher reported **$3.54 usable API credit** in chat on November 12. This covers the planning estimate; it was not independently inspected. API key, credential permissions and live access remain unverified. No key was configured in the assistant's process, and no local `.env` file was found; the user's terminal may have its own environment. Do not paste a key into chat, notebook source or these artifacts.

## Remaining user action: one validation access check

Open a VS Code terminal in the project folder and run:

```powershell
.\.venv\Scripts\python.exe src/run_evaluation.py --manifest data/manifests/validation_api_access_20261112.json --system whisper_api --execute --max-requests 1
```

This submits **one 3.76-second validation WAV**, using the same hosted request settings as the benchmark. At the published rate with four planning billable seconds, the estimate is $0.0004, already included above. When prompted, enter the key in the hidden terminal input. A configured `OPENAI_API_KEY` is used automatically. Completed reruns reuse the saved result and require no authentication; uncertain/failed requests stop without automatic retry.

Success should end with `successful_clips: 1`, `expected_clips: 1`, `complete: true`, and zero unresolved/unattempted clips. Preserve the raw checkpoint at `results/predictions/validation_api_access_20261112_whisper_api.json` and the corresponding metrics export. An inaccurate/empty successful transcript can still confirm API operation; this access clip is not a main-test accuracy result.

If it fails, retain the attempt and investigate the reported error; do not repeatedly rerun or buy more credit without identifying the issue. Only share non-secret summaries/errors in chat. After success, verify the saved response/identity and create a **separate inference-ready manifest**, referencing the frozen protocol/audit and the same 1,198 pool entries. Preserve this blocked preparation manifest and its hashes. No main-test execution is needed to complete the access check.

The local benchmark remains scheduled November 14, followed by the API benchmark on exactly the same clips November 15. The November 13 session is complete only after live access is checked and final manifest readiness is recorded. No publication or GitHub push has been performed.

## Access attempt update — November 12

The researcher ran the one-clip command. The saved attempt returned `AuthenticationError`, HTTP 401, after about one second, with no received transcript. The assistant verified the saved status and preserved the original checkpoint. [Failure/recovery record](../results/metrics/validation_api_access_401_20261112_verified.json). This establishes failed authentication, not an ASR accuracy result or a verified billing outcome.

[Official error guidance](https://developers.openai.com/api/docs/guides/error-codes) lists invalid/revoked keys, organization/project mismatch, permissions and IP restrictions among 401 causes. First correct or replace the private API key in the intended funded project. Do not paste credentials into chat. The existing command intentionally stops on its saved unresolved attempt and will not prompt for another key.

Prepared [a separate one-request retry manifest](../data/manifests/validation_api_access_retry1_20261112.json) using the identical WAV, reference and request settings, linking the original failed checkpoint by checksum. It has not been executed. After correcting the credential, the researcher can run:

```powershell
Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe src/run_evaluation.py --manifest data/manifests/validation_api_access_retry1_20261112.json --system whisper_api --execute --max-requests 1
```

The first line clears only the current terminal's environment variable so the hidden key prompt is used. The second command permits one fresh validation attempt; it does not overwrite the original failure. Keep the final summary or a new non-secret error, and stop if it fails. Access and held-out readiness remain pending.

## Second 401: diagnose authentication before another audio request

The saved explicit retry also returned `AuthenticationError`, HTTP 401. There are two observed one-request failures in separate checkpoints. Later reruns printed `STOP: saved unresolved attempt` and did not submit new calls. Both failures remain preserved. No additional audio retry has been prepared or executed at this stage.

Run the separate diagnostic in the VS Code terminal:

```powershell
.\.venv\Scripts\python.exe src/check_api_auth.py
```

It reads `OPENAI_API_KEY` when set, otherwise prompts for the complete key. The safe result records `credential_source` as `environment` or `hidden_prompt`. It prints only the character count and basic formatting flags, never key characters. Malformed input (for example quotes, control characters from paste, whitespace inside the key or a masked preview) stops before a network request. The expected `sk-` prefix is a basic format check, not proof that a key is valid.

If input passes those checks, it performs exactly one [model metadata GET request](https://developers.openai.com/api/reference/resources/models/methods/retrieve) for `whisper-1`, with SDK retries disabled, without uploading audio or requesting transcription. This separates authentication/model-read access from speech transcription. It reports only approved error codes, status and request ID; provider exception messages/bodies can contain secrets and are not printed. A safe report is saved to the ignored `.cache/api_auth_diagnostic.json` for follow-up.

Organization/project environment override presence is reported as booleans. The diagnostic uses the same inherited override behavior as the runner; inspect those settings if indicated. A metadata 403/404 may reflect model-read permissions and does not by itself establish whether audio transcription is allowed. Metadata success does not verify transcription permissions or billing. Interpret the sanitized result before deciding on a further audio request.

Four real-SDK/in-memory-transport tests validate the metadata-only request, no automatic retry, malformed-input checks and non-disclosure when the provider echoes a key inside errors. The full offline suite now has 84 passing tests. No diagnostic network request was executed by the assistant; the researcher must enter the key privately in their terminal. Do not send the key or a screenshot containing it.

## Requested environment-variable method

The diagnostic now honors `OPENAI_API_KEY` like the transcription runner. In PowerShell, run the first command separately, then paste the key at its prompt and press Enter:

```powershell
$asrApiSecret = Read-Host "Paste OpenAI API key" -AsSecureString
```

After that prompt returns, run:

```powershell
$env:OPENAI_API_KEY = [System.Net.NetworkCredential]::new("", $asrApiSecret).Password
Remove-Variable asrApiSecret
.\.venv\Scripts\python.exe src/check_api_auth.py
```

This puts the key in the current terminal's process environment without writing its literal value into command history or source files. It is available to Python processes launched from that terminal and ends when that terminal closes. Do not print the environment variable. A CLI regression test confirms environment precedence, hidden-prompt fallback and secret-free report/output. The current full suite has 85 passing tests. Authentication success is still unverified; setting a variable cannot repair an invalid/revoked credential by itself.

## Preferred private-file method — requested after terminal paste trouble

Both scripts now automatically read `%LOCALAPPDATA%\Research-asr\.env` before consulting the terminal environment. On this computer that is `C:\Users\ADMIN\AppData\Local\Research-asr\.env`, outside the project's OneDrive and Git folders. The file contains one setting:

```dotenv
OPENAI_API_KEY=PASTE_YOUR_COMPLETE_SECRET_KEY_HERE
```

The prepared file initially has an empty value. Open it in VS Code, paste the real key after `=`, save, then run `python src/check_api_auth.py` with the project interpreter. Its safe output reports `credential_source: local_env_file`. Do not run the transcription retry command yet; first inspect the authentication diagnostic. No repeated terminal secret input is needed. The private file takes precedence over the known stale one-control-character environment variable. If no private file exists, the prior environment/hidden-prompt fallback remains available.

The loader accepts only the one key assignment and optional comment/blank lines or matching quotes; it never executes file contents, prints the key or adds it to exported predictions. An empty/duplicate/malformed private file fails with a generic message rather than silently using an old environment value. No dotenv dependency was added. Tests isolate their credential files from the real private path; all 89 tests pass.

The repository's existing `.gitignore` excludes `.env` and `.env.*` files as well, but Git ignore rules do not prevent OneDrive or other backup/sync tools from uploading files. The chosen private path avoids this project's OneDrive folder and cannot be committed from this repository. Do not copy the populated file into the project, commit it, or share its contents. Authentication necessarily sends the key to OpenAI's API over HTTPS; local storage is not a promise that a usable credential is never transmitted.
