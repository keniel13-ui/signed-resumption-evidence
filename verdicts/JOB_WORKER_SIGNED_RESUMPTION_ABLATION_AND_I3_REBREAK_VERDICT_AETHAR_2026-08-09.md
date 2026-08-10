# Independent Re-Break — Ablations + Full I3 Floor (shipped hash)

**Date:** 2026-08-09 EDT  
**Breaker:** Grok / Aethar (not the maker)  
**Maker stage-1 runs (Ka'el PHASE 537–538):** accepted as **non-adjudicating**; this seat re-ran.

| Pin | SHA-256 |
|---|---|
| Live worker (shipped) | `df50689768455f9f55a86374e621006a00436c1ddae69bb92c530fe6c165db05` |
| Live module | `bba4c1a4513db19475bdaec95348b03247f091081bbf89935d145f0c6cf32000` |

**Harnesses (this seat):**  
- Ablations: `SIGNED_RESUMPTION_ABLATION_HARNESS_AETHAR_2026-08-09.py` (temp **copy** mutations only)  
- I3 floor: re-ran maker’s `I3_REGRESSION_FLOOR_HARNESS_KAEL_2026-08-09.py` (asserts worker hash before run)

**Live module/worker mutated by this breaker:** no  
**Trust root / P1 / LaunchAgent restart:** no  

---

## Verdict: **PASS — with disclosed N2 natural-timing caveat**

### A. Ablations (module protections)

| Protection removed | Paired attack | Baseline | Ablated | Flip |
|---|---|---|---|---|
| signature verification | wrong key | `SIGNATURE_INVALID` | ALLOW | ✓ |
| trust-root custody | mismatched `trust_root_realpath` | `TRUST_ROOT_PATH_UNEXPECTED` | ALLOW | ✓ |
| job-digest binding | changed job body | `RECEIPT_NOT_BOUND_TO_THIS_JOB_CONTENT` | ALLOW | ✓ |
| cwd binding | wrong `allowed_cwd` | `ALLOWED_CWD_MISMATCH` | ALLOW | ✓ |
| tool binding | tool≠repro | `TOOL_NOT_ON_THE_SIGNED_ROUTE` | ALLOW | ✓ |
| script_sha256 / route recompute | script bytes swapped | `ROUTE_MANIFEST_MISMATCH` | ALLOW | ✓ |
| nonce check+spend (**N1**) | sequential replay | `NONCE_ALREADY_SPENT` | ALLOW | ✓ |
| expiry check | expired receipt | `RECEIPT_EXPIRED` | ALLOW | ✓ |

**8/8 flipped.** Live module hash re-verified after every row (`bba4c1a…`).

### B. N2 (lock-only removal) — honest split

| Variant | Result |
|---|---|
| Natural timing (2 threads) | **1 ALLOW** — **no flip** |
| Widened window: 50ms delay between ledger read and append (disclosed) | **2/2 and 10/10 ALLOW** — flip **demonstrated** |

**Contract-honest statement for any article:**  
The TOCTOU window is real and the lock closes it, but **N2 is not demonstrated at natural timing on this machine**. Only under a **disclosed widened window**. The lock is not decoration; natural-timing flip is not claimed.

### C. Full I3 floor on **shipped** worker `df506897…`

Re-ran Ka'el harness (hash-asserted target):

```
19/19 cases pass · total executor calls: 0
cases still refusing on the SHALLOWEST check: 0 (none)
target: df50689768455f9f55a86374…
```

Intended deep reasons observed for the previously shallow-poisoned class (15–17):  
wall-time bound, timezone-aware expiry, signature-not-implemented — not job-content mismatch.

This closes Kairos/Ka'el gap: full 19 never fully executed on shipped bytes before; now it has, from a **second seat**.

---

## What this does / does not clear

| Cleared | Not cleared |
|---|---|
| Ablation gap for publishable mechanism claims (with N2 caveat) | **P1** live independent ALLOW (stage 4) |
| Full I3 on `df506897…` with zero executors + non-shallow reasons | Operator trust root / private key path |
| Job-digest protection is load-bearing (not C5-absent) | “Natural-timing N2 flip” |

**Article spine “remove either protection and the attack succeeds”:** now supported for the eight table rows; N2 only with disclosed widen.

**Still required before “solution shipped / publish mechanism as proven live”:** Keniel P1 per runbook under real charging + trust root.

---

## Evidence class

- This re-break = **independent stage-2** on ablations + I3.  
- Maker runs = stage-1 corroboration only.  
- P1 remains **human-only**.

---

## Gate state

```
module bba4c1a…     ablations 8/8 flip + N2 widened-only   PASS (this seat)
worker df506897…    I3 19/19 zero exec, non-shallow        PASS (this seat)
live P1             NOT RUN
outside counter     still 0 until ask sent
```

**Next:** P1 (Keniel) · outside ask (Keniel) · no new contract spiral.
