# Independent Breaker Verdict — Integration Addendum (I-B1 / I-B2)

**Date:** 2026-08-09 EDT  
**Breaker:** Grok / Aethar (assigned re-break; not the maker)  
**Maker:** Ka'el  
**Candidate:** `signed-resumption-candidate/JOB_WORKER_SIGNED_RESUMPTION_INTEGRATION_ADDENDUM_2026-08-09.md`  
**Candidate SHA-256:** `b06c1781bc5fc8cd40fbc512ee30f8076cff2c0d4feeab8f3442514482e75829`  
**Freeze commit:** `cf8d895` (addendum-only; freeze body file byte-diff **empty** vs `1228976`)  
**Body freeze (unchanged):** `74fcec1591c5dac30efd3b768583ff4808a391b40e01a08c95d23e95068fadf8`  
**Prior integration BLOCK:** `JOB_WORKER_SIGNED_RESUMPTION_INTEGRATION_FREEZE_BREAKER_VERDICT_AETHAR_2026-08-09.md` (`a134d765…6d11`), as **re-graded** in chat (two hard seams, not four)  

**Live worker:** `63d4e84413037114abf7df5f0709bf5f2d6b0e9d717f40afa64fd77c5d4e315f` — **untouched**  
**Implementation pin:** `bba4c1a4513db19475bdaec95348b03247f091081bbf89935d145f0c6cf32000`  
**Candidate / worker edited by this breaker:** no  

---

## Scope of this re-break

Per the addendum freeze rule and the breaker’s own re-grade:

| Item | Treatment |
|---|---|
| **I-B1 / IR1** | Hard — must close |
| **I-B2 / IR2** | Hard — must close |
| **I-B3 / IR3** | Residual binding — check, not re-inflate |
| **I-B4 / IR4** | Advisory restatement — check, not re-inflate |
| Body freeze invariants | Retained (I3 floor, single door, module digest, etc.) |

No glue code is required for this paper re-break. No worker implementation was written.

---

## Integrity probes (this turn)

| Check | Result |
|---|---|
| Addendum hash | `b06c1781…5829` matches disk |
| Body freeze hash | `74fcec15…adf8` unchanged (git diff empty) |
| Commit `cf8d895` | addendum file only (+137 lines) |
| Live worker | still `63d4e844…e315f` |
| Pre-integration snapshot | still byte-equal to live worker |
| `EXECUTION_AUTHORIZATION` in live worker | lines 37–38; resolves to `/Users/kenielmaldonado/km_agent/JOB_WORKER_EXECUTION_AUTHORIZED.json` — **matches IR1** |
| `strip_auto_prefix` | live line 321 — **matches IR3 citation** |
| Default `Config()` equality | `Config() == Config()` true; any field override unequal (frozen dataclass) |

---

## Verdict: **PASS — integration paper ready for glue implementation under the rules below**

IR1 and IR2 close the two hard seams. The demotions were respected, not re-inflated. Body freeze stays intact. Live worker remains unedited.

---

## IR1 — PASS (closes I-B1)

**Finding was:** “fixed constant” without a named constant.  
**Repair:** pin the **existing** live constant  

`EXECUTION_AUTHORIZATION` →  
`/Users/kenielmaldonado/km_agent/JOB_WORKER_EXECUTION_AUTHORIZED.json`

No new path. Inherits 07-31 attack surface on that file.  

Also frozen: raw-byte read → `parse_receipt`; path never from job/env/argv/receipt;  
`realpath` of opened file must equal the constant; I13/I14 rows.

**Live check:** constant exists at the cited lines; resolved path equals the frozen absolute string on this host.  

**Why this is the right shape:** inventing a parallel receipt path would dodge prior attacks. Reusing `EXECUTION_AUTHORIZATION` does not.

---

## IR2 — PASS (closes I-B2)

**Finding was:** `cfg` unfrozen — security boundary injectable.  
**Repair:**

1. Signed route builds `cfg = signed_resumption.Config()` **with no arguments**.  
2. Before use: `if cfg != signed_resumption.Config(): raise Refusal("NON_PRODUCTION_CONFIG_ON_SIGNED_ROUTE")`  
   — right-hand side is a **fresh** default (maker named the self-compare failure mode; the freeze shows the correct pattern).  
3. Evidence consequence: non-default Config I1 stays **maker fixture**, not integration evidence.  
4. Rows I11/I12/I15 + ablation (remove assertion → I11 must succeed).

**Live check:** `Config` is `frozen=True`; defaults include production trust root,  
`require_root_owned=True`, pause path matching live `EXECUTION_PAUSE`, cwd/argv aligned with the signed `repro` route freeze. Overrides are unequal to `Config()`.

This was the strongest original finding. It is closed on paper.

---

## IR3 — residual OK (not re-inflated)

Key derivation bound by name to live `strip_auto_prefix` + first token lowercased.  
Freeze body already showed the split formula; naming the function was the residual.  
Checked against live line 321. **Not promoted to a hard seam.**

---

## IR4 — advisory OK (not re-inflated)

Restates: legacy `independent_signature_verified` / `execution_decision` stay fail-closed  
until a separate freeze. Already required by body freeze “do not weaken  
`execution_decision`.” **Not a new seam.**

---

## Retained body invariants (still bind glue)

- I3: 19 attacks from `JOB_WORKER_BREAKER_VERDICT_2026-07-31.md`, verbatim, counting stubs, 0 execs.  
- Signed path: **only** `execute_authorized_job` (not bare `authorize` + external run).  
- Route before auth; headless 343 unchanged; module digest `bba4c1a…2000`; I4–I10 intents.  
- No trust root / agent key / live P1 / extra routes / article after paper PASS.

---

## Advisories for the glue breaker (not paper blockers)

1. **Assertion implementation** must compare against a **fresh** `Config()`, not `cfg != cfg`.  
   The addendum already freezes the correct pattern; glue code must not “simplify” it.  
2. **I15** (trust root absent → BLOCK) is the honest production state today — I1 green only under  
   breaker fixture / provisioned root remains K5-ladder-bound as the addendum states.  
3. **Dual readers of `EXECUTION_AUTHORIZATION`:** legacy `execution_decision` still expects  
   schema v1 semantics; signed path uses schema 2 via `parse_receipt`. Glue must not let a  
   v2 receipt authorize non-`repro` keys through the legacy True branch (body + IR4).  
4. When glue lands, the **code** breaker rebuilds its own harness; this paper PASS does not  
   clear unimplemented worker edits.

---

## Gate state

```
integration freeze body   74fcec15…adf8   (unchanged)
integration addendum      b06c1781…5829   PASS (this re-break)
signed_resumption.py      bba4c1a4…2000   PASS (prior code re-break)
live job_worker.py        63d4e844…e315f  UNTOUCHED
```

| Now allowed | Still forbidden |
|---|---|
| Implement **glue only** per body + this addendum | Trust-root install, agent-held private key |
| Independent **code** break of the worker-edit commit | Live P1, extra routes, articles |
| | Calling paper PASS a production enablement |

**Next brick (maker):** worker integration commit implementing body+addendum; pre-image remains `63d4e844…`.  
**Next brick (breaker ≠ maker):** attack that glue hash with counting stubs + I3 + I11–I15.  
**Parallel (Keniel):** outside A–L ask.

---

## Continuity

Maker correctly followed the breaker’s **re-grade** (two hard seams), verified live  
`EXECUTION_AUTHORIZATION` and the unfrozen `cfg` hole before repairing, and froze the  
self-compare failure mode for Config. That is the right response to a imperfect first  
verdict. This seat confirms the repair on the exact hash without reopening demoted items.
