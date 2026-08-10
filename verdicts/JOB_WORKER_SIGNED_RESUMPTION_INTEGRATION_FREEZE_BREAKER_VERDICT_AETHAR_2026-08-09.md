# Independent Breaker Verdict — Signed Resumption Integration Freeze

**Date:** 2026-08-09 EDT  
**Breaker:** Grok / Aethar (assigned by Keniel; not the maker)  
**Maker:** Ka'el  
**Candidate:** `signed-resumption-candidate/JOB_WORKER_SIGNED_RESUMPTION_INTEGRATION_FREEZE_2026-08-09.md`  
**Candidate SHA-256:** `74fcec1591c5dac30efd3b768583ff4808a391b40e01a08c95d23e95068fadf8`  
**Freeze commit:** `1228976`  
**Live worker (must stay frozen until glue PASS):** `63d4e84413037114abf7df5f0709bf5f2d6b0e9d717f40afa64fd77c5d4e315f`  
**Implementation pin (code PASS):** `bba4c1a4513db19475bdaec95348b03247f091081bbf89935d145f0c6cf32000` @ `6451338`  

**Candidate edited by this breaker:** no  
**`km_agent/job_worker.py` edited:** no  
**Trust root / private key / live P1:** no  

---

## Integrity probes (this turn)

| Check | Result |
|---|---|
| Freeze hash | `74fcec15…adf8` matches disk |
| Live worker hash | `63d4e844…e315f` (unchanged) |
| Snapshot `job_worker.PRE_INTEGRATION_63d4e844.py` | **byte-identical** to live worker |
| Implementation | still `bba4c1a…2000` |
| Claimed call sites 343 / 431 / 437–438 / 440 | **match live source** (`run_headless` / `process_one` / allowlist / `run_allowlisted`) |
| `independent_signature_verified` | only `False` returns (trust root absent / not implemented) |
| `execution_decision` | has a theoretical `return True` **after** ISV; **not reachable today** while ISV always fails |

---

## Verdict: **BLOCK — bounded integration delta, then re-break**

The freeze is the right *kind* of document: regression floor (I3), single `repro` door, route-before-auth, module digest, no trust-root unlock. Those intents stand.

It is **not** implementation-ready. Four load-bearing freezes are missing. Without them, a glue author can invent insecure constants, still green I1 with a fixture Config, and claim the freeze was followed.

This is **not** a redesign. One short addendum can close all four.

---

## What already holds (do not reopen)

1. **Regression floor I3** — replaying the **19** cases from  
   `JOB_WORKER_BREAKER_VERDICT_2026-07-31.md` (6 mandated + 13 breaker-own) with  
   counting stubs is the correct primary deliverable.  
2. **Single owned boundary on the signed path** — `execute_authorized_job` only; no  
   `execution_decision` + `run_allowlisted` on that path. Matches code PASS advisory.  
3. **Route-before-authorization** for the K3 inversion at 431 vs 437–438 is correctly named  
   and verified against source.  
4. **Headless line 343 unchanged** — I6 is sound.  
5. **I4 / I5 / I7 / I8 / I9 / I10 intents** are the right attack shapes.  
6. **Rollback** via committed pre-integration snapshot is real and hash-checked.  
7. **Still forbidden after PASS** (trust root, agent key, live P1, extra routes, article)  
   correctly keeps K5 later stages closed.

---

## I-B1 — Receipt location is asserted “fixed” but never frozen

Freeze §“How this can come out wrong” says the receipt path must be a worker constant,  
never derived from job text. The wiring says “if a receipt file is present.”

**Missing:** absolute path (or `AGENT_DIR`-relative constant **name + value**), read mode  
(raw bytes → `parse_receipt` vs pre-parsed dict), and refuse rules when the file is  
absent / empty / unreadable.

Without that, an implementer can:

- take the path from job text or an environment variable the job controls; or  
- “find” a receipt beside the job payload.

Either breaks the anti-self-path rule the freeze itself names.

### Required repair

Freeze, at minimum:

- constant identifier and resolved absolute path for the production receipt file;  
- that the worker reads **raw bytes** and calls `signed_resumption.parse_receipt` (or  
  equivalent size-before-parse path);  
- that job text, job id, and Telegram payload **must not** influence the path.

---

## I-B2 — Production `Config` construction is not frozen

Wiring step 2 calls  
`signed_resumption.execute_authorized_job(job, receipt, cfg)`  
but never freezes how `cfg` is built.

`Config` carries trust root, ledger, pause marker, argv, cwd, and  
`require_root_owned`. The code PASS already warned: **only**  
`execute_authorized_job` is the safe boundary, and production Config must be pinned.

Without a frozen production Config table, I1 can pass with breaker-style fixture  
paths while live glue points elsewhere (or the reverse).

### Required repair

Freeze the exact production `Config` field values (or the exact constructor call) used  
on the live worker for the signed `repro` route, including:

- `trust_root` / `trust_root_realpath` / `require_root_owned`  
- `ledger`  
- `pause_marker`  
- `argv` / `cwd` (must match the route freeze already on body+v2.1 for this host)  

And freeze: **glue must not accept a Config supplied by the job or receipt.**

---

## I-B3 — Route key derivation is not pinned to the live formula

Freeze says “derive `key` before any authorization” but not **how**.

Live `process_one` does:

```text
prompt = strip_auto_prefix(raw)   # strips auto: / exec: / /auto 
key = prompt.strip().lower().split()[0] if prompt.strip() else ""
```

If the glue uses a different tokenizer (full string, last token, regex), I4/I5/I2  
change meaning without any row moving on paper.

### Required repair

Freeze the derivation as **identical** to current `strip_auto_prefix` + first  
whitespace token lowercased (cite function names / behavior, not only line numbers).  
Line numbers may be cited as evidence; **behavior is binding**.

---

## I-B4 — Non-signed path fail-closed is time-dependent, not integration-bound

Freeze: every non-signed case “falls through to `execution_decision()`, which still has  
no reachable `True`.”

Live fact: `execution_decision` **contains**  
`return True, "independently verified…"` after `independent_signature_verified`.  
Today ISV only returns `False`, so True is unreachable. That matches 07-31.

Integration does **not** freeze that ISV remains unimplemented / always-false for the  
**legacy schema_version=1** path. A later partial implementation of the old verifier  
(or a confused dual-trust-root) would reopen **all allowlist keys** through the  
post-auth allowlist branch, even if the signed `repro` door is perfect.

### Required repair

Freeze an explicit invariant for this integration:

- For every path that still calls `execution_decision`,  
  `independent_signature_verified` **must continue to return only False**  
  (or the legacy True branch must be deleted / unreachable by construction),  
  **until a separate freeze** opens any non-`repro` signed route.

I3’s 19-attack replay is necessary but not sufficient without this invariant.

---

## Advisories (not blockers alone)

1. **Job close / Telegram after I1** — freeze does not say whether `close_job` /  
   `telegram` still run after `execute_authorized_job`. Operational, not security, if  
   executors stay counted.  
2. **`authorize()` still public on the module** — glue must not call it without  
   `execute_authorized_job` (already in code PASS). Restate in the addendum one line.  
3. **`job_digest` field set** still code-pinned, not contract-pinned — keep for next  
   **non-integration** freeze; do not open v2.2 spiral here if I-B1–B4 can close alone.  
4. **Line numbers** — verified correct today; pin behavior + function names so renumbers  
   do not void the freeze.

---

## Gate state

**Integration freeze `74fcec15…adf8` is BLOCKED.**

| Allowed now | Forbidden |
|---|---|
| One bounded **integration addendum** closing I-B1–I-B4 only | Editing `km_agent/job_worker.py` |
| Independent re-break of freeze+addendum (this seat or other non-maker) | Trust root, agent key, live P1 |
| | New routes, articles, Ali/German work as part of this gate |
| | Treating code PASS `bba4c1a…` as integration PASS |

**Live worker remains `63d4e844…e315f`.** Snapshot equality holds.

**Next brick (maker):** integration addendum v1 for I-B1–I-B4; body freeze hash unchanged.  
**Next brick (breaker):** re-break exact addendum hash; only then may glue land in a later commit.  
**Parallel (Keniel):** outside A–L ask — does not block this gate.

---

## Non-goals

No worker implementation was written or reviewed as code in this turn.  
No harness against unimplemented glue was required: freeze rule is **paper-before-glue**,  
and the paper does not yet pin the constants the glue must use.
