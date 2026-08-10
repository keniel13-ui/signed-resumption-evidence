# Independent Code Re-Break Verdict — Signed Resumption Repair `bba4c1a…`

**Date:** 2026-08-09 EDT  
**Breaker:** Grok / Aethar (continuity after Kairos platform interrupt mid re-break)  
**Maker:** Ka'el  
**Target commit:** `6451338` — *Repair C1-C4 from the independent code breakers*  
**Target implementation SHA-256:** `bba4c1a4513db19475bdaec95348b03247f091081bbf89935d145f0c6cf32000`  

**Prior BLOCK (preserved; not recycled onto this hash):**  
implementation `1d7fb9cb…83eb` @ `2dae89e` —  
`JOB_WORKER_SIGNED_RESUMPTION_V2_1_CODE_BREAKER_VERDICT_AETHAR_2026-08-09.md`.

**Harness:** `SIGNED_RESUMPTION_V2_1_CODE_BREAKER_HARNESS_KAIROS_2026-08-09.py`  
(updated by Kairos to pin `bba4c1a…` and exercise `execute_authorized_job`)  
**Harness SHA-256:** `ac99302b6092d5c173567d20c686dea8255897c97cec50a5a76d983e67a9bab9`  

This seat did not write the implementation. Candidate documents and live worker were not edited.

---

## Integrity pin

| Artifact | SHA-256 | Status |
|---|---|---|
| Body v2 | `7cc5d17dd49d8a05df4718106606d7cc848dac9f75988de575ccc33ce90e97f5` | frozen, unchanged |
| Addendum v2.1 | `ac3f5e9b8241e988c11287a00f0b9d2063aa8802dd28313e7178e8b1faa37ef5` | frozen, unchanged |
| Implementation | `bba4c1a4513db19475bdaec95348b03247f091081bbf89935d145f0c6cf32000` | **this attack** |
| Live `job_worker.py` | `63d4e84413037114abf7df5f0709bf5f2d6b0e9d717f40afa64fd77c5d4e315f` | **untouched** |

Candidate repo clean @ `6451338`.  
`git show 6451338` touches only `signed_resumption.py` (+89 / −2 vs blocked `2dae89e`).

---

## Procedural history (still visible)

1. Implementation first appeared at `2dae89e` **before** the assigned v2.1 contract re-break finished.  
2. That first code hash was independently **BLOCKED** (C1–C4).  
3. Repair commit `6451338` addresses those four only.  
4. This verdict is a **clean attack on the new hash**. It does not clear `1d7fb9cb…`.

Contract paper (body + v2.1) remains **PASS** from the earlier Aethar contract re-break.

---

## Verdict: **PASS — repaired implementation meets the independent harness bar**

Harness exit code **0**, `"verdict": "PASS"`, `artifact_integrity.all_match: true`.

### Prior defects — re-tested closed on `bba4c1a…`

| Prior | Required | Live harness result |
|---|---|---|
| **C1** job_digest unused | bind content after verify, before spend | **A4** → `RECEIPT_NOT_BOUND_TO_THIS_JOB_CONTENT`, 0 execs |
| **C2** no owned executor | single boundary owns run + timeout | **A17** → `ROUTE_CHANGED_AFTER_AUTHORIZATION`, 0 execs; **A20** → `EXECUTION_TIMED_OUT`, 1 exec, `success: false` |
| **C3** no raw size-before-parse | raw ingress | **raw oversize** → `RECEIPT_TOO_LARGE`, 0 execs; `parse_receipt` size check before `json.loads` |
| **C4** space `expires_at` | RFC 3339 only | **R5 space** → `EXPIRES_AT_NOT_RFC3339`, 0 execs |

### Positive / retained rows (green)

| Row | Result |
|---|---|
| P1 | ALLOW, 1 executor call, `EXECUTION_COMPLETED`, stdout `ORIGINAL` |
| P2 replay | `NONCE_ALREADY_SPENT`, 0 execs |
| P3 concurrent | one ALLOW + one `NONCE_ALREADY_SPENT`, **1** total route exec |
| A3 wrong key | `SIGNATURE_INVALID`, 0 execs |
| A18 script pre-auth | `ROUTE_MANIFEST_MISMATCH`, 0 execs |
| A19 interpreter repoint | `ROUTE_MANIFEST_MISMATCH`, 0 execs |
| A21 truncated ledger | `NONCE_LEDGER_TRUNCATED`, 0 execs |
| A22 / A23 / A24 | integer / nonce / extra-key refuses, 0 execs |
| Health pause | `PAUSED_BLOCKED` |
| Live worker | still frozen hash |

---

## What this PASS authorizes

| Allowed | Still forbidden |
|---|---|
| Treat `bba4c1a…` / `6451338` as the **implementation candidate that cleared the independent code bar** | Installing trust root or holding private keys in any agent |
| Wire **only** `execute_authorized_job` (not bare `authorize` + external run) into a later worker integration | Live P1 / LaunchAgent enablement without Keniel + integration plan |
| Integration design / dry-run planning against frozen Config defaults | Broadening tools beyond `repro` |
| | Recycling this PASS onto any other implementation hash |

**Not yet earned:** live independent ALLOW under root-owned trust file and off-device operator signature (evidence ladder stages 3–4). That is a **later** gate after integration, not this module break.

---

## Advisories (not blockers for this hash)

1. **`authorize()` remains a public spend-without-run entry.** It correctly spends the nonce and returns timeout. Production wiring must call **`execute_authorized_job` only**. Calling `authorize` then running the argv elsewhere re-opens the A17 class. Document that in the integration freeze.  
2. **Parsed dict still accepted** when the caller already holds a dict (raw path is for bytes). Size bound applies on the raw path. Acceptable if ingress is only raw or only trusted in-process construction.  
3. **`job_digest` definition** (fields `id`/`assign`/`text`) lives in code and is noted by the maker as needing a later contract freeze line. Matching the live worker’s digest is correct for integration; freeze the exact field set in the next paper commit so it cannot drift.  
4. **Platform interrupts** cut Kairos mid-flight twice. Continuity seats must re-run the harness on the **current** hash (done here), never paste an old BLOCK/PASS onto a new digest.

---

## Gate state

```
body v2     7cc5d17d…e97f5   PASS (contract)
addendum    ac3f5e9b…37ef5   PASS (contract)
code 1d7fb9cb…83eb           BLOCK (preserved receipt)
code bba4c1a…2000 @ 6451338  PASS (this re-break)
live worker 63d4e844…e315f   untouched
```

**Next bricks (in order):**

1. **Integration freeze (maker):** how `job_worker` / allowlist will call **only** `execute_authorized_job`, with Config production paths, without broadening scope.  
2. **Independent integration/code re-break** if any glue is written.  
3. **Keniel (human, parallel):** outside A–L ask to one runner other than Ali — does not block integration.  
4. **Later:** operator trust-root + single off-device signature + one live P1 — only after integration PASS.

No unrelated outreach or article work was opened by this re-break.
