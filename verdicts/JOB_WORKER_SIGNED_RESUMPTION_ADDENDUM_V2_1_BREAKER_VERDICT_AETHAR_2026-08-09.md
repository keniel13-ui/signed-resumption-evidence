# Independent Breaker Verdict — Signed Resumption Addendum v2.1

**Date:** 2026-08-09 EDT  
**Breaker:** Grok / Aethar (independent seat; not the maker)  
**Maker:** Ka'el  
**Assignment context:** Kairos seat hit a runtime content block mid re-break; Keniel ordered continuity. This seat re-breaks the frozen v2.1 hash only.

## Artifacts (unchanged by this breaker)

| Artifact | Path | SHA-256 |
|---|---|---|
| Body v2 (unchanged) | `signed-resumption-candidate/JOB_WORKER_SIGNED_RESUMPTION_PREREG_V2_2026-08-09.md` | `7cc5d17dd49d8a05df4718106606d7cc848dac9f75988de575ccc33ce90e97f5` |
| Addendum v2.1 | `signed-resumption-candidate/JOB_WORKER_SIGNED_RESUMPTION_ADDENDUM_V2_1_2026-08-09.md` | `ac3f5e9b8241e988c11287a00f0b9d2063aa8802dd28313e7178e8b1faa37ef5` |
| Freeze commit | `358cb98` | addendum-only (+180 lines); body file **byte-diff 0** vs `1b6ded7` |
| Live worker | `km_agent/job_worker.py` | `63d4e84413037114abf7df5f0709bf5f2d6b0e9d717f40afa64fd77c5d4e315f` |
| Prior BLOCK | `JOB_WORKER_SIGNED_RESUMPTION_PREREG_V2_BREAKER_VERDICT_KAIROS_2026-08-09.md` | controlling B1–B5 source |

**Candidate edited by this breaker:** no  
**Implementation written:** no  
**Python in candidate repo:** none  
**Trust root / signature / executor call:** none  

Prior v2 BLOCK that this addendum must close:
`JOB_WORKER_SIGNED_RESUMPTION_PREREG_V2_BREAKER_VERDICT_KAIROS_2026-08-09.md`.

---

## Verdict: **PASS — contract ready for implementation under the freeze rules below**

v2.1 closes **all five** Kairos B-findings with named rows, ablations, and recomputation rules. Live machine values match the frozen route table. Body hash is unchanged. Live worker is untouched. No code exists.

This PASS authorizes **implementation of body + v2.1 only**, then a **separate non-maker code break**. It does **not** authorize trust-root provisioning, operator signing, or a live P1 run.

---

## Live probes (breaker, this turn)

1. Candidate `git` clean at `358cb98`; only non-code files: `.gitignore`, body v2, addendum v2.1.  
2. `git diff 1b6ded7 358cb98 -- JOB_WORKER_SIGNED_RESUMPTION_PREREG_V2_2026-08-09.md` → empty (0 bytes).  
3. `shasum -a 256` of body and addendum match the table above.  
4. Live `job_worker.py` still `63d4e844…e315f`.  
5. Frozen route components re-derived on this host **2026-08-09**:

| Probe | Result |
|---|---|
| `realpath(/usr/local/bin/python3)` | `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13` |
| interpreter SHA-256 | `8116faf25ab40b24bc5cd512ba42e6186464892a6d5d696954f18bc2be4f1072` (**matches** R1 table) |
| `repro.py` SHA-256 | `f0c0ec9eee57c022207491ac6fcd02e64ff908aefa8ed936ced064c860cb7636` (**matches** R1 table) |
| argv JSON SHA-256 | `c7cc8887535876a72b68fd3e4d09852fad11965dd7a26edbc1bfaac8824897de` (still the B1-era argv-only digest; now **insufficient alone**, as required) |
| full route-manifest SHA-256 (canonical JSON of R1 keys) | `b98e4fa34c4c5b6b8d0ce7fdec42ba040dc12ce293d7ee1eb20de5d191b8a7a3` |
| `god_jobs.py` still carries literal `timeout=120` | confirmed line ~260 — B2 repair must **override** this for the signed route |

---

## B1 — PASS (closed by R1)

**Finding was:** signature bound argv **text**, not executed bytes.  
**Repair:** `argv_sha256` **withdrawn**; signed field is `route_manifest_sha256` over  
`argv, cwd_realpath, interpreter_realpath, interpreter_sha256, script_realpath, script_sha256`  
with recompute **immediately before** the executor call.  

**Rows:** A18 (script bytes change, name/cwd identical → BLOCK, 0 calls); A19 (interpreter symlink repoint → BLOCK).  
**Ablation:** strip `script_sha256` from the manifest → A18 must **succeed**.  

**Live check:** frozen interpreter and script digests recompute exactly on this machine.  
A valid receipt can no longer authorize a different program under the same filename without failing the pre-exec recompute. **B1 closed.**

---

## B2 — PASS (closed by R2 + R5 type rule)

**Finding was:** `max_wall_seconds` signed but not bound to the real subprocess timeout (live path still hard-codes 120).  
**Repair:** verified integer is the executor `timeout`, capped `min(signed, MAX_WALL=1500)`; values above MAX_WALL still refuse at A8; timeout is `EXECUTION_TIMED_OUT`, never success.  
**Row A20:** signed `1`, stub sleeps 5s → kill ~1s, not success.  
**Ablation:** ignore signed value, use literal 120 → A20 must **succeed** (proves the binding is load-bearing).  
**R5:** `max_wall_seconds` is strict integer; bool/float/string refuse.  

**Live check:** the current `timeout=120` still exists in `god_jobs.py` — that is the **defect the implementation must leave**, not a contract hole. The contract now **forbids** using that literal on this route. **B2 closed.**

---

## B3 — PASS (closed by R3)

**Finding was:** one ablation claimed both sequential replay (P2) and concurrent double-exec (P3). Interleaving shows those are different protections.  
**Repair:** body dual-claim row **withdrawn**. Replaced by:

| Ablation | Must flip | Must still block |
|---|---|---|
| **N1** remove check+spend entirely | **P2** | — |
| **N2** keep check+spend, remove **only** lock/critical section | **P3** (two execs) | **P2** still blocks |

Ledger path, JSONL line format, fail-closed truncated final line (**A21**), and `flock` held through re-read/append/fsync then released **before** exec are frozen.  

Two protections, two flips. **B3 closed.**

---

## B4 — PASS (closed by R4)

**Finding was:** health map unordered; pause vs ARMED conflict; forged+expired dual labels.  
**Repair:** ordered decision table, first match wins; worker and usefulness checker **same function**. Pause is rule 1 → `PAUSED_BLOCKED` dominates ALLOW unconditionally. Named overlaps from the v2 verdict are resolved in-text (pause+valid, pause+forged, expired+forged → TAMPERED via rule 4 before 5, spent+forged → TAMPERED, trust-root absent → PARKED, clean valid → ARMED). No generic `UNKNOWN`.  

Body's unordered four-state map is **withdrawn**. **B4 closed.**

---

## B5 — PASS (closed by R5)

**Finding was:** “frozen to the byte” without field types / signature representation.  
**Repair:** full field table with JSON types and bounds; signature is ASCII-armored SSH signature string; **no coercion before verification** (verify bytes first, parse second); boolean never accepted where integer required; extra or missing keys refuse before verification.  
**Rows:** A22 (`max_wall_seconds: true`), A23 (nonce case/length), A24 (extra key).  

Together with R1, the signed key set is the R5 set with `route_manifest_sha256` instead of `argv_sha256`. **B5 closed.**

---

## Retained v2 invariants (must not reopen) — still hold

- Versioned candidate repo + commit-before-code ordering.  
- Asymmetric OpenSSH only; principal `keniel-owner`; namespace `km-agent-execution-authorization`; fixed verifier argv; no shell; stdin payload; worker-generated `0600` signature path.  
- Trust-root realpath `/private/etc/keniel-agent/owner_execution_allowed_signers` with root/non-writable checks.  
- Exactly one `repro` route; closed unsignable tools/fallbacks.  
- One authorize at executor boundary; spend-before-execute; at-most-once; ledger deletion remains an **excluded** same-user bypass (not claimed solved).  
- Evidence ladder: maker fixture → breaker fixture → operator provisioning → live P1; no stage may borrow a later stage's strength.  
- Live worker remains `63d4e844…e315f` until a later implementation commit after this PASS.

---

## Advisories (not blockers)

1. **Body ablation table text is stale in place.** The body still *prints*  
   `argv_sha256 binding → A7` and `atomic nonce spend → P2 and P3`.  
   R1 and R3 **withdraw** those rows. Implementation and the code-breaker must treat the  
   **addendum withdrawals as controlling**. Do not re-open B1/B3 to reprint the body; this is  
   documentation debt inside an otherwise closed repair.  
2. **Computed constant.** The full frozen route's  
   `route_manifest_sha256 = b98e4fa34c4c5b6b8d0ce7fdec42ba040dc12ce293d7ee1eb20de5d191b8a7a3`  
   recomputes from R1's table; the addendum freezes the components rather than printing this  
   hex. Either form is sufficient; printing it in the implementation notes would reduce error.  
3. **Machine-local absolute paths** in R1 are correct for this host and match live probes.  
   Portability is out of scope for this contract.

---

## Gate state

**Contract set { body v2 `7cc5d17d…e97f5` + addendum v2.1 `ac3f5e9b…37ef5` } is PASS for implementation.**

| Allowed now | Still forbidden until later gates |
|---|---|
| Implement signed-resumption against body+v2.1 only | Trust-root install / private key handling by any agent |
| Independent **code** breaker on the implementation hash | Operator live signature request without Keniel |
| | Live P1 / any executor call under the new path before code PASS |
| | Broadening routes beyond `repro` |
| | Ali package, German message, article publish, API credit work as part of this gate |

**Next brick (maker):** implementation in a **later** commit (not this freeze).  
**Next brick (breaker, not maker):** code attack on the exact implementation hash.  
**Next brick (Keniel, parallel, human):** outside A–L ask to one runner other than Ali — does not block implementation.

---

## Non-goals confirmed

No Ali/German/Mandate/SlamJunk/API work was opened by this re-break.  
No candidate file was modified. Working tree remains clean at `358cb98`.
