# Addendum v2.1 — Signed Resumption

**Frozen:** 2026-08-09. **Maker:** Ka'el. **CONTRACT ONLY. NO CODE.**
**Body unchanged:** `JOB_WORKER_SIGNED_RESUMPTION_PREREG_V2_2026-08-09.md`
sha256 `7cc5d17dd49d8a05df4718106606d7cc848dac9f75988de575ccc33ce90e97f5`.

Closes **only** B1–B5 from
`JOB_WORKER_SIGNED_RESUMPTION_PREREG_V2_BREAKER_VERDICT_KAIROS_2026-08-09.md`. Nothing else in
the body moves. All five findings were re-verified against the live code before repair; the
maker did not take them on report.

**Verification of the findings, independently:**
- B1 — `sha256(json(["/usr/local/bin/python3","repro.py"]))` = `c7cc8887…97de`, identical to the
  breaker's value, and provably invariant under any change to `repro.py` bytes. Confirmed.
- B2 — `km_agent/god_jobs.py:260` uses a literal `timeout=120`. Confirmed.
- B3 — interleaving holds: dropping only the lock leaves sequential P2 blocking while concurrent
  P3 double-executes. One ablation cannot flip both. Confirmed.
- B4, B5 — true of the body's own text. Confirmed.

---

## R1 (closes B1) — the signed route binds executed bytes, not filenames

`argv_sha256` is **withdrawn** and replaced by `route_manifest_sha256`.

The canonical route manifest is UTF-8 JSON, `sort_keys=True`, `separators=(",",":")`, no
trailing newline, exactly these keys:

```
argv, cwd_realpath, interpreter_realpath, interpreter_sha256, script_realpath, script_sha256
```

Frozen values for the one permitted route, resolved 2026-08-09:

| Key | Value |
|---|---|
| `argv` | `["/usr/local/bin/python3","repro.py"]` |
| `cwd_realpath` | `/Users/kenielmaldonado/claim30_repro` |
| `interpreter_realpath` | `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13` |
| `interpreter_sha256` | `8116faf25ab40b24bc5cd512ba42e6186464892a6d5d696954f18bc2be4f1072` |
| `script_realpath` | `/Users/kenielmaldonado/claim30_repro/repro.py` |
| `script_sha256` | `f0c0ec9eee57c022207491ac6fcd02e64ff908aefa8ed936ced064c860cb7636` |

`/usr/local/bin/python3` is a symlink, so the manifest binds the **resolved** interpreter and its
digest, not the symlink.

The worker recomputes the entire manifest **immediately before the executor call** and refuses on
any mismatch. Recomputation after verification is mandatory, not advisory.

**New rows:**

| # | Case | Expected | Executor calls |
|---|---|---|---|
| **A18** | `repro.py` bytes changed after verification, filename and cwd identical | BLOCK | 0 |
| **A19** | interpreter symlink repointed to a different binary after verification | BLOCK | 0 |

**New ablation:** remove `script_sha256` from the manifest → **A18 must succeed.**

---

## R2 (closes B2) — the signed wall-time is the actual timeout

The verified `max_wall_seconds` integer is passed **directly** as the executor's `timeout`,
capped at `min(signed_value, MAX_WALL)` where `MAX_WALL = 1500`. The literal `120` is not used on
this route. A signed value larger than `MAX_WALL` still refuses at A8.

A timeout is a **refusal outcome**, never a completion. It records `EXECUTION_TIMED_OUT` and must
not be reported as a successful run.

| # | Case | Expected |
|---|---|---|
| **A20** | `max_wall_seconds = 1`, stub sleeps 5s | terminated at ~1s, recorded `EXECUTION_TIMED_OUT`, **not** success |

**New ablation:** ignore the signed value and use the literal 120 → **A20 must succeed** (the
stub runs to completion).

---

## R3 (closes B3) — the nonce ablation splits in two, and the ledger is frozen

The body's single row "remove atomic nonce spend → P2 and P3" is **withdrawn**. Replaced by:

| Ablation | Attack that must then succeed | Attack that must still block |
|---|---|---|
| **N1** — remove the nonce check and spend entirely | **P2** (sequential replay executes) | — |
| **N2** — keep check and spend, remove **only** the lock / critical section | **P3** (two concurrent attempts both execute) | **P2** still blocks |

Two independent protections, two independent flips. Neither may claim the other's coverage.

**Spend ledger, frozen:**

- Absolute path: `/Users/kenielmaldonado/km_agent/state/execution_nonce_spent.jsonl`
- Format: one UTF-8 JSON object per line, keys `nonce`, `job_id`, `spent_at_utc`, newline
  terminated.
- A malformed, truncated, or partially written final line is **fail-closed**: the whole ledger is
  treated as unreadable and every authorization refuses until a human repairs it. A partial write
  never yields an unspent verdict.
- Lock: `fcntl.flock(LOCK_EX)` on the ledger file itself, held across re-read, append, `flush`,
  `os.fsync`, then released **before** the executor call.

| # | Case | Expected |
|---|---|---|
| **A21** | final ledger line truncated mid-record | BLOCK, 0 executor calls |

---

## R4 (closes B4) — ordered health decision table, pause dominates

The body's unordered four-state map is **withdrawn**. Health state is the **first matching rule**,
evaluated top down. The worker and the usefulness checker call the **same** function.

| # | Condition | State |
|---|---|---|
| 1 | execution pause marker present | **`PAUSED_BLOCKED`** |
| 2 | no receipt present | **`PARKED`** |
| 3 | trust root absent or failing custody checks | **`PARKED`** |
| 4 | signature absent, malformed, or fails verification | **`TAMPERED`** |
| 5 | receipt expired | **`PARKED`** |
| 6 | nonce already spent | **`PARKED`** |
| 7 | valid, unexpired, unspent, route manifest matches | **`ARMED`** |

Resolving the breaker's named overlaps: pause + valid → `PAUSED_BLOCKED`; pause + forged →
`PAUSED_BLOCKED`; expired + forged → `TAMPERED` (rule 4 precedes 5); spent + forged →
`TAMPERED`; trust root absent + receipt present → `PARKED`; valid unspent, no pause → `ARMED`.

**`PAUSED_BLOCKED` dominates ALLOW unconditionally.** When rule 1 fires and a tamper condition
also exists, the tamper fact is surfaced as a secondary flag on the same record; it never
promotes the state and never permits execution. `ARMED` is a non-green armed state, not a healthy
one. No generic `UNKNOWN` may be emitted by either caller.

---

## R5 (closes B5) — field schema, exact types, no coercion

Every signed field, plus the unsigned sibling. Types are JSON types. **A boolean is never
accepted where an integer is required.** No normalization, casting, trimming, or Unicode folding
occurs before signature verification; the bytes are verified first, parsed second.

| Field | Type | Format / bounds |
|---|---|---|
| `schema_version` | integer | exactly `2`; `true`/`2.0`/`"2"` refuse |
| `state` | string | exactly `EXECUTION_AUTHORIZED` |
| `job_id` | string | nonempty, ≤ 128 chars, no NUL, no control chars |
| `job_digest` | string | exactly 64 lowercase hex |
| `tool` | string | exactly `repro` |
| `allowed_cwd` | string | nonempty, absolute POSIX path |
| `route_manifest_sha256` | string | exactly 64 lowercase hex |
| `max_wall_seconds` | integer | `1 ≤ n ≤ 1500`; bool, float, numeric string refuse |
| `expires_at` | string | RFC 3339 with explicit `Z` or `±HH:MM`; naive refuses |
| `nonce` | string | exactly 32 lowercase hex, single use |
| `signature` | string | ASCII-armored SSH signature beginning `-----BEGIN SSH SIGNATURE-----`; **not** part of the signed payload; written UTF-8 to the worker-generated `0600` temp file |

Any key outside this set, or any missing key, refuses before verification.

| # | Case | Expected |
|---|---|---|
| **A22** | `max_wall_seconds: true` | BLOCK |
| **A23** | `nonce` uppercase or wrong length | BLOCK |
| **A24** | unexpected extra key in the payload | BLOCK |

---

## Unchanged and not reopened

Everything the breaker listed as passing stands: the versioned candidate and commit ordering,
asymmetric signatures with no HMAC, the fixed principal `keniel-owner` and namespace
`km-agent-execution-authorization`, the pinned verifier binary, no-shell, stdin payload, the
worker-generated signature path, the `/etc` → `/private/etc` realpath custody treatment, one
`repro` route, one authorization at the executor boundary with spend-before-execute and
at-most-once, ledger deletion as an explicitly excluded same-user bypass, and the four-stage
evidence ladder.

**Advisory accepted:** the freeze commit also carried `.gitignore`, so "committed alone" was
imprecise. No code was in it. Recorded, not defended.

## Freeze rule

Body hash `7cc5d17d…e97f5` is unchanged. Re-break covers **B1–B5 plus retained v2 invariants
only**. No implementation, trust-root provisioning, signature request, or executor call is
authorized until PASS.
