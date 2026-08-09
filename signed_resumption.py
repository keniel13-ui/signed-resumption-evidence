#!/usr/bin/env python3
"""Signed resumption — pure verification for job_worker.

Implements body JOB_WORKER_SIGNED_RESUMPTION_PREREG_V2_2026-08-09.md
  sha256 7cc5d17dd49d8a05df4718106606d7cc848dac9f75988de575ccc33ce90e97f5
plus  JOB_WORKER_SIGNED_RESUMPTION_ADDENDUM_V2_1_2026-08-09.md
  sha256 ac3f5e9b8241e988c11287a00f0b9d2063aa8802dd28313e7178e8b1faa37ef5

Where the body and the addendum disagree, the addendum controls. The body's
argv_sha256 row and its single combined nonce ablation are withdrawn by R1/R3.

The worker and the health checker both import from here. Neither implements a
second signature policy.

Stdlib only. No network. Never holds or requests a private key.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone

SCHEMA_VERSION = 2
STATE_AUTHORIZED = "EXECUTION_AUTHORIZED"
TOOL = "repro"
PRINCIPAL = "keniel-owner"
NAMESPACE = "km-agent-execution-authorization"
SSH_KEYGEN = "/usr/bin/ssh-keygen"
MAX_WALL = 1500
MAX_RECEIPT_BYTES = 8192
MAX_SIGNATURE_BYTES = 4096
VERIFY_TIMEOUT = 10

SIGNED_KEYS = (
    "allowed_cwd",
    "expires_at",
    "job_digest",
    "job_id",
    "max_wall_seconds",
    "nonce",
    "route_manifest_sha256",
    "schema_version",
    "state",
    "tool",
)

_HEX64 = re.compile(r"\A[0-9a-f]{64}\Z")
_HEX32 = re.compile(r"\A[0-9a-f]{32}\Z")
_ARMOR = "-----BEGIN SSH SIGNATURE-----"


@dataclass(frozen=True)
class Config:
    """Injected by the caller. Never by a receipt.

    Defaults are the frozen production values. A breaker overrides these with
    its own fixture paths without editing this module.
    """

    trust_root: str = "/etc/keniel-agent/owner_execution_allowed_signers"
    trust_root_realpath: str = "/private/etc/keniel-agent/owner_execution_allowed_signers"
    require_root_owned: bool = True
    ledger: str = "/Users/kenielmaldonado/km_agent/state/execution_nonce_spent.jsonl"
    pause_marker: str = "/Users/kenielmaldonado/km_agent/JOB_WORKER_EXECUTION_PAUSED.json"
    argv: tuple = ("/usr/local/bin/python3", "repro.py")
    cwd: str = "/Users/kenielmaldonado/claim30_repro"
    principal: str = PRINCIPAL
    namespace: str = NAMESPACE


class Refusal(Exception):
    """Carries the frozen reason code. Never a free-form string at a call site."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


# ---------------------------------------------------------------- canonical bytes

def canonical_json(obj) -> bytes:
    """UTF-8, sorted keys, (",",":"), no trailing newline. R5/K2."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_payload(receipt: dict) -> bytes:
    """Exactly the signed keys. `signature` is never included."""
    return canonical_json({k: receipt[k] for k in SIGNED_KEYS})


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- R5 field schema

def _is_int(v) -> bool:
    # bool is a subclass of int; the contract refuses it where an integer is required.
    return isinstance(v, int) and not isinstance(v, bool)


def validate_schema(receipt) -> None:
    """Exact types. No coercion, no trimming, no normalisation. R5."""
    if not isinstance(receipt, dict):
        raise Refusal("RECEIPT_NOT_AN_OBJECT")
    keys = set(receipt)
    if keys - set(SIGNED_KEYS) - {"signature"}:
        raise Refusal("RECEIPT_HAS_UNEXPECTED_KEYS")
    if set(SIGNED_KEYS) - keys:
        raise Refusal("RECEIPT_MISSING_SIGNED_KEYS")

    if receipt["schema_version"] is not SCHEMA_VERSION and not (
        _is_int(receipt["schema_version"]) and receipt["schema_version"] == SCHEMA_VERSION
    ):
        raise Refusal("SCHEMA_VERSION_NOT_ACCEPTED")
    if receipt["state"] != STATE_AUTHORIZED:
        raise Refusal("STATE_NOT_EXECUTION_AUTHORIZED")
    if receipt["tool"] != TOOL:
        raise Refusal("TOOL_NOT_ON_THE_SIGNED_ROUTE")

    jid = receipt["job_id"]
    if not isinstance(jid, str) or not jid or len(jid) > 128 or any(ord(c) < 32 for c in jid):
        raise Refusal("JOB_ID_MALFORMED")
    for k, rx in (("job_digest", _HEX64), ("route_manifest_sha256", _HEX64), ("nonce", _HEX32)):
        v = receipt[k]
        if not isinstance(v, str) or not rx.match(v):
            raise Refusal(f"{k.upper()}_MALFORMED")

    cwd = receipt["allowed_cwd"]
    if not isinstance(cwd, str) or not cwd.startswith("/"):
        raise Refusal("ALLOWED_CWD_MALFORMED")

    mw = receipt["max_wall_seconds"]
    if not _is_int(mw):
        raise Refusal("MAX_WALL_SECONDS_NOT_AN_INTEGER")
    if mw < 1 or mw > MAX_WALL:
        raise Refusal("MAX_WALL_SECONDS_OUT_OF_RANGE")

    exp = receipt["expires_at"]
    if not isinstance(exp, str):
        raise Refusal("EXPIRES_AT_NOT_A_STRING")
    try:
        parsed = datetime.fromisoformat(exp.replace("Z", "+00:00"))
    except ValueError:
        raise Refusal("EXPIRES_AT_UNPARSEABLE")
    if parsed.tzinfo is None:
        raise Refusal("EXPIRES_AT_NOT_TIMEZONE_AWARE")

    sig = receipt.get("signature")
    if not isinstance(sig, str) or not sig.startswith(_ARMOR):
        raise Refusal("SIGNATURE_NOT_ARMORED_SSH")
    if len(sig.encode("utf-8")) > MAX_SIGNATURE_BYTES:
        raise Refusal("SIGNATURE_TOO_LARGE")


def not_expired(receipt: dict, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    exp = datetime.fromisoformat(str(receipt["expires_at"]).replace("Z", "+00:00"))
    return exp > now


# ---------------------------------------------------------------- R1 route manifest

def route_manifest(cfg: Config) -> dict:
    """Binds the bytes that will execute, not the filenames. R1."""
    interp = os.path.realpath(cfg.argv[0])
    script = os.path.realpath(os.path.join(cfg.cwd, cfg.argv[1]))
    return {
        "argv": list(cfg.argv),
        "cwd_realpath": os.path.realpath(cfg.cwd),
        "interpreter_realpath": interp,
        "interpreter_sha256": sha256_file(interp),
        "script_realpath": script,
        "script_sha256": sha256_file(script),
    }


def route_manifest_sha256(cfg: Config) -> str:
    return hashlib.sha256(canonical_json(route_manifest(cfg))).hexdigest()


# ---------------------------------------------------------------- K2 trust root

def check_trust_root(cfg: Config) -> None:
    """/etc is itself a root-owned symlink, so resolve then compare. Never a
    blanket symlink rejection, which would refuse the legitimate path."""
    real = os.path.realpath(cfg.trust_root)
    if real != cfg.trust_root_realpath:
        raise Refusal("TRUST_ROOT_PATH_UNEXPECTED")
    try:
        st = os.lstat(real)
    except OSError:
        raise Refusal("TRUST_ROOT_ABSENT")
    if not stat.S_ISREG(st.st_mode):
        raise Refusal("TRUST_ROOT_NOT_A_REGULAR_FILE")
    if cfg.require_root_owned and st.st_uid != 0:
        raise Refusal("TRUST_ROOT_NOT_ROOT_OWNED")
    if st.st_mode & 0o022:
        raise Refusal("TRUST_ROOT_WRITABLE_BY_NON_OWNER")
    pst = os.stat(os.path.dirname(real))
    if cfg.require_root_owned and pst.st_uid != 0:
        raise Refusal("TRUST_ROOT_PARENT_NOT_ROOT_OWNED")
    if pst.st_mode & 0o022:
        raise Refusal("TRUST_ROOT_PARENT_WRITABLE_BY_NON_OWNER")


def verify_signature(payload: bytes, signature: str, cfg: Config) -> None:
    """Fixed argv. Nothing here is receipt-controlled. Signature path is
    generated internally; a path supplied in a receipt is refused upstream."""
    check_trust_root(cfg)
    fd, sig_path = tempfile.mkstemp(prefix=".sigverify-", suffix=".sig")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(signature.encode("utf-8"))
        try:
            proc = subprocess.run(
                [
                    SSH_KEYGEN, "-Y", "verify",
                    "-f", cfg.trust_root,
                    "-I", cfg.principal,
                    "-n", cfg.namespace,
                    "-s", sig_path,
                ],
                input=payload,
                capture_output=True,
                timeout=VERIFY_TIMEOUT,
                shell=False,
            )
        except subprocess.TimeoutExpired:
            raise Refusal("SIGNATURE_VERIFY_TIMEOUT")
        except OSError:
            raise Refusal("SIGNATURE_VERIFIER_UNAVAILABLE")
        if proc.returncode != 0:
            raise Refusal("SIGNATURE_INVALID")
    finally:
        try:
            os.unlink(sig_path)
        except OSError:
            pass


# ---------------------------------------------------------------- R3 nonce ledger

def _read_ledger(fh) -> set:
    """Fail closed. A truncated or malformed final line makes the whole ledger
    unreadable rather than yielding an unspent verdict."""
    fh.seek(0)
    raw = fh.read()
    if not raw:
        return set()
    if not raw.endswith("\n"):
        raise Refusal("NONCE_LEDGER_TRUNCATED")
    spent = set()
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            raise Refusal("NONCE_LEDGER_MALFORMED")
        if not isinstance(rec, dict) or "nonce" not in rec:
            raise Refusal("NONCE_LEDGER_MALFORMED")
        spent.add(rec["nonce"])
    return spent


def check_and_spend_nonce(nonce: str, job_id: str, cfg: Config) -> None:
    """Atomic. Lock held across re-read, append, flush, fsync. Called before the
    executor. At-most-once: a crash after this point does not auto-retry. R3."""
    os.makedirs(os.path.dirname(cfg.ledger), exist_ok=True)
    with open(cfg.ledger, "a+", encoding="utf-8") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            if nonce in _read_ledger(fh):
                raise Refusal("NONCE_ALREADY_SPENT")
            fh.seek(0, os.SEEK_END)
            fh.write(json.dumps(
                {"nonce": nonce, "job_id": job_id,
                 "spent_at_utc": datetime.now(timezone.utc).isoformat()},
                sort_keys=True, separators=(",", ":")) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


# ---------------------------------------------------------------- R4 health state

def health_state(receipt, cfg: Config, now: datetime | None = None) -> dict:
    """Ordered. First match wins. Shared by the worker and the checker. R4."""
    tamper = False
    if os.path.exists(cfg.pause_marker):
        try:
            if isinstance(receipt, dict):
                validate_schema(receipt)
                verify_signature(canonical_payload(receipt), receipt["signature"], cfg)
        except Refusal:
            tamper = True
        return {"state": "PAUSED_BLOCKED", "tamper": tamper, "allow": False}
    if not isinstance(receipt, dict) or not receipt:
        return {"state": "PARKED", "tamper": False, "allow": False}
    try:
        check_trust_root(cfg)
    except Refusal:
        return {"state": "PARKED", "tamper": False, "allow": False}
    try:
        validate_schema(receipt)
        verify_signature(canonical_payload(receipt), receipt["signature"], cfg)
    except Refusal:
        return {"state": "TAMPERED", "tamper": True, "allow": False}
    if not not_expired(receipt, now):
        return {"state": "PARKED", "tamper": False, "allow": False}
    try:
        with open(cfg.ledger, "a+", encoding="utf-8") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                spent = _read_ledger(fh)
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except Refusal:
        return {"state": "PARKED", "tamper": False, "allow": False}
    except OSError:
        return {"state": "PARKED", "tamper": False, "allow": False}
    if receipt["nonce"] in spent:
        return {"state": "PARKED", "tamper": False, "allow": False}
    if receipt["route_manifest_sha256"] != route_manifest_sha256(cfg):
        return {"state": "TAMPERED", "tamper": True, "allow": False}
    return {"state": "ARMED", "tamper": False, "allow": False}


# ---------------------------------------------------------------- the one decision

def authorize(job: dict, receipt, cfg: Config, now: datetime | None = None) -> int:
    """Called EXACTLY ONCE, at the final executor boundary. Returns the timeout
    the executor must use. Raises Refusal otherwise. Never returns on failure.

    Order matters: pause dominates, bytes are verified before the route is
    trusted, and the nonce is spent last so a refusal never consumes it.
    """
    if os.path.exists(cfg.pause_marker):
        raise Refusal("EXECUTION_PAUSE_ACTIVE")
    if not isinstance(job, dict):
        raise Refusal("NO_BOUND_JOB")
    if isinstance(receipt, (bytes, str)) and len(receipt) > MAX_RECEIPT_BYTES:
        raise Refusal("RECEIPT_TOO_LARGE")

    validate_schema(receipt)
    if receipt["job_id"] != job.get("id"):
        raise Refusal("RECEIPT_NOT_BOUND_TO_THIS_JOB_ID")
    if not not_expired(receipt, now):
        raise Refusal("RECEIPT_EXPIRED")

    # bytes first, parse second: the signature covers the canonical payload
    verify_signature(canonical_payload(receipt), receipt["signature"], cfg)

    # R1: recomputed here, immediately before execution, not at parse time
    if receipt["route_manifest_sha256"] != route_manifest_sha256(cfg):
        raise Refusal("ROUTE_MANIFEST_MISMATCH")
    if os.path.realpath(receipt["allowed_cwd"]) != os.path.realpath(cfg.cwd):
        raise Refusal("ALLOWED_CWD_MISMATCH")

    check_and_spend_nonce(receipt["nonce"], receipt["job_id"], cfg)

    # R2: the signed integer is the executor's timeout, capped by the route ceiling
    return min(int(receipt["max_wall_seconds"]), MAX_WALL)
