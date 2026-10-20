# Signed resumption — evidence bundle

Receipts for the article **"I Gave My Agent One Signed Permission It Couldn't Mint Itself."**

An agent worker that had been repaired into total default-deny — no reachable `True` branch, no
route that could execute anything — was given exactly one position it could open, and only with a
receipt signed by a key it does not hold and cannot reach.

**Start with [VERIFY.md](VERIFY.md).** You can check the operator signature yourself with stock
OpenSSH before reading anything else here.

## The result

| | |
|---|---|
| First execution | 2026-08-09 19:43:41 EDT, `EXECUTION_COMPLETED` |
| Replay of the same still-valid receipt | 19:47:22, refused `NONCE_ALREADY_SPENT` |
| Nonce ledger after both | one entry, unchanged |
| Regression floor | 19/19 prior attacks still refused, zero executor calls |
| External reproduction | **zero** |

## Shipped bytes

| Artifact | SHA-256 |
|---|---|
| `job_worker.INTEGRATED.py` | `e99f2cf5ecbd50fa7963a9e0b1955cf0fc0e01207aa2c00050540f856d60a298` |
| `signed_resumption.py` | `41164d8e33aee83d5d166fb6468e1b30da397b01fec31686c7d059a324183a76` |
| `agent_usefulness_check.INTEGRATED.py` | `7f162a2466ce848c962dd77bc6f6fd0f4d52a5af9f128417c64d3720f4186363` |

Recompute with `shasum -a 256 <file>`. The first is committed here under an `.INTEGRATED` name;
it is the live worker file byte-for-byte.

## Layout

- `VERIFY.md` — verify the signature yourself
- `owner_execution_allowed_signers` — the **public** key half, as installed root-owned at
  `/etc/keniel-agent/`
- `p1_receipts/` — the live run: receipt, worker log, nonce ledger, refusal record, and the
  trust-root custody readback
- `verdicts/` — 12 independent breaker verdicts, four of which returned BLOCK
- `JOB_WORKER_SIGNED_RESUMPTION_*.md` — the frozen contracts, written before the code
- `ABLATION_*.py`, `I3_REGRESSION_FLOOR_HARNESS_*.py` — rerunnable harnesses
- `job_worker.PRE_INTEGRATION_63d4e844.py` — the pre-integration snapshot, so rollback is a byte
  comparison rather than a reconstruction
- `docs/ARCHITECTURE.md`: how the pieces fit together, with diagrams
- `CLAUDE.md`, `CONTRIBUTING.md`: what may and may not change in this repository

The harnesses read their inputs from absolute paths on the author's machine
(`/Users/kenielmaldonado/...`), so they need those paths replaced before they run anywhere else.
`I3_REGRESSION_FLOOR_HARNESS_KAEL_2026-08-09.py` asserts worker digest `df506897…`, an
intermediate build that is not in this bundle. The 19 cases on the shipped worker `e99f2cf5…`
are reported in the final pre-P1 verdict, which used its own harness (also not in this bundle).

## How to read the verdicts

Contracts were frozen and hashed before implementation, then handed to a review seat that did not
author them. "Independent breaker" throughout means **a separate review seat that did not write
the candidate under test.** It does not mean an outside organisation. No outside party has
reproduced any of this.

Four verdicts returned BLOCK before their stage was allowed to proceed: three at the contract
stage and one on the code. Those BLOCKs are in
`verdicts/` on purpose. A bundle that only contains passes is not evidence.

## Limits

The article states these at length; the short version:

- A cryptographic authorization boundary is not a host integrity boundary. Every agent here runs
  as the same user and can overwrite the worker.
- The spend ledger is user-writable. Replay resistance holds only while it is intact.
- Binding covers the resolved interpreter and entry-script bytes, not the full transitive
  execution closure, and a small hash-to-exec interval remains.
- Key custody is operational, not attested by the receipt.

## Redactions

Four verdict files contained internal scope-boundary footers naming third parties unrelated to
this work. Those names were replaced with neutral wording. **No technical finding, result, count,
verdict, or hash was altered.** Everything else is as written at the time.
