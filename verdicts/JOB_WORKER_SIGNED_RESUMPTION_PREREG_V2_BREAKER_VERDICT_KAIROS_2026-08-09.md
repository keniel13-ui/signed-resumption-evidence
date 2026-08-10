# Independent Breaker Verdict — Signed Resumption Preregistration v2

**Date:** 2026-08-09 EDT  
**Breaker:** Kairos/Codex, separately live seat assigned by Keniel after Ka'el PHASE 524  
**Maker:** Ka'el  
**Candidate:** `signed-resumption-candidate/JOB_WORKER_SIGNED_RESUMPTION_PREREG_V2_2026-08-09.md`  
**Candidate SHA-256:** `7cc5d17dd49d8a05df4718106606d7cc848dac9f75988de575ccc33ce90e97f5`  
**Freeze commit:** `1b6ded7c8c955f573ab59ad07358bc518b28b7ab`  
**Frozen live worker SHA-256:** `63d4e84413037114abf7df5f0709bf5f2d6b0e9d717f40afa64fd77c5d4e315f`  
**Candidate edited by breaker:** no  
**Implementation written:** no  

## Verdict: **BLOCK — bounded v2.1 delta, then re-break**

v2 materially repairs v1. The candidate is now genuinely versioned before code;
the OpenSSH principal, namespace, fixed verifier argv, canonical JSON rules,
trust-root checks, one-route intent, at-most-once choice, and evidence tiers are
substantially stronger. A real independent fixture confirmed that the frozen
OpenSSH sign/verify primitive works with the stated namespace and principal.

The contract is still not implementation-ready. Five bounded seams let a valid
signature authorize behavior broader than the signed permission, make a required
ablation impossible as written, or let the worker and health checker disagree.

## Receipts and probes

- Candidate repository is clean at `1b6ded7`; no Python implementation exists.
- The freeze commit contains the preregistration and a non-code `.gitignore`.
  Therefore K1's freeze-before-implementation intent holds, although the phrase
  "committed alone" is literally imprecise. This is advisory, not a blocker.
- Live `km_agent/job_worker.py` still matches `63d4e844…e315f`.
- Frozen argv canonical JSON is
  `["/usr/local/bin/python3","repro.py"]`; SHA-256
  `c7cc8887535876a72b68fd3e4d09852fad11965dd7a26edbc1bfaac8824897de`.
- Current `repro.py` SHA-256 is
  `f0c0ec9eee57c022207491ac6fcd02e64ff908aefa8ed936ced064c860cb7636`.
- Current live allowlist executor uses `timeout=120` in
  `km_agent/god_jobs.py`.
- Independent harness:
  `SIGNED_RESUMPTION_V2_CONTRACT_BREAKER_HARNESS_KAIROS_2026-08-09.py`.
  It exits `1` because the contract invariants below do not hold; its OpenSSH
  fixture itself passes sign and verify.

## B1 — The signed route binds argv text, not the bytes that execute

K3 signs only the digest of the two argv strings. Neither the resolved interpreter
bytes nor `repro.py` bytes/commit are bound. Replacing `repro.py` with a different
program leaves `argv_sha256` exactly `c7cc8887…9de`.

That makes A17 unachievable for the most important post-verification route change:
the filename and cwd remain identical while the program changes. A valid receipt
can therefore execute work different from what the human approved without changing
any signed field. This violates the contract's own "mint, broaden, alter" question.

### Required repair

Freeze a canonical route manifest that includes at minimum:

- absolute argv;
- resolved interpreter path and SHA-256;
- absolute script path and SHA-256;
- real cwd; and
- the exact manifest SHA-256 carried in the signed payload.

Recompute it immediately before execution. Add a row that changes only `repro.py`
bytes after verification and requires BLOCK / zero executor calls. Binding a clean
Git commit is acceptable only if the implementation also verifies the executed
working tree matches that commit and rejects dirt.

## B2 — `max_wall_seconds` is signed but is not bound to the actual executor timeout

The contract rejects only a value above `MAX_WALL`. It never requires the real
subprocess timeout to equal or be capped by the signed value. The current executor
uses a literal 120 seconds. A receipt signed with `max_wall_seconds=1` can satisfy A8
while the action is allowed to run for 120 seconds.

### Required repair

The final executor must consume the verified integer directly as its timeout (or a
smaller fixed route ceiling). Add a row with a one-second signed limit and a sleeping
stub; it must time out without being reported as a successful completion. Freeze
strict integer typing so JSON `true`, floats, and numeric strings are not accepted as
wall-time integers.

## B3 — The nonce ablation conflates sequential replay with atomic concurrency

The table says removing **atomic nonce spend** must make both P2 and P3 succeed. A
mechanical interleaving disproves that:

- without a lock, the first sequential attempt records the nonce and the second
  sequential attempt still blocks; P2 does not flip;
- without a lock, two concurrent attempts can both observe unspent and both execute;
  P3 flips to two executor calls.

Atomicity is load-bearing for concurrency. The existence of the replay check/spend is
separately load-bearing for sequential replay. One ablation cannot honestly claim both.

### Required repair

Split the row:

1. remove nonce check/spend entirely -> P2 replays; and
2. retain check/spend but remove only the lock/atomic critical section -> P3 executes
   twice while sequential P2 still blocks.

Also freeze the spend-ledger absolute path, record format, and fail-closed behavior for
malformed or partially written records so crash handling is scoreable before code.

## B4 — The health-state table conflicts with pause dominance and has no precedence

K5 maps every valid, unexpired, unspent receipt to `ARMED`. A12 says the same receipt
with the pause marker present must BLOCK because pause dominates. The health table has
no pause state or precedence rule, so the shared verifier can report `ARMED` while the
worker refuses.

Other overlaps are also unresolved: a forged-and-expired receipt matches both
`TAMPERED` and `PARKED`; a spent receipt whose signature is now invalid does too. The
implementation can choose the visible state after the freeze.

### Required repair

Freeze an ordered health decision table. It must state the visible state for at least:
pause + valid receipt, pause + forged receipt, expired + forged, spent + forged, trust
root absent + receipt present, and valid unspent with no pause. Execution pause must
still dominate ALLOW even if tamper information is also surfaced.

## B5 — "Frozen to the byte" does not freeze field types or signature representation

K2 fixes the key set and JSON encoder, but not the accepted JSON type/shape for each
field. In particular, it does not freeze:

- nonempty string rules for `job_id`, `tool`, `allowed_cwd`, and `nonce`;
- lowercase 64-hex rules for `job_digest` and the route/argv digest;
- strict integer-not-boolean rules for `schema_version` and `max_wall_seconds`;
- the exact accepted timezone-aware `expires_at` string form; or
- `signature` as an ASCII-armored SSH signature string encoded to UTF-8 for the
  internally generated file.

Those choices affect the canonical bytes, parser behavior, replay key, and what the
off-device operator is asked to sign. They were explicitly required by v1 K2 and remain
post-freeze choices in v2.

### Required repair

Add a compact field-schema table with exact JSON type, format, and bounds for every
signed field and for the sibling `signature`. Reject booleans where integers are
required and reject normalization/coercion before signature verification.

## What passes and must not be reopened

- The candidate workspace and commit ordering now exist.
- Asymmetric signatures remain the correct primitive; no HMAC.
- The fixed OpenSSH principal `keniel-owner`, namespace
  `km-agent-execution-authorization`, verifier binary, no-shell rule, stdin payload,
  and internal signature path are sound.
- The `/etc` -> `/private/etc` realpath treatment and root/non-writable regular-file
  custody direction are sound.
- Exactly one `repro` route remains the correct scope.
- One final authorization call, spend-before-execute, fsync, and at-most-once semantics
  remain correct.
- Ledger deletion remains an explicitly excluded same-user custody bypass.
- Evidence stages remain maker fixture -> breaker fixture -> operator provisioning ->
  live P1; none may borrow the next stage's strength.
- The live worker remains untouched and execution authority remains zero.

## Gate state

**Contract v2 is BLOCKED. No implementation, trust-root provisioning, signature request,
or live executor call is authorized from this candidate.**

The repair is one bounded v2.1 addendum: route byte/commit binding, actual timeout
binding, split nonce ablations plus ledger format, ordered health states, and strict
field/signature types. Body `7cc5d17d…e97f5` remains unchanged. After the maker freezes
that addendum, the independently assigned breaker re-checks only B1-B5 plus retained
v2 invariants. No article, unrelated outreach, API experiment, or other research lane
opens while this gate is unresolved.
