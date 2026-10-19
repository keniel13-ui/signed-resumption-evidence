# Reproducing the checks in this bundle

Everything here is stdlib Python plus OpenSSH's `ssh-keygen`. Nothing needs to be installed
from PyPI to verify the bundle or run the harnesses. Every command on this page was run on
macOS 15 (Darwin 24.6) with Python 3.9.6 and OpenSSH 9.9p2 before it was written down.

## Requirements

- Python 3.9 or newer
- `ssh-keygen` from OpenSSH 8.1 or newer (needed for `-Y sign` / `-Y verify`)
- A POSIX system (the module uses `fcntl`). The bundled module calls `/usr/bin/ssh-keygen`
  by absolute path, which exists on macOS and on common Linux distributions.

## 1. Verify the receipt and the bundle (read-only)

```bash
python3 tools/verify_bundle.py
```

This automates [VERIFY.md](../VERIFY.md) and adds cross-checks. Observed output:

```
PASS  evidence-sums      34 files match
PASS  shipped-bytes      3/3 match README and P1_RESULT
PASS  frozen-contracts   4/4 contracts match their frozen digests
PASS  pre-integration    matches the frozen base cited by PREREG_V2
PASS  payload            433 bytes, sha256 4ed5ecff82de...
PASS  module-payload     signed_resumption.canonical_payload == VERIFY.md payload
PASS  signature          Good "km-agent-execution-authorization" signature for keniel-owner with ED25519 key SHA256:EsftjEQJF0z4+fBDDZNEXmIUUK0ydtyijHqfsmRyfpA
PASS  tamper             modified payload refused (exit 255)
PASS  key-fingerprint    256 SHA256:EsftjEQJF0z4+fBDDZNEXmIUUK0ydtyijHqfsmRyfpA keniel-owner (ED25519)
PASS  module-accepts     validate_schema + verify_signature accept; tampered copy -> SIGNATURE_INVALID
PASS  p1-consistency     1 ledger entry = receipt nonce; replay refused NONCE_ALREADY_SPENT while the receipt was still unexpired
PASS  verdict-inventory  12 verdicts: 4 BLOCK, 8 PASS

12/12 checks passed
```

`--json` prints the same results as JSON. Exit status is 0 only if every check passes.

What each check means, and what it does not:

| Check | Establishes | Does not establish |
|---|---|---|
| `evidence-sums` | No evidence file changed since `tools/evidence.sha256` was generated from upstream `621ab4f` | Anything about the bytes before they were committed |
| `shipped-bytes` | The three shipped files hash to the README and P1_RESULT values | That those bytes are what ran (that is the operator's statement) |
| `frozen-contracts` | The four contract files hash to the digests cited in code and verdicts | When they were frozen |
| `signature`, `tamper`, `key-fingerprint` | VERIFY.md steps 1 to 3 | Key custody (see VERIFY.md) |
| `module-accepts` | The shipped module's own schema and signature code accept the receipt | The root-ownership custody checks, which need `/etc` and root, so a fixture Config with `require_root_owned=False` is used |
| `p1-consistency` | Receipt, nonce ledger, refusal record and worker log agree; the replay happened before expiry | That the log lines were not edited (they are not signed) |
| `verdict-inventory` | 12 verdict files, 4 BLOCK and 8 PASS, matching the README | That the review seats were independent |

The evidence manifest can also be checked with nothing but coreutils:

```bash
shasum -a 256 -c tools/evidence.sha256
```

## 2. Re-run the harnesses

The harnesses were written for the author's machine and read their inputs from absolute paths
under `/Users/kenielmaldonado/`. They cannot run elsewhere as committed, and they are evidence,
so they are not edited. `tools/run_harness.py` runs a temporary copy instead:

```bash
python3 tools/run_harness.py ABLATION_HARNESS_KAEL_2026-08-09.py
```

The runner:

1. refuses unless `signed_resumption.py` and `job_worker.INTEGRATED.py` hash to the README values;
2. builds a sandbox with a private `HOME`, copies those two files into it, and adds a stand-in
   `god_jobs` module (the author's real one is not in the bundle; every unpatched call to the
   stand-in raises);
3. rewrites only the two quoted input paths in a temporary copy of the harness, and prints each
   rewrite;
4. runs the copy with a timeout (`--timeout`, default 600 s) and removes the sandbox (`--keep`
   keeps it).

Observed on the machine above, against the final shipped bytes:

| Harness | Command | Observed |
|---|---|---|
| Module ablations | `python3 tools/run_harness.py ABLATION_HARNESS_KAEL_2026-08-09.py` | `8/8 ablations flipped` |
| A12 / A20 / I8 follow-up | `python3 tools/run_harness.py ABLATION_FOLLOWUP_A12_A20_I8_KAEL_2026-08-09.py` | A12, A20, I8 flip `YES`; I4a, I4b, I7 rows are structural (`NO` / `n/a` by design) |
| I4a / I7 removal | `python3 tools/run_harness.py ABLATION_I4A_I7_REMOVAL_TESTS_KAEL_2026-08-09.py` | I4a `YES`, I7 `YES`, happy path executor calls = 1 |
| N2 natural timing | `python3 tools/run_harness.py ABLATION_N2_NATURAL_TIMING_KAEL_2026-08-09.py` | baseline 1, ablated 1, `NOT DEMONSTRATED` |
| N2 widened window | `python3 tools/run_harness.py ABLATION_N2_WIDENED_WINDOW_KAEL_2026-08-09.py` | baseline 1, ablated 10, flip `YES` |
| I3 floor | `python3 tools/run_harness.py I3_REGRESSION_FLOOR_HARNESS_KAEL_2026-08-09.py` | refused (exit 2), see below |

The N2 rows are race experiments; your counts may differ. The recorded verdict also reports
natural-timing N2 as not demonstrated.

### Which bytes the recorded runs used

A re-run here is a run on the **final** shipped bytes, which is not always what the recorded
verdicts ran against:

- `verdicts/JOB_WORKER_SIGNED_RESUMPTION_ABLATION_AND_I3_REBREAK_VERDICT_AETHAR_2026-08-09.md`
  pins module `bba4c1a4...` and worker `df506897...`. The bundle ships module `41164d8e...` and
  worker `e99f2cf5...`. Neither earlier file is in the bundle.
- `I3_REGRESSION_FLOOR_HARNESS_KAEL_2026-08-09.py` asserts the worker hash `df506897...`, so the
  runner refuses it by default. `--retarget` runs the same 19 cases against the shipped worker
  and prints `RETARGETED RUN. Not the recorded experiment.`:

  ```bash
  python3 tools/run_harness.py --retarget I3_REGRESSION_FLOOR_HARNESS_KAEL_2026-08-09.py
  ```

  Observed: `19/19 cases pass · total executor calls: 0`, shallowest-check count 0.

Output of this runner is a reproduction attempt by whoever runs it. It is not a breaker verdict
and does not change the README's "External reproduction" count.

## 3. Tests and lint

```bash
python3 -m unittest discover -s tests -v   # 22 tests, about 10 s
```

The tests run `verify_bundle` against the committed bundle and against tampered copies in a
temporary directory, unit-test the runner, and re-run the four deterministic harnesses through
it. The bundle itself is never written.

Lint and format checks cover `tools/` and `tests/` only (see `ruff.toml`). The evidence files are
deliberately excluded and must never be reformatted.

```bash
python3 -m pip install ruff==0.17.1
ruff check .
ruff format --check .
```

CI (`.github/workflows/ci.yml`) runs the same commands on Ubuntu and macOS.
