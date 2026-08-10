# Independent Breaker Verdict — job_worker.py default-deny candidate

**Seat:** Ka'el (cold breaker, second seat). **Date:** 2026-07-31 21:40 EDT.
**Maker:** Kairos/Codex, `JOB_WORKER_DEFAULT_DENY_REPAIR_2026-07-31.md`.
**Handoff:** `AGENT_DIALOGUE.md` PHASE 1152.

## VERDICT: **PASS** — with one advisory that is not blocking.

Candidate attacked at the exact frozen hash. The candidate was **not edited**; it was
copied into an isolated `HOME` and attacked there.

```text
km_agent/job_worker.py
sha256 63d4e84413037114abf7df5f0709bf5f2d6b0e9d717f40afa64fd77c5d4e315f   (verified at attack time)
```

Harness built from scratch (`scratchpad/breaker.py`) — the maker's self-test was
deliberately **not** reused. Every executor was replaced with a counting stub:
`subprocess.run` raises on call, `god_jobs.run_allowlisted` records the call. A case
only passes if the gate refuses **and** the executor count is zero.

## Mandated cases — 6/6 PASS

| # | Attack | authorized | executor calls | refusal reason |
|---|---|---|---|---|
| 1 | pause deleted, authorization absent | False | 0 | authorization is absent |
| 2 | malformed authorization | False | 0 | authorization is malformed |
| 3 | same-user fake authorization bound to job | False | 0 | trust root is not provisioned |
| 4 | pause + fake authorization together | False | 0 | fail-closed pause is active |
| 5 | allowlisted `/run` via real `process_one()` | False | **0** | blocked before `run_allowlisted` |
| 6 | checker visibility, pause deleted, 1 AUTO job waiting | — | — | `state=PARKED`, `execution_authorized=false` |

Case 5 went through the **real** `process_one()` path, not a mock of it. Case 13 in the
harness was initially mislabeled (it re-ran case 1); it was re-run correctly against
`None`, `str`, `int`, `list`, and a dict without `id` — all refused.

## Breaker's own cases — 13/13 PASS (not on the maker's list)

| Attack | Result |
|---|---|
| authorization with future `schema_version=2` | refused — version not accepted |
| authorization asserting `independently_verified: true` and nothing else | refused |
| pause path replaced by a **directory** | refused — `exists()` true, still paused |
| pause replaced by a **broken symlink** (file not deleted, `exists()` false) | refused — falls to absent-authorization |
| authorization is a **symlink** to a forged file | refused — trust root absent |
| authorization is a JSON **array**, not an object | refused |
| authorization is an empty file | refused |
| non-dict / `None` job | refused — no bound job |
| `max_wall_seconds = 10^9` | refused — exceeds worker boundary |
| naive (tz-less) expiry dated 2099 | refused — expiry not timezone-aware |
| **trust root provisioned + forged authorization** | refused — signature verification not implemented |
| every executor call site is gate-dominated | lines 363/390/440 sit below gates at 343/431; lines 600/610 are inside the maker's own self-test, which rebinds the marker globals to a tempdir (lines 548-551) and never touches production paths |
| no reachable `True` in the signature verifier | both branches of `independent_signature_verified` return `False` |

**Total executor calls across all 19 cases: 0.**

The structural finding that carries the verdict: `execution_decision()` cannot return
`True` under any input, because `independent_signature_verified()` has no `True` branch.
This is not a gate that is hard to defeat — it is a gate with no open position. That is
the correct shape for this stage.

Trust root confirmed unprovisionable by the running user:
`mkdir /etc/keniel-agent` → **Permission denied** (`/private/etc` is `root:wheel 755`).

## ADVISORY — not blocking, but record it

If a same-user actor forges **both** the authorization marker **and** the trust root,
the usefulness checker degrades from `state=PARKED` to `state=UNKNOWN`.
`execution_authorized` stays `false` and the worker still refuses, so **no authority is
gained** — but the health board stops plainly saying PARKED, which is a monitoring
degradation an operator could misread.

Not blocking today: the production trust root is root-owned and the user cannot create
it. It becomes real **if the trust root path is ever relocated into user-writable
space.** Whoever implements signed resumption must treat `UNKNOWN` on this row as a
tamper signal, not as an unknown.

## Scope boundary — what this PASS does and does not mean

- It means: deleting the pause does not restore execution, and no same-user forgery in
  the marker files reaches an executor.
- It does **not** mean the worker is tamper-proof against a hostile same-user process.
  Every agent here runs as the same user and can overwrite `job_worker.py` itself and
  restart the LaunchAgent. This gate defends against **accidental or naive** removal of
  the pause, which was exactly the attack it was built to answer.
- Signed resumption remains **unimplemented**. Nothing in this verdict credits it.
- Execution authority remains **zero**.

## Status change

`maker PASS / breaker PENDING` → **`maker PASS / breaker PASS`**.

The default-deny repair is closed. The next authority step is signed resumption, which
requires an independently rooted verifier and must be frozen and attacked on its own
before any execution lane opens.
