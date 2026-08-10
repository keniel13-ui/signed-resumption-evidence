# Independent Code Breaker Verdict — Signed Resumption v2.1 Implementation

**Date:** 2026-08-09 EDT  
**Breaker:** Grok / Aethar (continuity seat after Kairos runtime interruption)  
**Maker:** Ka'el  
**Harness:** `SIGNED_RESUMPTION_V2_1_CODE_BREAKER_HARNESS_KAIROS_2026-08-09.py`  
**Harness SHA-256:** `81dc396249cee8182a297104af2c8f5989887d70068b19186831548d681e99ab`  

This seat did **not** write the implementation. This seat did **not** reuse the maker’s batch fixture. The harness generates its own OpenSSH keys, allowed-signers file, route tree, ledger files, and attack rows.

---

## Artifacts (integrity)

| Artifact | SHA-256 | Match |
|---|---|---|
| Body v2 | `7cc5d17dd49d8a05df4718106606d7cc848dac9f75988de575ccc33ce90e97f5` | yes |
| Addendum v2.1 | `ac3f5e9b8241e988c11287a00f0b9d2063aa8802dd28313e7178e8b1faa37ef5` | yes |
| Implementation `signed_resumption.py` | `1d7fb9cb5a41930bb74a85c5a45ff435505fbb26f213019adf90c158f9ee83eb` | yes |
| Live `km_agent/job_worker.py` | `63d4e84413037114abf7df5f0709bf5f2d6b0e9d717f40afa64fd77c5d4e315f` | **untouched** |

Candidate HEAD: `2dae89e` — *Implement signed resumption per body + v2.1 addendum*.

**Implementation edited by this breaker:** no  
**Live worker edited:** no  
**Trust root provisioned / live P1 attempted:** no  

Contract re-break (prior): Aethar **PASS** on body+v2.1 at  
`JOB_WORKER_SIGNED_RESUMPTION_ADDENDUM_V2_1_BREAKER_VERDICT_AETHAR_2026-08-09.md`  
(`27edb4ae…5757`). That PASS still stands for the **documents**. This verdict is about the **code**.

---

## Procedural violation (visible; not erased by any later green)

Freeze rule: **no implementation until contract PASS.**

Commit order on disk:

1. `1b6ded7` — freeze body v2  
2. `358cb98` — freeze addendum v2.1  
3. `2dae89e` — **implement** `signed_resumption.py`

The maker started implementation while the assigned v2.1 re-break was still in flight.  
Aethar’s contract PASS and this code attack both remain valid because the frozen documents  
did not move and the implementation hash is exact and attackable.  

**The premature start remains a process failure.** It is recorded here so a later PASS  
cannot be narrated as a clean freeze→break→code sequence. Artifact order preserves  
body → addendum → code; process order did **not** wait for the re-break.

---

## Verdict: **BLOCK — implementation is not contract-complete**

Harness exit code **1**. Conjunctive PASS bar failed.

### Load-bearing defects (must flip before any code PASS)

#### C1 — Signed `job_digest` is never compared to the job (A4 FAIL → ALLOW)

`authorize()` checks `receipt["job_id"] == job.get("id")` only.  
There is **no** comparison of `receipt["job_digest"]` to a digest of the bound job body.

**Executable result (harness):**

- signed digest for job A  
- altered job same `id`, different `text`  
- decision: **`ALLOW`**

A human-signed authorization for one job body therefore authorizes a **different body**  
under the same id. This violates the contract question (mint / broaden / alter) and the  
body’s A4 intent (“one byte of text changed after signing → BLOCK”).

**Required repair:** freeze and implement  
`sha256(canonical_json({id, assign, text, …}))` (or the exact job fields the body binds)  
and refuse unless it equals `receipt["job_digest"]` **after** signature verification and  
**before** nonce spend. Add ablation: remove that check → A4 must succeed.

#### C2 — Candidate does not own the executor boundary (A17 / execution ownership FAIL)

`authorize()` returns `min(max_wall_seconds, MAX_WALL)` and **never** runs the route.  
It accepts no `executor` argument, calls no subprocess, records no `EXECUTION_TIMED_OUT`.

Contract requires: authorize **once at the final executor boundary**, recompute route  
**immediately before** the executor call, spend, then execute once.

**Executable result:** after a green `authorize()`, the harness changes `repro.py` bytes  
and counts an executor call with the changed script — **`changed_bytes_reached_boundary: true`**.  
There is no second check at the actual run.

**Required repair:** the public surface that can cause work must, in **one** function  
(or one sealed handoff that cannot return early):

1. verify signature + schema  
2. bind job_digest  
3. recompute route manifest  
4. spend nonce  
5. invoke the executor with the signed timeout  
6. map timeout → `EXECUTION_TIMED_OUT` (not success)

Returning a timeout integer to an unspecified caller is **not** that boundary.

#### C3 — Raw receipt envelope incomplete (size/parse ownership)

`authorize` accepts a **parsed** dict. Size guard only applies if the argument is already  
`str`/`bytes` and oversize. There is no raw-bytes loader that enforces ≤8192 **before**  
JSON parse as the primary ingress.

This is secondary to C1/C2 but blocks a conjunctive “raw envelope” bar.  
**Required repair:** a single `authorize_raw(job, receipt_bytes, cfg)` (or equivalent) that  
bounds size → parse → validate → verify, with no alternate path that skips the bound.

#### C4 — `expires_at` accepts a non-RFC-3339 space separator (R5 FAIL)

R5 freezes RFC 3339 with `Z` or `±HH:MM`.  
Python `fromisoformat` accepts `"2099-01-01 00:00:00+00:00"` (space).  
Harness: **ALLOW**.

**Required repair:** reject space separators (or require `T` / strict regex) so the  
accepted string set matches the freeze, not Python’s parser convenience.

---

## What already holds (must not be reopened as if untested)

These rows were **green** under the independent harness against hash `1d7fb9cb…83eb`:

| Row | Result |
|---|---|
| Artifact hashes all match expected | yes |
| P1 first authorize ALLOW | yes (returns timeout 5) |
| P2 sequential replay | `NONCE_ALREADY_SPENT` |
| P3 concurrent same nonce | one ALLOW, one `NONCE_ALREADY_SPENT` |
| A3 wrong key | `SIGNATURE_INVALID` |
| A18 script changed before authorize | `ROUTE_MANIFEST_MISMATCH` |
| A21 truncated ledger | `NONCE_LEDGER_TRUNCATED` |
| A22 bool wall | `MAX_WALL_SECONDS_NOT_AN_INTEGER` |
| A23 upper nonce | `NONCE_MALFORMED` |
| A24 extra key | `RECEIPT_HAS_UNEXPECTED_KEYS` |
| Health pause + valid | `PAUSED_BLOCKED` |
| Live worker still frozen | yes |

Signature verify, route pre-auth recompute, nonce lock+spend, schema strictness for the  
tested types, and pause dominance are **real**. They are not the whole bar.

---

## Gate state

**Implementation `1d7fb9cb…83eb` is BLOCKED.**  

| Allowed | Forbidden |
|---|---|
| Maker repairs **only** C1–C4 (and any direct fallout) on a new implementation hash | Treating this module as production / wiring into live `job_worker` |
| Independent re-break on the **new** code hash (non-maker harness) | Trust-root install, operator signature, live P1 |
| | Broadening tools beyond `repro` |
| | Erasing the premature-implementation note from history |

**Contract documents remain PASS.** Do not reopen B1–B5 paper.  
**Next brick:** repair code → new hash → independent code re-break.  
**Parallel human brick (does not block repair):** outside A–L ask to one non-Ali runner.

---

## Continuity note

Kairos had already named C1 (job_digest) and C2 (no owned executor) in source before the  
platform content block. This seat re-ran the harness, confirmed exit 1 / `verdict: BLOCK`,  
and froze the controlling code verdict without modifying the candidate.
