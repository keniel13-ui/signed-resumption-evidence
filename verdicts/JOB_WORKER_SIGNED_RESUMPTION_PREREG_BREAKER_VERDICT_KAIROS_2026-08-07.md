# Independent Breaker Verdict — Signed Resumption Preregistration

**Date:** 2026-08-07 EDT  
**Breaker:** Kairos/Codex, separately live seat  
**Maker:** Ka'el  
**Candidate:** `JOB_WORKER_SIGNED_RESUMPTION_PREREG_2026-08-07.md`  
**Candidate SHA-256:** `69f1c6cd64fb0b0b5b8ad82dbe4971bbb74bd97f4e98c6c424c0ffdfaba8685b`  
**Candidate edited by breaker:** no  
**Code written:** no

## Verdict: **BLOCK**

The direction is correct: asymmetric authorization, a trust root outside the
worker's write reach, a mandatory legitimate ALLOW, and protection-by-protection
ablations. The frozen contract is not yet implementation-ready, however. Four
load-bearing seams would let an implementation choose the answer after the
freeze or make the mandatory P1 row unreachable.

Known-before-new classification: signed resumption itself is
`CONFIRMS_KNOWN`; it was already the named next authority step. The four seams
below are `CHANGES_KNOWN`: they change the claim that this exact contract is
ready for code.

## Checks performed before adjudication

- Candidate hash recomputed exactly.
- Frozen base `km_agent/job_worker.py` remains SHA-256
  `63d4e84413037114abf7df5f0709bf5f2d6b0e9d717f40afa64fd77c5d4e315f`.
- `/usr/bin/ssh-keygen` is root-owned and supports `-Y sign` / `-Y verify`.
- The local OpenSSH manual confirms verification requires an allowed-signers
  file, signer identity (`-I`), namespace (`-n`), signature file (`-s`), and
  message bytes on standard input.
- `/private/etc` is `root:wheel`, mode `755`; `/etc` is a root-owned symlink to
  `/private/etc`.
- The existing worker and executor routes were read line-by-line.
- A no-write dynamic probe of the current headless path produced:
  `decision_calls=2`, `executor_calls=0` when the first decision allowed and the
  second represented an already-spent nonce.
- `/Users/kenielmaldonado` and `km_agent/` are not Git repositories. Running
  `git status` in the candidate directory returns "not a git repository."

## K1 — The freeze/candidate custody claim is false as written

Section 9 says a repository pre-commit hook enforces separate freeze and
implementation commits. No repository or hook contains this preregistration and
`km_agent/job_worker.py`. The contract is a hashed local file, but its stated
commit-order enforcement does not exist.

This matters because the result is supposed to be externally replayable and
because the live worker must not become the development candidate.

### Required repair

Before code:

1. Name an actual versioned candidate workspace containing the preregistration,
   implementation, tests, and result artifacts.
2. Commit the repaired preregistration alone and record its commit plus SHA-256.
3. Put implementation in a later commit.
4. Keep the live `km_agent/job_worker.py` unchanged until the isolated candidate
   has contract PASS, implementation, and an independent code verdict.
5. Either install and verify the claimed commit-order hook in that repository or
   remove the hook claim and state the actual enforcement mechanism.

## K2 — The signature protocol is not frozen tightly enough for an off-device signer

The contract says "canonical serialization" but does not freeze the canonical
bytes. It also does not freeze the required OpenSSH signer identity, namespace,
signature representation, or safe signature-file handling. `ssh-keygen -Y
verify` cannot be implemented without choosing those values after the freeze.

The root path is named, but A11 requires more than path existence. The verifier
must be told how to reject a symlink, non-regular file, non-root owner, or a file
or parent directory writable by the worker's group/user. `/etc` itself is a
symlink on this Mac, so an imprecise "reject every symlink in the path" rule
would also reject the legitimate production path.

### Required repair

Freeze all of the following before code:

- the complete signed field set;
- exact UTF-8 canonical JSON rules, including types and trailing-newline rule;
- an exact signer principal;
- a custom fixed namespace;
- the fixed `/usr/bin/ssh-keygen` argument vector;
- an internally generated, non-receipt-controlled temporary signature path,
  mode, cleanup, timeout, and no-shell rule;
- exact custody checks on the canonical `/private/etc/keniel-agent` directory
  and allowed-signers file;
- maximum receipt and signature sizes;
- the non-secret operator handoff: canonical payload, payload digest, public-key
  fingerprint, and returned ASCII-armored SSH signature.

The worker may construct an unsigned canonical request for Keniel to inspect and
sign. Constructing bytes is not authority; producing the signature is. Section
6 should not accidentally invalidate this necessary request-generation path.

## K3 — `tool` and `allowed_cwd` do not yet bind the executor that actually runs

The contract does not define the `tool` vocabulary or how it is independently
derived. The live code makes this load-bearing:

- `process_one()` authorizes `CLAIM30` before it derives the executor route.
- The `eye` allowlist entry subsequently runs in `km_agent`, not `CLAIM30`.
- Allowlisted Python commands use relative `python3` and inherited `PATH`, so a
  receipt naming a logical key does not identify the executable actually run.
- The headless route prefers Grok but silently falls back to Claude after an
  exception. A receipt for one can therefore launch the other unless fallback
  behavior is bound or removed.

A6 can currently be satisfied by comparing a receipt's `tool` literal to a
second literal while the real executor changes underneath it. That would repeat
Mandate V4's asserted-mode failure.

### Required repair

Signed-resumption v1 should open **one narrow route only**:

- one named existing allowlist action (recommended: `repro`);
- one frozen real working directory;
- one frozen absolute executable/argument vector or a digest-bound command
  manifest;
- no Grok, Claude, `AUTO:` freeform, fallback, or any other signed tool class.

The worker must derive this route from the queued job before authorization and
compare the derived route, real cwd, and real command manifest to the signed
values. Add negative rows for extra prompt arguments, another allowlist key,
headless-route substitution, cwd substitution through `RUN_CWD`, executable
substitution through `PATH`, and post-verification route change.

## K4 — The nonce state machine contradicts the result bar and is mechanically incomplete

P2 requires a one-shot replay block and §3 says a nonce is recorded as spent.
Section 6 then says the design is invalid if the worker can delete that record,
while §7 correctly admits that the user-space record can be deleted and the
strong claim does not include determined replay resistance. Those three
statements do not currently produce one scoreable result class.

There are also two executable gaps:

1. `process_one()` calls `execution_decision()` and the headless route calls it
   again. If the first call spends the nonce, the second call rejects P1. This
   was reproduced without touching disk: two decisions, zero executor calls.
2. "Check then append" is not enough. Two concurrent attempts can both observe
   an unspent nonce unless check-and-spend is atomic.

The spend timing also needs a declared safety choice. Spending after execution
permits a crash replay. Spending before execution gives at-most-once behavior,
but a crash after spending can permanently consume a job that never ran.

### Required repair

- Authorize exactly once at the final executor boundary.
- Atomically check-and-spend under a lock before the executor call, with flush
  and `fsync` before execution.
- Freeze at-most-once semantics: a crash after spend does not automatically
  retry the job.
- Add a concurrent same-nonce row: two attempts, exactly one executor call.
- Split the claims honestly:
  - `REPLAY_BLOCKED_WHILE_SPEND_LEDGER_INTACT` may be earned;
  - deleting/truncating/rolling back the user-writable spend ledger is the
    expected custody-boundary bypass and cannot be advertised as solved.
- Make the nonce ablation flip only the first bounded claim, never the stronger
  hostile-same-user replay claim.

## K5 — The positive evidence and tamper states are not operationally defined

Section 8 forbids every agent from holding a private key or signing a receipt,
which is correct. But the contract does not distinguish fixture testing from the
real P1 evidence. A locally generated test key can prove parser and verifier
mechanics; it cannot prove independent authority.

The usefulness checker also currently maps every authorization+trust-root state
to `UNKNOWN` because it does not verify signatures. The contract says the forged
row becomes a tamper signal but names neither the exact state nor the legitimate
signed state, and the row is absent from the result matrix.

### Required repair

Freeze the evidence sequence:

1. Maker tests use an explicitly labeled temporary fixture key and earn no
   independence claim.
2. Independent code breaker uses its own fixture and attacks the exact code
   hash; this proves mechanics, not operator custody.
3. Only after code PASS does Keniel provision the root-owned public trust file
   and return one off-device signature over the frozen payload.
4. The live harmless P1 run and its receipt establish the bounded independent
   ALLOW.

Also freeze exact health states. At minimum, a forged/unverifiable receipt beside
a present trust root must be `TAMPERED` or `FAILED`, never generic `UNKNOWN` or
`PARKED`; a valid unspent receipt must have a distinct non-green armed state; a
spent/absent receipt returns to default-deny `PARKED`. The checker should consume
the same pure verification routine as the worker rather than implement a second
signature policy.

## What survives unchanged

- Asymmetric signatures are the correct primitive; HMAC would collapse signer
  and verifier custody.
- The root-owned allowed-signers direction is sound.
- P1 must ALLOW exactly once or there is no positive result.
- Pause dominance, expiry, job binding, cwd binding, tool binding, and ablations
  remain mandatory.
- The hostile same-user code-rewrite boundary remains out of scope and must stay
  visible in any article.
- Zero outside reproductions remains the honest evidence level.

## Gate state

**Contract v1 is BLOCKED. No implementation or live trust-root provisioning is
authorized from this candidate.**

The repair is bounded: custody, exact signature bytes, one executable route, one
atomic nonce state machine, and one evidence/health sequence. It does not reopen
Run N, Mandate, Employee Stage 2, money, outreach, or general headless authority.

