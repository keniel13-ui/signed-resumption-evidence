# Integration Freeze — wiring signed resumption into `job_worker.py`

**Frozen:** 2026-08-09. **Maker:** Ka'el. **CONTRACT ONLY. NO WORKER EDIT EXISTS.**
**Breaker: assigned by Keniel. Not Ka'el.**

Cleared to reach this point by two independent verdicts: contract v2.1 PASS, and code PASS on
`signed_resumption.py` sha256
`bba4c1a4513db19475bdaec95348b03247f091081bbf89935d145f0c6cf32000` (commit `6451338`).

**This is the first artifact in the lane that touches the live worker.** It touches it on paper
only. `km_agent/job_worker.py` remains at sha256
`63d4e84413037114abf7df5f0709bf5f2d6b0e9d717f40afa64fd77c5d4e315f` until this freeze PASSes and
the glue itself clears an independent break.

---

## The regression floor — this is the point of the whole document

On 2026-07-31 the default-deny worker survived **19 independent attacks with zero executor
calls**, and `execution_decision()` had no reachable `True`. Integration opens exactly one
position. **Everything else must behave identically to that verdict.**

If any attack from the 07-31 verdict newly reaches an executor, integration is a **regression**
and is reverted regardless of how well the signed route performs.

---

## Call sites, read from source at `63d4e844…e315f`

| Line | Site | Today | After |
|---|---|---|---|
| `343` | `run_headless()` → `execution_decision(job, cwd)` | always refuses | **unchanged, still always refuses** |
| `431` | `process_one()` → `execution_decision(job, cwd)` | authorizes **before** the route is derived | **removed from the signed path**; retained for every other path |
| `437-438` | `key = prompt…split()[0]`; `if key in god_jobs.ALLOWLIST` | route derived *after* authorization | route derived **first**, then authorized |
| `440` | `god_jobs.run_allowlisted(key)` | executes | **not reached on the signed route**; `execute_authorized_job()` owns that call |

The ordering inversion at `431` versus `437` is the K3 defect. Integration fixes it by deriving
the route before any authorization decision.

---

## The wiring, exactly

1. In `process_one()`, derive `key` **before** any authorization call.
2. **If `key == "repro"` and a receipt file is present:** call
   `signed_resumption.execute_authorized_job(job, receipt, cfg)` and nothing else. Do **not**
   call `execution_decision()`, and do **not** call `god_jobs.run_allowlisted()`.
3. **Every other case** — any other allowlist key, freeform prompts, `AUTO:`/`EXEC:`, and both
   headless paths — falls through to the existing `execution_decision()`, which still has no
   reachable `True`.
4. `run_headless()` at line `343` is not modified.
5. The usefulness checker imports `signed_resumption.health_state` and stops computing its own
   state. It must not implement a second signature policy.
6. `import signed_resumption` resolves to the reviewed module by absolute path. A stale copy on
   `sys.path` shadowing it is a refusal, not a fallback: the worker verifies the module file's
   sha256 equals `bba4c1a4…2000` at import and refuses to run the signed route otherwise.

**Authorization count on the signed route: exactly one, inside `execute_authorized_job`.**

---

## Result bar

| # | Case | Expected | Executor calls |
|---|---|---|---|
| **I1** | queued `repro` job, valid signed receipt | ALLOW, runs once | 1 |
| **I2** | queued `repro` job, no receipt | BLOCK | 0 |
| **I3** | all 19 attacks from the 2026-07-31 breaker verdict, replayed verbatim | BLOCK, exactly as then | **0** |
| **I4** | `adapter`, `loose`, `suite-status`, `suite-log`, `eye` with a valid `repro` receipt | BLOCK | 0 |
| **I5** | freeform `AUTO:` / `EXEC:` prompt with a valid `repro` receipt | BLOCK | 0 |
| **I6** | headless path with a valid `repro` receipt | BLOCK at line 343 | 0 |
| **I7** | pause marker present, valid receipt, `repro` queued | BLOCK, `PAUSED_BLOCKED` | 0 |
| **I8** | `signed_resumption.py` shadowed by a modified copy on `sys.path` | BLOCK, module digest mismatch | 0 |
| **I9** | receipt valid but `job_id` belongs to a different queued job | BLOCK | 0 |
| **I10** | checker and worker disagree on health state for the same inputs | **impossible by construction** — one shared function; a disagreement is a defect |

## Ablations

| Remove | Attack that must then succeed |
|---|---|
| the `key == "repro"` guard | I4 (another allowlist key executes on a `repro` receipt) |
| route-derivation-before-authorization ordering | I4 |
| the module digest check | I8 |
| pause dominance in the signed path | I7 |

---

## How this can come out wrong

- **The 19-attack replay is paraphrased rather than replayed.** It must be the same cases from
  `JOB_WORKER_BREAKER_VERDICT_2026-07-31.md`, not a fresh set that happens to pass.
- **`execution_decision()` is weakened** to make the signed path convenient. It must keep having
  no reachable `True`.
- **The receipt is read from a path the job can influence.** The receipt location is fixed in
  worker constants, never derived from job text.
- **I1 is made to pass by a fixture key while the row is reported as independent.** I1 here is
  still K5 stage 2 at best. Operator provisioning and live P1 remain later stages.
- **Integration is declared done without running I3.** The regression floor is the deliverable;
  the new capability is not.

---

## Rollback

Live worker hash before: `63d4e84413037114abf7df5f0709bf5f2d6b0e9d717f40afa64fd77c5d4e315f`.
Recorded here so a revert is a byte comparison rather than a memory. The pre-integration file is
committed to the candidate repo before the edit, so rollback is `git checkout`, not reconstruction.

## Still forbidden after this freeze PASSes

Trust-root installation, any agent holding or requesting the private key, any live P1 run, any
additional route, and any article. Those are later rungs on the K5 ladder and none of them are
unlocked by integration.

## Freeze rule

No row moves after this hash is recorded. The breaker attacks the glue at its own hash, builds
its own harness, replaces every executor with a counting stub, and replays the 07-31 nineteen
verbatim. A row passes only if the decision **and** the count match.
