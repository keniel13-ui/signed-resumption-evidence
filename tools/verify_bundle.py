#!/usr/bin/env python3
"""Check this evidence bundle end to end, read-only.

Automates VERIFY.md and adds the cross-checks a careful reader would do by
hand. Every check reads committed files only. Nothing in the bundle is written;
scratch files go to a temporary directory that is removed afterwards.

Checks:
  evidence-sums      every evidence file matches tools/evidence.sha256
  shipped-bytes      README "Shipped bytes" and P1_RESULT digests match the files
  frozen-contracts   contract files match the digests the code and verdicts cite
  pre-integration    job_worker.PRE_INTEGRATION_63d4e844.py is the cited 63d4e844... bytes
  payload            VERIFY.md step 1: 433 bytes, sha256 4ed5ecff...
  module-payload     the shipped module canonicalises the receipt to the same bytes
  signature          VERIFY.md step 2 with ssh-keygen: Good signature
  tamper             VERIFY.md step 3: a one-byte change fails verification
  key-fingerprint    published key is SHA256:EsftjEQ... (the value in VERIFY.md)
  module-accepts     shipped module's validate_schema + verify_signature accept the receipt
  p1-consistency     receipt, nonce ledger, refusal record and worker log agree
  verdict-inventory  12 verdict files, 4 BLOCK and 8 PASS, as README states

Exit status: 0 when every check passes, 1 otherwise. Stdlib only. Needs
OpenSSH's ssh-keygen (8.1 or newer, for -Y verify) on PATH.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

RECEIPT = "p1_receipts/JOB_WORKER_EXECUTION_AUTHORIZED.json"
LEDGER = "p1_receipts/execution_nonce_spent.jsonl"
REFUSAL = "p1_receipts/refusal_P1.jsonl"
WORKER_LOG = "p1_receipts/worker_log_P1.txt"
SIGNERS = "owner_execution_allowed_signers"
SUMS = "tools/evidence.sha256"

PRINCIPAL = "keniel-owner"
NAMESPACE = "km-agent-execution-authorization"

# Values stated in VERIFY.md.
PAYLOAD_BYTES = 433
PAYLOAD_SHA256 = "4ed5ecff82def7098f604c39d95a62ace61f4850f035ba8088b8c49637c6b64f"
KEY_FINGERPRINT = "SHA256:EsftjEQJF0z4+fBDDZNEXmIUUK0ydtyijHqfsmRyfpA"

# Digests cited for the three shipped files (README table and P1_RESULT table).
SHIPPED = {
    "job_worker.INTEGRATED.py": "e99f2cf5ecbd50fa7963a9e0b1955cf0fc0e01207aa2c00050540f856d60a298",
    "signed_resumption.py": "41164d8e33aee83d5d166fb6468e1b30da397b01fec31686c7d059a324183a76",
    "agent_usefulness_check.INTEGRATED.py": "7f162a2466ce848c962dd77bc6f6fd0f4d52a5af9f128417c64d3720f4186363",
}

# Frozen contract digests, with where each is cited.
CONTRACTS = {
    "JOB_WORKER_SIGNED_RESUMPTION_PREREG_V2_2026-08-09.md": (
        "7cc5d17dd49d8a05df4718106606d7cc848dac9f75988de575ccc33ce90e97f5",
        "signed_resumption.py docstring",
    ),
    "JOB_WORKER_SIGNED_RESUMPTION_ADDENDUM_V2_1_2026-08-09.md": (
        "ac3f5e9b8241e988c11287a00f0b9d2063aa8802dd28313e7178e8b1faa37ef5",
        "signed_resumption.py docstring",
    ),
    "JOB_WORKER_SIGNED_RESUMPTION_INTEGRATION_FREEZE_2026-08-09.md": (
        "74fcec1591c5dac30efd3b768583ff4808a391b40e01a08c95d23e95068fadf8",
        "integration addendum header",
    ),
    "JOB_WORKER_SIGNED_RESUMPTION_INTEGRATION_ADDENDUM_2026-08-09.md": (
        "b06c1781bc5fc8cd40fbc512ee30f8076cff2c0d4feeab8f3442514482e75829",
        "integration addendum breaker verdict",
    ),
}

PRE_INTEGRATION = (
    "job_worker.PRE_INTEGRATION_63d4e844.py",
    "63d4e84413037114abf7df5f0709bf5f2d6b0e9d717f40afa64fd77c5d4e315f",
)

VERDICT_COUNT = 12
VERDICT_BLOCKS = 4
_VERDICT_LINE = re.compile(r"^##\s+VERDICT:\s+\*\*(PASS|BLOCK)\b", re.IGNORECASE | re.MULTILINE)
_README_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*`([0-9a-f]{64})`\s*\|", re.MULTILINE)


class CheckFailed(Exception):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def find_ssh_keygen() -> str:
    exe = shutil.which("ssh-keygen")
    if not exe:
        raise CheckFailed("ssh-keygen not found on PATH (install OpenSSH 8.1+)")
    return exe


def ssh_verify(keygen: str, signers: Path, sig: Path, payload: bytes) -> subprocess.CompletedProcess:
    return subprocess.run(
        [keygen, "-Y", "verify", "-f", str(signers), "-I", PRINCIPAL, "-n", NAMESPACE, "-s", str(sig)],
        input=payload,
        capture_output=True,
        timeout=30,
        shell=False,
    )


def load_receipt(repo: Path) -> dict:
    data = json.loads((repo / RECEIPT).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "signature" not in data:
        raise CheckFailed("receipt is not an object with a signature field")
    return data


def verify_md_payload(receipt: dict) -> bytes:
    """VERIFY.md step 1, verbatim in effect."""
    p = {k: v for k, v in receipt.items() if k != "signature"}
    return json.dumps(p, sort_keys=True, separators=(",", ":")).encode()


def read_jsonl(path: Path) -> list:
    raw = path.read_text(encoding="utf-8")
    rows = []
    for n, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise CheckFailed(f"{path.name}:{n} is not JSON ({exc.msg})") from None
    return rows


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# ------------------------------------------------------------------ checks


def check_evidence_sums(repo: Path, _ctx: dict) -> str:
    sums = repo / SUMS
    if not sums.is_file():
        raise CheckFailed(f"{SUMS} missing")
    bad, listed = [], set()
    for line in sums.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, name = line.split(None, 1)
        name = name.lstrip("*")
        listed.add(name)
        path = repo / name
        if not path.is_file():
            bad.append(f"{name}: missing")
        elif sha256_file(path) != digest:
            bad.append(f"{name}: changed")
    tracked = {p.relative_to(repo).as_posix() for p in evidence_files(repo)}
    unlisted = sorted(tracked - listed)
    if unlisted:
        bad.append("not in manifest: " + ", ".join(unlisted))
    if bad:
        raise CheckFailed("; ".join(bad))
    return f"{len(listed)} files match"


def evidence_files(repo: Path) -> list:
    """Everything that is part of the published bundle, as opposed to tooling."""
    out = []
    for p in sorted(repo.iterdir()):
        if p.is_file() and (p.suffix in (".py", ".md") or p.name == SIGNERS):
            # README.md is prose that may be corrected; its digest table is
            # checked separately by shipped-bytes. The others are tooling docs.
            if p.name in ("README.md", "CLAUDE.md", "CONTRIBUTING.md"):
                continue
            out.append(p)
    for sub in ("verdicts", "p1_receipts"):
        out.extend(sorted(q for q in (repo / sub).iterdir() if q.is_file()))
    return out


def check_shipped_bytes(repo: Path, _ctx: dict) -> str:
    readme = dict(_README_ROW.findall((repo / "README.md").read_text(encoding="utf-8")))
    if readme != SHIPPED:
        raise CheckFailed(f"README table {readme} differs from expected {SHIPPED}")
    p1 = (repo / "p1_receipts/P1_RESULT_2026-08-09.md").read_text(encoding="utf-8")
    for name, digest in SHIPPED.items():
        got = sha256_file(repo / name)
        if got != digest:
            raise CheckFailed(f"{name} is {got}, published {digest}")
        if digest not in p1:
            raise CheckFailed(f"{digest[:12]}... for {name} not cited in P1_RESULT")
    return "3/3 match README and P1_RESULT"


def check_frozen_contracts(repo: Path, _ctx: dict) -> str:
    for name, (digest, cited) in CONTRACTS.items():
        got = sha256_file(repo / name)
        if got != digest:
            raise CheckFailed(f"{name} is {got}, {cited} cites {digest}")
    module_src = (repo / "signed_resumption.py").read_text(encoding="utf-8")
    for name in (
        "JOB_WORKER_SIGNED_RESUMPTION_PREREG_V2_2026-08-09.md",
        "JOB_WORKER_SIGNED_RESUMPTION_ADDENDUM_V2_1_2026-08-09.md",
    ):
        if CONTRACTS[name][0] not in module_src:
            raise CheckFailed(f"module docstring no longer cites {name}")
    return f"{len(CONTRACTS)}/{len(CONTRACTS)} contracts match their frozen digests"


def check_pre_integration(repo: Path, _ctx: dict) -> str:
    name, digest = PRE_INTEGRATION
    got = sha256_file(repo / name)
    if got != digest:
        raise CheckFailed(f"{name} is {got}, contracts cite {digest}")
    return "matches the frozen base cited by PREREG_V2"


def check_payload(repo: Path, ctx: dict) -> str:
    payload = verify_md_payload(ctx["receipt"])
    if len(payload) != PAYLOAD_BYTES or sha256_bytes(payload) != PAYLOAD_SHA256:
        raise CheckFailed(f"{len(payload)} bytes, sha256 {sha256_bytes(payload)}")
    ctx["payload"] = payload
    return f"{PAYLOAD_BYTES} bytes, sha256 {PAYLOAD_SHA256[:12]}..."


def load_module(repo: Path):
    spec = importlib.util.spec_from_file_location("_bundled_signed_resumption", repo / "signed_resumption.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclasses needs the registration
    spec.loader.exec_module(mod)
    return mod


def check_module_payload(repo: Path, ctx: dict) -> str:
    sr = ctx["module"]
    if sr.canonical_payload(ctx["receipt"]) != ctx["payload"]:
        raise CheckFailed("signed_resumption.canonical_payload differs from the VERIFY.md payload")
    return "signed_resumption.canonical_payload == VERIFY.md payload"


def check_signature(repo: Path, ctx: dict) -> str:
    keygen = find_ssh_keygen()
    sig = ctx["tmp"] / "payload.sig"
    sig.write_text(ctx["receipt"]["signature"], encoding="utf-8")
    proc = ssh_verify(keygen, repo / SIGNERS, sig, ctx["payload"])
    out = (proc.stdout + proc.stderr).decode("utf-8", "replace").strip()
    if proc.returncode != 0 or not out.startswith(f'Good "{NAMESPACE}" signature for {PRINCIPAL}'):
        raise CheckFailed(f"ssh-keygen exit {proc.returncode}: {out}")
    if KEY_FINGERPRINT not in out:
        raise CheckFailed(f"good signature but unexpected key: {out}")
    return out


def check_tamper(repo: Path, ctx: dict) -> str:
    keygen = find_ssh_keygen()
    bad = ctx["payload"].replace(b'"max_wall_seconds":600', b'"max_wall_seconds":601', 1)
    if bad == ctx["payload"]:
        raise CheckFailed("tamper pattern not found in payload")
    proc = ssh_verify(keygen, repo / SIGNERS, ctx["tmp"] / "payload.sig", bad)
    if proc.returncode == 0:
        raise CheckFailed("a modified payload verified; the signature check is vacuous")
    return f"modified payload refused (exit {proc.returncode})"


def check_key_fingerprint(repo: Path, _ctx: dict) -> str:
    keygen = find_ssh_keygen()
    proc = subprocess.run([keygen, "-lf", str(repo / SIGNERS)], capture_output=True, timeout=30, shell=False)
    out = proc.stdout.decode("utf-8", "replace").strip()
    if proc.returncode != 0 or KEY_FINGERPRINT not in out or "(ED25519)" not in out:
        raise CheckFailed(f"exit {proc.returncode}: {out or proc.stderr.decode('utf-8', 'replace')}")
    lines = [ln for ln in (repo / SIGNERS).read_text(encoding="utf-8").splitlines() if ln.strip()]
    if len(lines) != 1 or not lines[0].startswith(PRINCIPAL + " "):
        raise CheckFailed("allowed_signers must hold exactly one keniel-owner line")
    return out


def check_module_accepts(repo: Path, ctx: dict) -> str:
    """Run the shipped module's own schema and signature checks on the receipt.

    The trust-root custody checks need a root-owned file under /etc, which a
    reader does not have, so this uses a fixture Config pointing at a private
    copy of the published key (require_root_owned=False). Everything else is
    the module's production code path.
    """
    sr = ctx["module"]
    if not os.path.exists(sr.SSH_KEYGEN):
        raise CheckFailed(f"module hardcodes {sr.SSH_KEYGEN}, which does not exist here")
    root_dir = ctx["tmp"] / "trust"
    root_dir.mkdir(mode=0o755)
    # The module refuses a trust-root parent that is group/other WRITABLE; 0o755 is the
    # strictest mode that is still a normal readable directory.
    os.chmod(root_dir, 0o755)  # noqa: S103
    trust = root_dir / "allowed_signers"
    shutil.copyfile(repo / SIGNERS, trust)
    os.chmod(trust, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
    cfg = sr.Config(trust_root=str(trust), trust_root_realpath=os.path.realpath(trust), require_root_owned=False)
    receipt = ctx["receipt"]
    try:
        sr.validate_schema(receipt)
        sr.verify_signature(sr.canonical_payload(receipt), receipt["signature"], cfg)
    except sr.Refusal as exc:
        raise CheckFailed(f"module refused the receipt: {exc.code}") from None
    tampered = dict(receipt, max_wall_seconds=601)
    try:
        sr.verify_signature(sr.canonical_payload(tampered), receipt["signature"], cfg)
    except sr.Refusal as exc:
        if exc.code != "SIGNATURE_INVALID":
            raise CheckFailed(f"tampered receipt refused with unexpected code {exc.code}") from None
    else:
        raise CheckFailed("module accepted a tampered receipt")
    return "validate_schema + verify_signature accept; tampered copy -> SIGNATURE_INVALID"


def check_p1_consistency(repo: Path, ctx: dict) -> str:
    r = ctx["receipt"]
    ledger = read_jsonl(repo / LEDGER)
    if len(ledger) != 1:
        raise CheckFailed(f"nonce ledger has {len(ledger)} entries, README states one")
    spent = ledger[0]
    if spent.get("nonce") != r["nonce"] or spent.get("job_id") != r["job_id"]:
        raise CheckFailed("ledger entry does not match the receipt's nonce/job_id")
    refusals = read_jsonl(repo / REFUSAL)
    if len(refusals) != 1:
        raise CheckFailed(f"refusal record has {len(refusals)} entries, expected 1")
    ref = refusals[0]
    if ref.get("job_id") != r["job_id"] or ref.get("job_digest") != r["job_digest"]:
        raise CheckFailed("refusal record is not for the receipt's job")
    if not str(ref.get("reason", "")).endswith("NONCE_ALREADY_SPENT"):
        raise CheckFailed(f"refusal reason is {ref.get('reason')!r}")
    if ref.get("execution_authorized") is not False:
        raise CheckFailed("refusal record does not say execution_authorized=false")
    t_spent, t_replay, t_exp = parse_ts(spent["spent_at_utc"]), parse_ts(ref["ts"]), parse_ts(r["expires_at"])
    if not (t_spent < t_replay < t_exp):
        raise CheckFailed("timeline is not spent < replay < expiry")
    log = (repo / WORKER_LOG).read_text(encoding="utf-8")
    if f"job {r['job_id']} signed route EXECUTION_COMPLETED" not in log:
        raise CheckFailed("worker log has no EXECUTION_COMPLETED line for the job")
    if f"job {r['job_id']} REFUSED" not in log:
        raise CheckFailed("worker log has no REFUSED line for the job")
    return "1 ledger entry = receipt nonce; replay refused NONCE_ALREADY_SPENT while the receipt was still unexpired"


def check_verdict_inventory(repo: Path, _ctx: dict) -> str:
    files = sorted((repo / "verdicts").glob("*.md"))
    outcomes = {}
    for f in files:
        found = _VERDICT_LINE.findall(f.read_text(encoding="utf-8"))
        if len(found) != 1:
            raise CheckFailed(f"{f.name}: expected one verdict heading, found {found}")
        outcomes[f.name] = found[0].upper()
    blocks = sum(1 for v in outcomes.values() if v == "BLOCK")
    if len(files) != VERDICT_COUNT or blocks != VERDICT_BLOCKS:
        raise CheckFailed(f"{len(files)} verdicts, {blocks} BLOCK; README states {VERDICT_COUNT} and {VERDICT_BLOCKS}")
    return f"{len(files)} verdicts: {blocks} BLOCK, {len(files) - blocks} PASS"


CHECKS = [
    ("evidence-sums", check_evidence_sums),
    ("shipped-bytes", check_shipped_bytes),
    ("frozen-contracts", check_frozen_contracts),
    ("pre-integration", check_pre_integration),
    ("payload", check_payload),
    ("module-payload", check_module_payload),
    ("signature", check_signature),
    ("tamper", check_tamper),
    ("key-fingerprint", check_key_fingerprint),
    ("module-accepts", check_module_accepts),
    ("p1-consistency", check_p1_consistency),
    ("verdict-inventory", check_verdict_inventory),
]

# Checks that cannot run if an earlier one failed.
DEPENDS = {"module-payload": "payload", "signature": "payload", "tamper": "signature"}


def run_checks(repo: Path = REPO) -> list:
    results = []
    with tempfile.TemporaryDirectory(prefix="sr-verify-") as tmp:
        ctx = {"tmp": Path(tmp)}
        try:
            ctx["receipt"] = load_receipt(repo)
            ctx["module"] = load_module(repo)
        except (OSError, ValueError, CheckFailed) as exc:
            return [("load", False, f"{type(exc).__name__}: {exc}")]
        status = {}
        for name, fn in CHECKS:
            dep = DEPENDS.get(name)
            if dep and not status.get(dep):
                results.append((name, False, f"skipped: {dep} failed"))
                status[name] = False
                continue
            try:
                detail = fn(repo, ctx)
                ok = True
            except CheckFailed as exc:
                ok, detail = False, str(exc)
            except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
                ok, detail = False, f"{type(exc).__name__}: {exc}"
            status[name] = ok
            results.append((name, ok, detail))
    return results


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Verify the signed-resumption evidence bundle (read-only).")
    ap.add_argument("--json", action="store_true", help="print results as JSON")
    ap.add_argument("--repo", type=Path, default=REPO, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    results = run_checks(args.repo.resolve())
    if args.json:
        print(json.dumps([{"check": n, "ok": ok, "detail": d} for n, ok, d in results], indent=2))
    else:
        w = max(len(n) for n, _, _ in results)
        for name, ok, detail in results:
            print(f"{'PASS' if ok else 'FAIL'}  {name:<{w}}  {detail}")
        failed = sum(1 for _, ok, _ in results if not ok)
        print(f"\n{len(results) - failed}/{len(results)} checks passed")
    return 0 if all(ok for _, ok, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())
