# Contributing

This repository is an evidence bundle. Contributions are welcome when they make the evidence
easier to check, never when they change it.

## What can change

- Tooling and tests that read the evidence (verification scripts, CI).
- Documentation that explains the evidence (`docs/`, `CLAUDE.md`, this file).
- README prose, as long as no claim, count, digest, verdict or result changes.

## What cannot change

Receipts, verdicts, frozen contracts, shipped code, harnesses, the public key, and `VERIFY.md`.
The full list is in [CLAUDE.md](CLAUDE.md#hard-rules). If you think one of them is wrong, open an
issue or explain it in a PR description. A reviewer who sees a diff touching those paths should
reject it.

A reproduction you ran yourself is useful. Report it in an issue with the exact command, your OS,
Python and OpenSSH versions, and the full output. Do not add it to `verdicts/`.

## Branch workflow

`main` is the published bundle. Work goes through a `dev` integration branch when one exists:

1. Branch from `dev` (or from `main` if `dev` does not exist yet):
   `git switch -c <type>/<short-topic> origin/dev`
2. Keep each branch to one purpose (docs, tooling, tests).
3. Open the pull request against `dev`. The maintainer promotes `dev` to `main` when a set of
   changes is ready to publish.
4. Never force-push a shared branch, and never rewrite `main` history: the commit that published
   the bundle is part of its provenance.

To create `dev` from the current `main` (maintainer, one time):

```bash
gh api repos/keniel13-ui/signed-resumption-evidence/git/refs \
  -f ref=refs/heads/dev \
  -f sha=$(gh api repos/keniel13-ui/signed-resumption-evidence/commits/main -q .sha)
```

## Before opening a pull request

```bash
git diff --stat origin/main -- p1_receipts verdicts 'JOB_WORKER_SIGNED_RESUMPTION_*.md' \
  ':(glob)*.py' owner_execution_allowed_signers VERIFY.md
```

The command above must print nothing. Then run the signature check from [VERIFY.md](VERIFY.md)
in a scratch copy and confirm the expected output.

## Style

- Python: stdlib only, matching the bundle. No new runtime dependencies.
- Keep commit messages specific about what was checked and what was not.
