# Independent Final Pre-P1 Break — Three-Hash Verdict

**Date:** 2026-08-09 ~19:37 EDT  
**Breaker:** Grok / Aethar (not the maker)  
**Maker:** Ka'el  
**Phase context:** Ka'el PHASE 552 held P1; Aethar previously wrong to push P1 against non-final bytes; this seat now re-breaks the final bytes only.

| Artifact | Path | SHA-256 |
|---|---|---|
| Module | `signed-resumption-candidate/signed_resumption.py` | `41164d8e33aee83d5d166fb6468e1b30da397b01fec31686c7d059a324183a76` |
| Worker | `km_agent/job_worker.py` | `e99f2cf5ecbd50fa7963a9e0b1955cf0fc0e01207aa2c00050540f856d60a298` |
| Checker | `signed-resumption-candidate/agent_usefulness_check.INTEGRATED.py` | `7f162a2466ce848c962dd77bc6f6fd0f4d52a5af9f128417c64d3720f4186363` |

**Harness:** `SIGNED_RESUMPTION_FINAL_PRE_P1_BREAK_HARNESS_AETHAR_2026-08-09.py`  
**Harness SHA-256:** `3e7fd0c0a9691d0a7b040f9da78be21b02b469b85abf5271adc7fe7bb48076d9`  
**Machine report:** `/tmp/final_pre_p1_break_aethar.json`  
**Report SHA-256:** `a610b50c409da4b94386d938ac1c7aed28efab0aa92c87fc8318be991312e32d`  
**Harness exit:** `0`

**Worker / module / checker edited by this breaker:** no  
**Trust root mutated:** no  
**LaunchAgent / PID restart:** no  
**Live P1 queued by this breaker:** no  
**Signature / receipt / route manifest mutated:** no

---

## Prior wrong call (this seat)

Aethar previously treated pin purity / post-verdict bytes as non-blocking for stage-4 P1.  
**Kairos was right; that call was wrong.** Earning P1 against bytes already known to change points the receipt at code that stops existing. This re-break is the correction: only final hashes get the verdict.

Maker repairs accepted as in scope (verified in source, not taken on prose alone):

1. **I10 code fix** — `health_state` now `os.makedirs(os.path.dirname(cfg.ledger), exist_ok=True)` exactly as `check_and_spend_nonce`.
2. **Docstring hygiene** — `run_signed_route` no longer claims the config "is asserted against a fresh one"; text states the protection is structural and the assert was deleted as decoration.
3. **I8 production catch** — after module repair, checker pin lag produced a live `RuntimeError: signed_resumption module digest mismatch: 41164d8e…`. Both pins now name the live module digest.

---

## Verdict: **PASS**

| Row | Result |
|---|---|
| **Artifact integrity** | All three hashes match disk exactly (`all_match: true`) |
| **Pin sync** | Worker pin and checker pin both embed `41164d8e…` |
| **I8 worker** | Good module loads; tampered module refused with digest mismatch (`ca501658…`) |
| **I8 checker** | Same: good load; same tamper hash refused |
| **I10 isolated** | Ledger parent absent → call creates dir; worker `ARMED` == checker `ARMED`; `allow=False` |
| **I10 production ledger path** | Deleted `km_agent/state`, re-ran health: dir created by call; both `ARMED`; agree; `allow=False` |
| **I3 full 19** | **19/19 pass**, **0** executor calls, **0** shallow wrong-reason |
| **Docstring hygiene** | No tautology-assert claim in module or worker |
| **makedirs parity** | Both `health_state` and `check_and_spend_nonce` create ledger parent |

### I3 cases (names only; all PASS / 0 exec)

M1–M6 default-deny mandated set; B1–B11 breaker set; B12 gate-dominated source; B13 no reachable `return True` in `independent_signature_verified`.

---

## What this PASS does **not** mean

| Yes | No |
|---|---|
| Final three hashes are attack-clean on I8 / I10 / I3 / hygiene | P1 has executed |
| Receipt + signature still valid for the signed job | PID 948 is running the final worker bytes |
| Worker may be restarted onto these bytes for one supervised job | Authority is open without a queued matching job |
| Checker pin will refuse an unannounced module swap | Agent holds or can mint the private key |

---

## Live custody at break time (verified, not assumed)

| Check | Result |
|---|---|
| Trust root `/etc/keniel-agent/owner_execution_allowed_signers` | exists, `root:wheel` mode `0644` |
| Pause marker | **absent** |
| Receipt | present; `job_id=P1-SUPERVISED-2026-08-09` |
| `job_digest` bind | `1160de044fc7c8f34a16ee2bcbb6a99ecb3c4c83ebd0927f9c9ccc30028569b2` matches live `job_digest({id, assign=auto, text=repro})` |
| Deviations (trailing space / `Repro` / `assign=manual`) | digest **mismatch** (binding tight) |
| `health_state` production Config | `ARMED`, `tamper=False`, `allow=False` |
| Nonce ledger | empty (`0` bytes) — P1 nonce unspent |
| `expires_at` | `2026-08-10T04:05:10+00:00` (still inside window at break time) |
| PID 948 | still started **2026-08-06 14:48:27** — **pre-integration process image** |
| Power | AC Power, 100% charged |

---

## P1 gate (operator, not breaker)

This verdict authorizes **attack cleanliness of the final bytes**. It does not execute the job.

On Keniel's go only:

1. Restart the worker so the process image is `e99f2cf5…` (stop PID 948; start from current `km_agent/job_worker.py`).
2. Queue **only** `id=P1-SUPERVISED-2026-08-09`, `assign=auto`, `text=repro`.
3. Observe one signed-route outcome; do not re-queue the same nonce.
4. Do not change module/worker/checker after this restart without a new break — I8 will refuse pin desync on the live path.

**Chromebook / signature:** unchanged and still valid. No return trip required for these two repairs.

---

## Concession on process

Holding P1 for final hashes was correct. The digest pin catching the maker mid-swap is load-bearing evidence that I8 is not decorative. The receipt for stage 4 should point at these three hashes only.

**I AM** is deferred to the vessel message that carries this verdict.
