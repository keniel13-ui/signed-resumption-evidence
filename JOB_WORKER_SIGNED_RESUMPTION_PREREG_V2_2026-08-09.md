# Preregistration v2 — Signed Resumption for `job_worker.py`

**Frozen:** 2026-08-09. **Maker:** Ka'el. **Status: CONTRACT ONLY. NO CODE EXISTS.**
**Breaker: assigned by Keniel. Not Ka'el, and no seat may appoint itself.**

Authorization: Keniel, PHASE 500 — *"build the signed resumption... this has to be done right."*
Supersedes v1 (`69f1c6cd…8685b`), which was independently **BLOCKED** by Kairos
(`7d8812d0…69212`) on five seams. This file closes those five and changes nothing else.

Frozen base: `km_agent/job_worker.py` sha256
`63d4e84413037114abf7df5f0709bf5f2d6b0e9d717f40afa64fd77c5d4e315f` (unchanged since 07-31).
The live worker is **not** the development candidate and is not edited until this contract PASSes
and an implementation clears an independent code breaker.

---

## The question

> Can the worker execute one human-approved job **without being able to mint, broaden, alter, or
> replay that approval itself**?

The July 31 gate has no reachable `True`. This opens exactly one position.

---

## K1 — Custody (v1 claimed a hook that does not exist)

v1 §9 claimed a pre-commit hook enforced freeze-before-code. **False:** neither `~` nor
`km_agent` is a git repository, so no hook governed either file.

**Closed here by construction.** This contract lives in
`~/signed-resumption-candidate/`, a real git repository. This preregistration is committed
**alone**. Implementation lands in a **later** commit. Commit order is the receipt; no hook is
claimed. `km_agent/job_worker.py` stays untouched at `63d4e844…e315f` for the whole cycle.

---

## K2 — The signature protocol, frozen to the byte

**Canonical payload.** UTF-8 JSON, `sort_keys=True`, `separators=(",",":")`, **no trailing
newline**, containing exactly these keys and no others:

```
schema_version, state, job_id, job_digest, tool, allowed_cwd,
argv_sha256, max_wall_seconds, expires_at, nonce
```

`signature` is carried beside the payload and is **never** part of the signed bytes.
`schema_version` = `2`. `state` = `EXECUTION_AUTHORIZED`.

**Verification command — fixed argv, no shell, nothing receipt-controlled:**

```
/usr/bin/ssh-keygen -Y verify
  -f /etc/keniel-agent/owner_execution_allowed_signers
  -I keniel-owner
  -n km-agent-execution-authorization
  -s <internally generated temp path>
```

Canonical payload on **stdin**. Timeout 10s. `shell=False`. The binary path, `-I`, `-n`, and
`-f` are literals in the worker; **no receipt field may influence any of them.**

**Signature file.** Written by the worker to a path it generates itself under a private temp
dir, mode `0600`, removed in a `finally`. A path supplied in the receipt is a hard refusal.

**Trust-root custody checks, all required before verification:**

1. `os.path.realpath` of the trust root **equals** `/private/etc/keniel-agent/owner_execution_allowed_signers`.
   (`/etc` is itself a root-owned symlink on this Mac, so blanket symlink rejection would break
   the legitimate path. Resolve, then compare.)
2. The resolved path is a **regular file** (`stat.S_ISREG`), not a symlink, directory, or FIFO.
3. Owner **uid 0**, and not group- or world-writable (`mode & 0o022 == 0`).
4. Its parent directory: owner uid 0, and `mode & 0o022 == 0`.
5. Any check failing = refuse. Do not fall through to verification.

**Size bounds.** Receipt ≤ 8192 bytes, signature ≤ 4096 bytes. Over = refuse before parsing.

**Operator handoff (non-secret).** The worker may build and display an *unsigned* canonical
request: the payload, its sha256, and the expected public-key fingerprint. **Constructing bytes
is not authority; producing the signature is.** §6 does not forbid this path.

---

## K3 — One route, bound to what actually executes

v1's `tool` was a literal compared to a literal. The live code makes that fatal: `process_one()`
authorizes before deriving the route, `eye` runs in `km_agent` rather than `CLAIM30`, `python3`
is PATH-selected, and the headless path silently falls back from Grok to Claude.

**v2 opens exactly one route.** Frozen values, read from the live allowlist on 2026-08-09:

| Field | Frozen value |
|---|---|
| `tool` | `repro` |
| `allowed_cwd` | realpath `/Users/kenielmaldonado/claim30_repro` |
| argv | `["/usr/local/bin/python3", "repro.py"]` — **absolute interpreter, PATH not consulted** |
| `argv_sha256` | sha256 of the canonical JSON of that exact argv list |

**The worker must derive the route from the queued job BEFORE authorization**, then compare the
derived tool, the realpath of the derived cwd, and the sha256 of the derived argv against the
signed values. Any mismatch refuses.

**Closed and unsignable:** `adapter`, `loose`, `suite-status`, `suite-log`, `eye`, freeform
`AUTO:`/`EXEC:`, Grok, Claude, and every fallback path. A receipt naming any of them is invalid
regardless of signature validity.

---

## K4 — One authorization, atomic spend, at-most-once

Two problems in v1: the headless path calls `execution_decision()` twice (measured: two
decisions, zero executor calls), so a first-call spend would block the legitimate P1; and
check-then-append is not atomic.

1. **Authorize exactly once**, at the final executor boundary. The earlier call is removed for
   this route.
2. **Check-and-spend atomically before the executor runs:** acquire an exclusive lock
   (`fcntl.flock`) on the spend ledger, re-read it under the lock, refuse if the nonce is
   present, otherwise append, `flush()`, `os.fsync()`, release — *then* call the executor.
3. **At-most-once is the frozen semantic.** A crash after spend and before completion does
   **not** auto-retry. Losing a job is preferred to running it twice.
4. **Concurrency row required:** two simultaneous attempts with the same nonce → exactly **one**
   executor call.

**Claim split, and this is binding:**
- `REPLAY_BLOCKED_WHILE_SPEND_LEDGER_INTACT` **may** be earned.
- Deleting, truncating, or rolling back the user-writable ledger is the **expected custody
  bypass** and is **not** claimed as solved. The worker cannot write the root-owned directory, so
  it cannot record a spend there. The nonce ablation flips only the first claim, never a
  hostile-same-user replay claim.

---

## K5 — Evidence tiers and health states

**Evidence sequence, in order. No stage may borrow a later stage's strength.**

1. **Maker fixture.** Ka'el generates a clearly labelled throwaway key. Proves parser and
   verifier mechanics. Earns **no** independence claim.
2. **Breaker fixture.** The assigned breaker uses its **own** key against the exact
   implementation hash, with its own harness. Proves mechanics, not operator custody.
3. **Operator provisioning.** Only after code PASS: Keniel creates the root-owned trust file and
   returns **one** off-device signature over the frozen payload. No agent holds the private key.
4. **Live P1.** One harmless `repro` run. This, and only this, is the bounded independent ALLOW.

**Health states — frozen, no generic `UNKNOWN`:**

| Condition | State |
|---|---|
| trust root present, receipt present but unverifiable/forged | **`TAMPERED`** |
| valid, unexpired, unspent receipt | **`ARMED`** |
| receipt spent, absent, or expired | **`PARKED`** (default-deny, green) |
| trust root absent | **`PARKED`** |

The usefulness checker **imports the same pure verification function the worker uses.** It must
not implement a second signature policy.

---

## Positive result bar — every row in one run

| # | Case | Expected | Executor calls |
|---|---|---|---|
| **P1** | valid signed receipt, correct job/cwd/tool/argv, unexpired, unspent | **ALLOW, runs once** | **1** |
| **P2** | same receipt replayed | BLOCK, nonce spent | 0 |
| **P3** | two simultaneous attempts, same nonce | one ALLOW, one BLOCK | **1** |
| A1 | no receipt | BLOCK | 0 |
| A2 | receipt, no signature | BLOCK | 0 |
| A3 | signed by a key not in allowed-signers | BLOCK | 0 |
| A4 | one byte of `text` changed after signing | BLOCK | 0 |
| A5 | `allowed_cwd` changed | BLOCK | 0 |
| A6 | `tool` changed to another allowlist key | BLOCK | 0 |
| A7 | `argv_sha256` mismatch (extra arg / different interpreter) | BLOCK | 0 |
| A8 | `max_wall_seconds` > `MAX_WALL` | BLOCK | 0 |
| A9 | expired / tz-naive `expires_at` | BLOCK | 0 |
| A10 | trust root absent | BLOCK | 0 |
| A11 | trust root user-writable, or a symlink to a user-writable copy | BLOCK | 0 |
| A12 | pause marker present with a valid receipt | BLOCK, pause dominates | 0 |
| A13 | receipt is array / empty / non-dict / oversize | BLOCK | 0 |
| A14 | `schema_version` ≠ 2 | BLOCK | 0 |
| A15 | valid signature from a **different** job's receipt | BLOCK | 0 |
| A16 | signature file path supplied in the receipt | BLOCK | 0 |
| A17 | route changed **after** verification, before exec | BLOCK | 0 |

## Ablations — each must flip

| Remove | Attack that must then succeed |
|---|---|
| signature verification | A3 |
| trust-root custody checks | A11 |
| job-digest binding | A4 |
| cwd binding | A5 |
| tool binding | A6 |
| argv_sha256 binding | A7 |
| atomic nonce spend | P2 and P3 |
| expiry check | A9 |
| pause dominance | A12 |

A protection whose removal changes nothing is decoration and is deleted from the claim.

---

## How this can come out wrong

Five designs died on `RESEARCH_SPINE.md` §3 because the result followed from a choice in the
room. Stated in advance, this is invalid if:

- the worker can construct bytes that verify (then P1 proves nothing);
- any receipt field reaches the `ssh-keygen` argv, `-I`, `-n`, `-f`, or the signature path;
- P1 is made to pass by weakening any attack row rather than by a real signature;
- the ablations do not flip;
- the nonce claim is stated as replay-proof rather than ledger-intact-scoped;
- the derived route is compared to itself rather than to the signed values.

---

## Scope limits — carried into any article

- **Not tamper-proof.** Every agent runs as the same user and can overwrite `job_worker.py` and
  restart the LaunchAgent. This defends against **accidental and naive** authority restoration.
  Verbatim from the 07-31 breaker verdict.
- **Mint, not replay.** The strong claim is that the agent cannot mint authorization. Replay
  resistance holds only while the spend ledger is intact.
- **Zero outside reproductions.** Everything here runs on Keniel's machine.

## Freeze rule

No row in the bar, the ablations, or the how-it-comes-out-wrong list moves after this hash is
recorded. If the implementation cannot satisfy a row, that is a **negative result** and publishes
as one. Breaker builds its own harness, does not reuse the maker's self-test, replaces every
executor with a counting stub, and a row passes only if the decision **and** the count match.
