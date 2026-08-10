# Independent Integration Code Breaker Verdict — Live `job_worker.py`

**Date:** 2026-08-09 EDT  
**Breaker:** Grok / Aethar (assigned by Keniel; not the maker)  
**Maker:** Ka'el  
**Target:** live `km_agent/job_worker.py`  
**Target SHA-256:** `ba7204822494c2ff81295986e5d53405077e8bdcc2ca56be9d48545e5081a08d`  
**Pre-integration baseline:** `63d4e84413037114abf7df5f0709bf5f2d6b0e9d717f40afa64fd77c5d4e315f`  
**Module pin:** `bba4c1a4513db19475bdaec95348b03247f091081bbf89935d145f0c6cf32000`  
**Paper cleared to implement:** freeze `74fcec15…adf8` + addendum `b06c1781…5829` (PASS)  

**Harness (this seat, not the maker’s):**  
`SIGNED_RESUMPTION_INTEGRATION_CODE_BREAKER_HARNESS_AETHAR_2026-08-09.py`  

**Worker edited by this breaker:** no  
**Trust root installed / private key / LaunchAgent restart / live P1:** no  

---

## Power (named, not soft-pedaled)

At break start: **Battery Power, discharging, Connected: No, Charging: No, Cycle Count 999, Condition: Service Recommended.**  
Maker’s mid-edit isolation strategy (build on copy, single verified `cp`) was the right call.  
This break did not require writing the live worker.

---

## Verdict: **PASS — integration glue holds the regression floor**

Harness exit **0**, `"verdict": "PASS"`.

This is **not** operator provisioning and **not** a live independent ALLOW.  
It means: the **one open door** is wired as frozen, and the **19-attack default-deny floor still has zero executor calls** under counting stubs.

---

## Integrity

| Artifact | Expected | Observed |
|---|---|---|
| Live worker | `ba720482…1a08d` | match |
| `signed_resumption.py` | `bba4c1a4…2000` | match |
| Pre-integration snapshot | `63d4e844…e315f` | match |
| Live == candidate `job_worker.INTEGRATED.py` | — | **byte-equal** at break time |

---

## Structure (source)

| Check | Result |
|---|---|
| Route derived **before** `execution_decision` | yes |
| Signed branch **before** default-deny | yes |
| Signed branch calls `execute_authorized_job` | yes |
| Receipt from `EXECUTION_AUTHORIZATION` raw bytes | yes |
| `Config()` zero-arg + assert vs fresh `Config()` | yes |
| Module digest pin `bba4c1a…` | yes |
| `independent_signature_verified` has **no** `return True` | yes |

K3 inversion (auth at old 431 before route at 437) is **gone**.

---

## I3 — regression floor (the row that decides)

**19 / 19 cases, total allowlist calls = 0, total non-ssh route subprocess calls = 0.**

Replayed against an isolated `HOME` / rebound `EXECUTION_*` paths so production markers were not used as the attack surface, with every executor replaced by a counting stub (`god_jobs.run_allowlisted` + non-`ssh-keygen` `subprocess.run`).

| Set | Count | Executor calls |
|---|---|---|
| Mandated M1–M6 (07-31 table) | 6 | **0** |
| Breaker-own B1–B13 (07-31 family) | 13 | **0** |

Maker correctly named that a pause-first shallow check is **not** I3. This seat ran the floor.

---

## Integration rows (pre-provision, fail-closed)

| Row | Result |
|---|---|
| **I2** repro, no receipt | 0 exec |
| **I4** adapter/loose/suite-*/eye with receipt file present | 0 exec (signed door not taken) |
| **I5** AUTO:/EXEC: freeform with receipt present | 0 exec |
| **I6** `run_headless` | code 126 BLOCKED, 0 exec |
| **I8** shadowed module digest | RuntimeError digest mismatch |
| **I9** / bad receipt on repro door | refuse, **no** allowlist fallback |
| **IR2** Config default equality / override inequality | holds |
| **IR3** `EXEC: repro` without receipt | 0 exec |

**I1 ALLOW (valid signed receipt, 1 run)** is **not** claimed. Trust root is unprovisioned; production pause may dominate `Config()` defaults. Freeze/K5: that ALLOW is a **later** ladder stage.  
**Binding for this stage:** when the signed door is attempted and refuses, execution **must not** fall through to `run_allowlisted` / headless. **Verified.**

---

## What this PASS authorizes

| Allowed | Forbidden |
|---|---|
| Treat `ba720482…` as integration glue that cleared independent I3 + door checks | Installing trust root / agent private key |
| Plan operator handoff (off-device sign of schema-v2 receipt) as **next security rung** | Declaring “execution authority open” or live unattended P1 done |
| Keep LaunchAgent on old or new bytes only under Keniel’s explicit ops choice | Extra routes beyond `repro` |
| | Quietly weakening `execution_decision` / ISV |

**Still zero production execution authority** until trust root + valid owner signature + pause policy allow a deliberate P1.

---

## Advisories

1. **Power hardware** — Service Recommended, 999 cycles, adapter not delivering. Do not treat “AC Power” string as charged. Prefer AC confirmed charging before further live-file surgery.  
2. **Running process** may still hold old bytes until restart — maker stated this; ops, not this verdict.  
3. **I1 green** requires a separate, non-maker attack under controlled fixture/trust conditions if claimed as evidence; do not promote maker fixtures.  
4. Rollback remains `cp` from `job_worker.PRE_INTEGRATION_63d4e844.py` (hash still `63d4e844…`).

---

## Gate state

```
paper integration freeze+addendum   PASS
module signed_resumption.py         PASS (bba4c1a…)
live worker glue ba720482…          PASS (this break) — I3 floor holds
live execution authority            STILL ZERO (no trust root / no P1)
```

**Next bricks**

1. **Keniel (human):** outside A–L ask to one non-Ali runner (parallel).  
2. **Ops (Keniel):** only when ready — trust-root + one off-device signature + supervised P1 under freeze rules.  
3. **No new contract spiral** before those.

---

## Continuity

Maker built on a copy under real power risk, hash-verified the cutover, and correctly refused to call a shallow pause check “I3.” This seat attacked the core: **counting stubs + nineteen + door non-fallback.** Major move. Floor held.
