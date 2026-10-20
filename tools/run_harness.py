#!/usr/bin/env python3
"""Re-run a bundled harness against the bundled bytes, in a throwaway sandbox.

The harnesses in this repository were written for the author's machine. They
read the module and the worker from absolute paths under
/Users/kenielmaldonado/ and the worker writes logs under ~/km_agent/. As
committed, they cannot run anywhere else.

This runner does NOT edit the committed harness files. For each run it:

1. checks that the bundled inputs still have the SHA-256 digests the README
   publishes (it refuses to run against anything else),
2. builds a sandbox directory with a private HOME, copies the bundled module
   and worker into it, and writes a stand-in ``god_jobs`` module (the real one
   is not part of this bundle),
3. makes a temporary copy of the harness in which only the two literal input
   paths are replaced by the sandbox copies, and prints every replacement,
4. runs that copy with a wall-clock timeout, with HOME pointed at the sandbox
   so nothing is written to the real home directory.

A run produced this way is a re-run on the FINAL shipped bytes. Some recorded
verdicts were produced against earlier bytes (see docs/REPRODUCE.md). The
output of this runner is not a recorded verdict and must not be presented as
one.

Stdlib only.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Bundled inputs and the digests published in README.md ("Shipped bytes").
MODULE_FILE = "signed_resumption.py"
WORKER_FILE = "job_worker.INTEGRATED.py"
EXPECTED = {
    MODULE_FILE: "41164d8e33aee83d5d166fb6468e1b30da397b01fec31686c7d059a324183a76",
    WORKER_FILE: "e99f2cf5ecbd50fa7963a9e0b1955cf0fc0e01207aa2c00050540f856d60a298",
}

# The only literals the runner rewrites. Anything else that mentions the
# author's paths (for example the Config defaults that ABLATION_I4A_I7 uses as
# a search pattern against the module source) must stay byte-identical, or the
# harness would stop matching the module it edits.
AUTHOR_MODULE_PATH = "/Users/kenielmaldonado/signed-resumption-candidate/signed_resumption.py"
AUTHOR_WORKER_PATH = "/Users/kenielmaldonado/km_agent/job_worker.py"

# Harnesses that pin a worker digest which is not in this bundle.
_PINNED_TARGET = re.compile(r'^EXPECT = "([0-9a-f]{64})"$', re.MULTILINE)

GOD_JOBS_STUB = '''"""Stand-in for the author's god_jobs module, which is not in this bundle.

job_worker imports it at load time. Every harness that reaches these functions
patches them with counting stubs, so this module only has to exist. Any call
that is not patched raises, so a harness can never silently "execute" through
this stand-in.
"""
ALLOWLIST = {"adapter": "stand-in", "eye": "stand-in", "repro": "stand-in"}


def _refuse(*_a, **_k):
    raise RuntimeError("god_jobs stand-in reached without a harness patch")


run_allowlisted = _refuse
close_job = _refuse
rewrite_markdown = _refuse
'''

DEFAULT_TIMEOUT = 600


class RunnerError(Exception):
    """A precondition failed. The message says which one."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def check_inputs(repo: Path = REPO) -> dict:
    """Refuse to run against bytes that are not the published ones."""
    seen = {}
    for name, want in EXPECTED.items():
        path = repo / name
        if not path.is_file():
            raise RunnerError(f"bundled input missing: {name}")
        got = sha256_file(path)
        if got != want:
            raise RunnerError(f"bundled input {name} has sha256 {got}, README publishes {want}")
        seen[name] = got
    return seen


def pinned_target(source: str) -> str | None:
    m = _PINNED_TARGET.search(source)
    return m.group(1) if m else None


def rewrite(source: str, module_path: str, worker_path: str, retarget_to: str | None = None) -> tuple[str, list]:
    """Return (new_source, replacements). Only exact literal paths are touched."""
    replacements = []
    for old, new in ((AUTHOR_MODULE_PATH, module_path), (AUTHOR_WORKER_PATH, worker_path)):
        quoted_old = f'"{old}"'
        n = source.count(quoted_old)
        if n:
            source = source.replace(quoted_old, f'"{new}"')
            replacements.append((old, new, n))
    pin = pinned_target(source)
    if pin is not None and retarget_to is not None:
        source = source.replace(f'EXPECT = "{pin}"', f'EXPECT = "{retarget_to}"', 1)
        replacements.append((pin, retarget_to, 1))
    return source, replacements


def build_sandbox(root: Path, repo: Path = REPO) -> dict:
    home = root / "home"
    agent_dir = home / "km_agent"
    candidate = root / "signed-resumption-candidate"
    agent_dir.mkdir(parents=True)
    candidate.mkdir()
    module = candidate / "signed_resumption.py"
    worker = agent_dir / "job_worker.py"
    shutil.copyfile(repo / MODULE_FILE, module)
    shutil.copyfile(repo / WORKER_FILE, worker)
    (agent_dir / "god_jobs.py").write_text(GOD_JOBS_STUB, encoding="utf-8")
    return {"home": home, "module": module, "worker": worker}


def run(
    harness: Path,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    keep: bool = False,
    retarget: bool = False,
    repo: Path = REPO,
    out=sys.stdout,
) -> int:
    harness = harness.resolve()
    if not harness.is_file():
        raise RunnerError(f"harness not found: {harness}")
    inputs = check_inputs(repo)
    source = harness.read_text(encoding="utf-8")

    pin = pinned_target(source)
    if pin is not None and pin not in inputs.values() and not retarget:
        raise RunnerError(
            f"{harness.name} asserts its target worker has sha256 {pin}. "
            "Those bytes are not in this bundle, so the recorded run cannot be "
            "reproduced from it. Pass --retarget to run the same cases against "
            f"the shipped worker ({EXPECTED[WORKER_FILE][:12]}...) instead; "
            "that is a different experiment and is labelled as one."
        )

    root = Path(tempfile.mkdtemp(prefix="sr-harness-"))
    try:
        box = build_sandbox(root, repo)
        new_source, replacements = rewrite(
            source, str(box["module"]), str(box["worker"]), retarget_to=EXPECTED[WORKER_FILE] if retarget else None
        )
        copy = root / harness.name
        copy.write_text(new_source, encoding="utf-8")

        print(f"harness        {harness.name}", file=out)
        print(f"harness sha256 {sha256_file(harness)}", file=out)
        for name, digest in inputs.items():
            print(f"input          {name} {digest}", file=out)
        print("god_jobs       stand-in (real module not in bundle)", file=out)
        for old, new, n in replacements:
            print(f"rewrite        {old} -> {new} ({n}x)", file=out)
        if retarget and pin is not None:
            print("NOTE           RETARGETED RUN. Not the recorded experiment.", file=out)
        print(f"sandbox        {root}", file=out)
        print("-" * 72, file=out, flush=True)

        env = dict(os.environ, HOME=str(box["home"]), PYTHONDONTWRITEBYTECODE="1")
        try:
            proc = subprocess.run(
                [sys.executable, str(copy)],
                cwd=str(root),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            partial = exc.output or ""
            if isinstance(partial, bytes):
                partial = partial.decode("utf-8", "replace")
            print(partial, end="", file=out)
            print(f"TIMEOUT after {timeout}s", file=out)
            return 124
        print(proc.stdout, end="", file=out)
        print("-" * 72, file=out)
        print(f"exit {proc.returncode}", file=out, flush=True)
        return proc.returncode
    finally:
        if keep:
            print(f"sandbox kept at {root}", file=out)
        else:
            shutil.rmtree(root, ignore_errors=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("harness", type=Path, help="path to a bundled *_HARNESS*.py / ABLATION_*.py file")
    ap.add_argument(
        "--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"wall-clock limit in seconds (default {DEFAULT_TIMEOUT})"
    )
    ap.add_argument("--keep", action="store_true", help="keep the sandbox directory")
    ap.add_argument(
        "--retarget",
        action="store_true",
        help="for a harness that pins a worker digest absent from the bundle, "
        "run it against the shipped worker instead (labelled as such)",
    )
    args = ap.parse_args(argv)
    try:
        return run(args.harness, timeout=args.timeout, keep=args.keep, retarget=args.retarget)
    except RunnerError as exc:
        print(f"run_harness: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
