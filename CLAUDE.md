# CLAUDE.md

Guidance for Claude Code (and any other agent) working in this repository.

## What this repository is

A published **evidence bundle** for the article "I Gave My Agent One Signed Permission It
Couldn't Mint Itself." It holds the exact code that ran, the frozen contracts, 12 breaker
verdicts (four BLOCK), the maker's ablation harnesses, and the receipts from one supervised live
run (P1, 2026-08-09). It is not an application and has no build. See `README.md`, `VERIFY.md`
and `docs/ARCHITECTURE.md`.

## Hard rules

These files are recorded evidence. **Never edit, reformat, re-encode, rename, or "fix" them**,
even for typos, lint, line endings, or trailing whitespace:

- `p1_receipts/**` (receipt, signature, nonce ledger, refusal record, worker log, custody readback)
- `verdicts/**`
- `JOB_WORKER_SIGNED_RESUMPTION_*.md` (frozen contracts; their SHA-256 digests are cited by code
  and verdicts)
- `signed_resumption.py`, `job_worker.INTEGRATED.py`, `agent_usefulness_check.INTEGRATED.py`,
  `job_worker.PRE_INTEGRATION_63d4e844.py` (digests published in README and P1_RESULT)
- `ABLATION_*.py`, `I3_REGRESSION_FLOOR_HARNESS_*.py` (harnesses as run)
- `owner_execution_allowed_signers` (the public trust root)
- `VERIFY.md`

A single changed byte in any of these breaks a published digest or the operator signature. If
you believe one of them is wrong, say so in a PR description or issue. Do not change it.

Also:

- Do not change the claims, counts, verdicts or results stated in `README.md`. Corrections to
  README prose are fine; the "Shipped bytes" table and result table are not.
- There is no private key here and there must never be one. `.gitignore` excludes `secrets/` and
  `state/`. Do not generate keys inside the repository tree.
- Do not describe a re-run you performed as an "external reproduction" or a verdict. The README
  states external reproductions as zero; that is the author's count to change.

## Verifying (read-only)

The signature check in `VERIFY.md` runs with stock tools and writes `payload.json`,
`payload.sig` and `bad.json` into the current directory. Run it from a scratch copy or delete
those files afterwards:

```bash
cp -R . /tmp/sre && cd /tmp/sre   # then follow VERIFY.md steps 1 to 3
```

Expected: `Good "km-agent-execution-authorization" signature for keniel-owner with ED25519 key
SHA256:EsftjEQJF0z4+fBDDZNEXmIUUK0ydtyijHqfsmRyfpA`, and the one-byte tamper must fail.

Recompute the shipped digests with `shasum -a 256 <file>` and compare with the README table.

## Code facts worth knowing before reading the Python

- Stdlib only. POSIX only (`fcntl`). Signature verification shells out to
  `/usr/bin/ssh-keygen -Y verify` with a fixed argv and `shell=False`.
- `signed_resumption.authorize()` is the single decision; its check order is contractual (see
  `docs/ARCHITECTURE.md`). `execute_authorized_job()` re-hashes the route right before
  `subprocess.run`.
- `signed_resumption.Config` defaults are production paths on the author's Mac. Tests and
  harnesses pass a fixture `Config(...)`; production code paths take no `cfg` argument on purpose.
- The worker imports `god_jobs`, which is not in this bundle, and uses paths under
  `~/km_agent`. Never run the worker's `main()`; it polls a queue and can launch agents.
- The harnesses hardcode `/Users/kenielmaldonado/...` input paths. To experiment with them, copy
  them somewhere else and point a fixture at copies of the bundled files. Never point them at
  real paths under your home directory.

## Contributing

See `CONTRIBUTING.md`. Additions (tooling, tests, docs) go next to the evidence, never into it.
