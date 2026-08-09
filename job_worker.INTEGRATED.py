#!/usr/bin/env python3
"""
Job worker — the third domino (Mac executor).

Flow:
  Keniel (phone) → @Godhighpower_bot → jobs.jsonl + GOD_JOBS.md
  → this worker polls → runs allowlisted /run OR headless agent for AUTO: jobs
  → closes job → Telegram reply

This is NOT injection into an open Grok TUI. It is a separate headless process
on the home Mac. That is the only reliable unattended path.

Hard lines: no money, trade, auto-outreach; cwd allowlist; max wall time;
headless only for jobs marked AUTO: / EXEC: / assign=auto.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import subprocess
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
AGENT_DIR = os.path.join(HOME, "km_agent")
JOBS_JSONL = os.path.join(AGENT_DIR, "jobs.jsonl")
TOKEN_FILE = os.path.join(AGENT_DIR, "bot_token.txt")
CHATID_FILE = os.path.join(AGENT_DIR, "chat_id.txt")
WORKER_LOG = os.path.join(AGENT_DIR, "job_worker.log")
WORKER_LOCK = os.path.join(AGENT_DIR, "job_worker.lock")
EXECUTION_PAUSE = os.path.join(AGENT_DIR, "JOB_WORKER_EXECUTION_PAUSED.json")
EXECUTION_AUTHORIZATION = os.path.join(
    AGENT_DIR, "JOB_WORKER_EXECUTION_AUTHORIZED.json"
)
# A future authorization verifier must anchor outside every same-user agent's
# write reach. This path is intentionally not provisioned by this repair.
AUTHORIZATION_TRUST_ROOT = "/etc/keniel-agent/owner_execution_allowed_signers"
REFUSAL_LOG = os.path.join(AGENT_DIR, "job_worker_refusals.jsonl")
CLAIM30 = os.path.join(HOME, "claim30_repro")
POLL_SEC = 20
MAX_WALL = 25 * 60  # 25 minutes per headless job
MAX_TURNS = 40
GROK = os.path.expanduser("~/.grok/bin/grok")
CLAUDE = os.path.expanduser("~/.npm-global/bin/claude")

# Directories headless agent may work in
CWD_ALLOW = (
    CLAIM30,
    os.path.join(HOME, "INBOX"),
    AGENT_DIR,
)

import sys

sys.path.insert(0, AGENT_DIR)
import god_jobs  # noqa: E402

_LOCK_HANDLE = None


def log(msg: str) -> None:
    line = "%s  %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        with open(WORKER_LOG, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass
    print(line, end="", flush=True)


def acquire_singleton() -> bool:
    """Hold an OS-backed lock for the lifetime of this worker.

    A PID file alone can become stale. flock is released by the kernel when the
    owning process exits, so a crashed worker cannot strand the service.
    """
    global _LOCK_HANDLE
    handle = open(WORKER_LOCK, "a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        log("job_worker refused: another process owns %s" % WORKER_LOCK)
        return False

    handle.seek(0)
    handle.truncate()
    handle.write("%s\n" % os.getpid())
    handle.flush()
    os.fsync(handle.fileno())
    _LOCK_HANDLE = handle
    return True


def read_file(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


def pause_receipt() -> dict | None:
    raw = read_file(EXECUTION_PAUSE)
    if not raw:
        return None
    try:
        receipt = json.loads(raw)
    except json.JSONDecodeError:
        # A malformed marker still fails closed.
        return {"state": "PAUSED", "reason": "pause marker is malformed"}
    if not isinstance(receipt, dict):
        return {"state": "PAUSED", "reason": "pause marker is not an object"}
    return receipt


def execution_paused() -> bool:
    return os.path.exists(EXECUTION_PAUSE)


def file_digest_id(path: str, missing: str) -> str:
    raw = read_file(path)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16] if raw else missing


def pause_id() -> str:
    return file_digest_id(EXECUTION_PAUSE, "pause-marker-missing")


def authorization_id() -> str:
    return file_digest_id(EXECUTION_AUTHORIZATION, "authorization-missing")


def job_digest(job: dict) -> str:
    bound = {
        "assign": job.get("assign"),
        "id": job.get("id"),
        "text": job.get("text"),
    }
    raw = json.dumps(
        bound,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def authorization_receipt() -> tuple[dict | None, str]:
    if not os.path.exists(EXECUTION_AUTHORIZATION):
        return None, "explicit execution authorization is absent"
    raw = read_file(EXECUTION_AUTHORIZATION)
    if not raw:
        return None, "explicit execution authorization is empty"
    try:
        receipt = json.loads(raw)
    except json.JSONDecodeError:
        return None, "explicit execution authorization is malformed"
    if not isinstance(receipt, dict):
        return None, "explicit execution authorization is not an object"
    return receipt, ""


def independent_signature_verified(receipt: dict) -> tuple[bool, str]:
    """Fail closed until an independently rooted verifier is frozen and audited.

    A same-user HMAC, public key, or boolean in AGENT_DIR would be writable by
    the same agents this gate constrains. This repair deliberately does not
    pretend that such a marker is an independent authorization.
    """
    del receipt
    if not os.path.exists(AUTHORIZATION_TRUST_ROOT):
        return False, "independent owner authorization trust root is not provisioned"
    return False, "independent signature verification is not implemented"


def execution_decision(job: dict | None, cwd: str) -> tuple[bool, str]:
    if execution_paused():
        return False, "explicit fail-closed pause is active"
    if not isinstance(job, dict):
        return False, "execution request has no bound job"

    receipt, error = authorization_receipt()
    if receipt is None:
        return False, error
    if receipt.get("schema_version") != 1:
        return False, "authorization schema version is not accepted"
    if receipt.get("state") != "EXECUTION_AUTHORIZED":
        return False, "authorization state is not EXECUTION_AUTHORIZED"
    if receipt.get("job_id") != job.get("id"):
        return False, "authorization is not bound to this job id"
    if receipt.get("job_digest") != job_digest(job):
        return False, "authorization is not bound to this job content"

    try:
        allowed_cwd = os.path.realpath(str(receipt["allowed_cwd"]))
        requested_cwd = os.path.realpath(cwd)
    except (KeyError, TypeError, ValueError):
        return False, "authorization has no valid working directory"
    if allowed_cwd != requested_cwd:
        return False, "authorization is not bound to this working directory"

    try:
        max_wall_seconds = int(receipt["max_wall_seconds"])
    except (KeyError, TypeError, ValueError):
        return False, "authorization has no valid wall-time bound"
    if max_wall_seconds < 1 or max_wall_seconds > MAX_WALL:
        return False, "authorization wall-time exceeds the worker boundary"

    try:
        expires_at = datetime.fromisoformat(
            str(receipt["expires_at"]).replace("Z", "+00:00")
        )
    except (KeyError, TypeError, ValueError):
        return False, "authorization expiry is missing or invalid"
    if expires_at.tzinfo is None:
        return False, "authorization expiry is not timezone-aware"
    if expires_at <= datetime.now(timezone.utc):
        return False, "authorization has expired"

    verified, reason = independent_signature_verified(receipt)
    if not verified:
        return False, reason
    return True, "independently verified, job-bound execution authorization"


def refusal_key(job: dict) -> str:
    return "%s:%s:%s" % (pause_id(), authorization_id(), job.get("id", "?"))


def refusal_already_recorded(key: str) -> bool:
    if not os.path.exists(REFUSAL_LOG):
        return False
    try:
        with open(REFUSAL_LOG, encoding="utf-8") as f:
            for line in f:
                try:
                    if json.loads(line).get("refusal_key") == key:
                        return True
                except json.JSONDecodeError:
                    continue
    except OSError:
        return False
    return False


def record_execution_refusal(job: dict, reason: str) -> dict:
    key = refusal_key(job)
    receipt = {
        "schema_version": 1,
        "record_type": "job_worker_execution_refusal",
        "ts": datetime.now(timezone.utc).isoformat(),
        "refusal_key": key,
        "pause_id": pause_id(),
        "authorization_id": authorization_id(),
        "job_id": job.get("id"),
        "job_digest": job_digest(job),
        "assign": job.get("assign"),
        "matched_auto": is_auto(job),
        "execution_authorized": False,
        "reason": reason,
    }
    if refusal_already_recorded(key):
        return receipt
    with open(REFUSAL_LOG, "a", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        f.write(json.dumps(receipt, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    log("job %s REFUSED by default-deny execution gate" % job.get("id", "?"))
    return receipt


def telegram(text: str) -> None:
    token = read_file(TOKEN_FILE)
    chat = read_file(CHATID_FILE)
    if not token or not chat:
        return
    if len(text) > 3900:
        text = text[:3850] + "\n…(truncated)"
    data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
    url = "https://api.telegram.org/bot%s/sendMessage" % token
    try:
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=30)
    except Exception as e:
        log("telegram send failed: %s" % e)


def load_jobs() -> list[dict]:
    if not os.path.exists(JOBS_JSONL):
        return []
    rows = []
    with open(JOBS_JSONL, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def is_auto(job: dict) -> bool:
    text = (job.get("text") or "").strip()
    assign = (job.get("assign") or "").lower()
    if assign in ("auto", "executor", "run"):
        return True
    low = text.lower()
    return low.startswith("auto:") or low.startswith("exec:") or low.startswith("/auto ")


def strip_auto_prefix(text: str) -> str:
    t = text.strip()
    low = t.lower()
    for p in ("auto:", "exec:", "/auto "):
        if low.startswith(p):
            return t[len(p) :].strip()
    return t


def pick_open_auto(rows: list[dict]) -> dict | None:
    for r in rows:
        if r.get("status") != "open":
            continue
        if is_auto(r):
            return r
    return None


def run_headless(
    prompt: str, cwd: str, job: dict | None = None
) -> tuple[int, str]:
    """Prefer Grok multi-turn headless; fall back to Claude -p."""
    authorized, reason = execution_decision(job, cwd)
    if not authorized:
        return 126, "BLOCKED: %s" % reason
    env = os.environ.copy()
    env["CI"] = "1"
    # Grok: non-interactive style flags from CLI help
    if os.path.isfile(GROK):
        cmd = [
            GROK,
            "--always-approve",
            "--max-turns",
            str(MAX_TURNS),
            "--cwd",
            cwd,
            "--output-format",
            "plain",
            "--no-plan",
            prompt,
        ]
        try:
            p = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=MAX_WALL,
                env=env,
            )
            out = (p.stdout or "") + "\n" + (p.stderr or "")
            return p.returncode, out.strip()
        except subprocess.TimeoutExpired as e:
            out = ((e.stdout or "") + "\n" + (e.stderr or "")).strip()
            return 124, "TIMEOUT after %ss\n%s" % (MAX_WALL, out[:2000])
        except Exception as e:
            log("grok failed: %s — trying claude" % e)

    if os.path.isfile(CLAUDE):
        cmd = [
            CLAUDE,
            "-p",
            prompt,
            "--allowedTools",
            "Read,Edit,Write,Bash,Glob,Grep",
            "--max-turns",
            str(MAX_TURNS),
        ]
        try:
            p = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=MAX_WALL,
                env=env,
            )
            out = (p.stdout or "") + "\n" + (p.stderr or "")
            return p.returncode, out.strip()
        except subprocess.TimeoutExpired:
            return 124, "TIMEOUT (claude)"
        except Exception as e:
            return 1, "claude failed: %s" % e

    return 1, "No headless agent binary found (grok/claude)"


def looks_rate_limited(text: str) -> bool:
    t = text.lower()
    needles = (
        "rate limit",
        "rate_limit",
        "usage limit",
        "quota",
        "too many requests",
        "429",
        "capacity",
        "overloaded",
    )
    return any(n in t for n in needles)


# ---- signed resumption (integration freeze 74fcec15…adf8 + addendum b06c1781…5829) ----

SIGNED_ROUTE_KEY = "repro"
SIGNED_RESUMPTION_MODULE = "/Users/kenielmaldonado/signed-resumption-candidate/signed_resumption.py"
SIGNED_RESUMPTION_SHA256 = "bba4c1a4513db19475bdaec95348b03247f091081bbf89935d145f0c6cf32000"


def _load_signed_resumption():
    """I8: a reviewed module that can be swapped at import time is not reviewed.
    Load by absolute path and refuse unless the file digest is the reviewed one."""
    import importlib.util

    with open(SIGNED_RESUMPTION_MODULE, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()
    if digest != SIGNED_RESUMPTION_SHA256:
        raise RuntimeError("signed_resumption module digest mismatch: %s" % digest)
    spec = importlib.util.spec_from_file_location(
        "_signed_resumption_reviewed", SIGNED_RESUMPTION_MODULE
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_signed_route(job: dict) -> dict:
    """The one open position. IR1: the receipt comes from the existing
    EXECUTION_AUTHORIZATION constant, read as raw bytes. IR2: the config is the
    zero-argument production Config and is asserted against a fresh one, so a
    fixture cannot reach this path."""
    sr = _load_signed_resumption()

    if os.path.realpath(EXECUTION_AUTHORIZATION) != EXECUTION_AUTHORIZATION:
        raise RuntimeError("authorization path is not the frozen constant")
    with open(EXECUTION_AUTHORIZATION, "rb") as fh:
        raw_receipt = fh.read()

    cfg = sr.Config()
    if cfg != sr.Config():
        raise RuntimeError("NON_PRODUCTION_CONFIG_ON_SIGNED_ROUTE")

    return sr.execute_authorized_job(job, raw_receipt, cfg)


def process_one(job: dict) -> None:
    jid = job.get("id", "?")
    raw = job.get("text") or ""
    prompt = strip_auto_prefix(raw)
    # Default work dir: suite (safest known project)
    cwd = CLAIM30 if os.path.isdir(CLAIM30) else HOME
    if not any(os.path.samefile(cwd, a) if os.path.isdir(a) else cwd.startswith(a) for a in CWD_ALLOW):
        cwd = CLAIM30
    # K3 ordering fix: the route is derived BEFORE any authorization decision.
    # `prompt` is already strip_auto_prefix(raw) above, which is IR3.
    key = prompt.strip().lower().split()[0] if prompt.strip() else ""

    # The one open position. Every other key, freeform prompt and headless path
    # falls through to the default-deny gate below, unchanged.
    if key == SIGNED_ROUTE_KEY and os.path.exists(EXECUTION_AUTHORIZATION):
        try:
            outcome = run_signed_route(job)
        except Exception as exc:
            record_execution_refusal(job, "signed route refused: %s" % exc)
            return
        log("job %s signed route %s" % (jid, outcome.get("outcome")))
        god_jobs.close_job("%s %s" % (jid, outcome.get("outcome")))
        return

    authorized, reason = execution_decision(job, cwd)
    if not authorized:
        record_execution_refusal(job, reason)
        return

    # Fast path: pure allowlist keywords
    if key in god_jobs.ALLOWLIST:
        log("job %s allowlist /run %s" % (jid, key))
        result = god_jobs.run_allowlisted(key)
        # run_allowlisted already closed a synthetic job; close this one too
        god_jobs.close_job("%s %s" % (jid, result[:500].replace("\n", " ")))
        telegram("AUTO-RUN done [%s]\n%s" % (jid, result[:1500]))
        return

    full_prompt = (
        "You are the home-Mac unattended executor for Keniel. "
        "Read ~/INBOX/GOD_JOBS.md and ~/BRAIN_CURRENT.md L0-L1 if needed. "
        "Hard lines: no money movement, no trading, no auto-send outreach, "
        "no force-push, no reading bot tokens into chat. "
        "Work only in allowlisted project dirs (claim30_repro preferred). "
        "When done, summarize what changed and what is still open.\n\n"
        "JOB:\n%s\n" % prompt
    )
    log("job %s headless start cwd=%s" % (jid, cwd))
    telegram("AUTO job started [%s]\n%s" % (jid, prompt[:400]))
    code, out = run_headless(full_prompt, cwd, job)
    summary = out[-2500:] if len(out) > 2500 else out
    if looks_rate_limited(out) or code != 0 and looks_rate_limited(out):
        # leave open + mark retry delay in outcome field? keep open, set note
        rows = load_jobs()
        for r in rows:
            if r.get("id") == jid:
                r["retry_after"] = int(time.time()) + 3600
                r["last_error"] = "rate_limit_or_fail"
                break
        # rewrite whole file
        tmp = JOBS_JSONL + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.replace(tmp, JOBS_JSONL)
        god_jobs.rewrite_markdown()
        telegram(
            "AUTO job RATE-LIMITED / failed [%s] — will retry after ~1h\ncode=%s\n%s"
            % (jid, code, summary[:1200])
        )
        log("job %s rate-limit/fail code=%s" % (jid, code))
        return

    god_jobs.close_job("%s code=%s %s" % (jid, code, summary[:800].replace("\n", " | ")))
    telegram("AUTO job DONE [%s] exit=%s\n%s" % (jid, code, summary[:1500]))
    log("job %s done code=%s" % (jid, code))


def main() -> None:
    if not acquire_singleton():
        return
    log(
        "job_worker live poll=%ss authorization_mode=explicit-independent-receipt "
        "execution_authorized_default=false pause_active=%s"
        % (POLL_SEC, str(execution_paused()).lower())
    )
    while True:
        try:
            rows = load_jobs()
            # skip jobs with retry_after in future
            now = int(time.time())
            candidates = []
            for r in rows:
                if r.get("status") != "open":
                    continue
                if not is_auto(r):
                    continue
                ra = r.get("retry_after") or 0
                if ra and int(ra) > now:
                    continue
                candidates.append(r)
            if candidates:
                # oldest first
                job = candidates[0]
                process_one(job)
            time.sleep(POLL_SEC)
        except Exception as e:
            log("loop error: %s" % e)
            time.sleep(30)


def self_test_authorization() -> int:
    import tempfile
    from unittest.mock import patch

    fake_job = {
        "id": "SELFTEST-AUTHORIZATION",
        "status": "open",
        "assign": "run",
        "text": "EXEC: this must never execute",
    }
    fake_allowlist_job = {
        "id": "SELFTEST-ALLOWLIST",
        "status": "open",
        "assign": "run",
        "text": "EXEC: repro",
    }
    global EXECUTION_PAUSE
    global EXECUTION_AUTHORIZATION
    global AUTHORIZATION_TRUST_ROOT
    global REFUSAL_LOG
    original_paths = (
        EXECUTION_PAUSE,
        EXECUTION_AUTHORIZATION,
        AUTHORIZATION_TRUST_ROOT,
        REFUSAL_LOG,
    )
    cases: dict[str, dict] = {}
    try:
        with tempfile.TemporaryDirectory(prefix="job-worker-auth-test-") as tempdir:
            EXECUTION_PAUSE = os.path.join(tempdir, "PAUSED.json")
            EXECUTION_AUTHORIZATION = os.path.join(tempdir, "AUTHORIZED.json")
            AUTHORIZATION_TRUST_ROOT = os.path.join(tempdir, "unprovisioned-trust-root")
            REFUSAL_LOG = os.path.join(tempdir, "refusals.jsonl")
            fake_authorization = {
                "schema_version": 1,
                "state": "EXECUTION_AUTHORIZED",
                "job_id": fake_job["id"],
                "job_digest": job_digest(fake_job),
                "allowed_cwd": os.path.realpath(CLAIM30),
                "max_wall_seconds": MAX_WALL,
                "expires_at": "2099-01-01T00:00:00+00:00",
                "authorized_by": "SELFTEST-UNTRUSTED",
                "signature": "not-an-independent-signature",
            }

            with patch.object(subprocess, "run") as mocked_run:
                # Ka'el's attack direction: deleting the pause must not restore
                # authority when no explicit authorization exists.
                with open(EXECUTION_PAUSE, "w", encoding="utf-8") as f:
                    json.dump({"state": "PAUSED"}, f)
                os.unlink(EXECUTION_PAUSE)
                code, message = run_headless(
                    "SELFTEST: deleted pause", CLAIM30, fake_job
                )
                cases["pause_deleted_no_authorization"] = {
                    "code": code,
                    "message": message,
                }

                with open(EXECUTION_AUTHORIZATION, "w", encoding="utf-8") as f:
                    f.write("{not-json")
                code, message = run_headless(
                    "SELFTEST: malformed authorization", CLAIM30, fake_job
                )
                cases["malformed_authorization"] = {
                    "code": code,
                    "message": message,
                }

                with open(EXECUTION_AUTHORIZATION, "w", encoding="utf-8") as f:
                    json.dump(fake_authorization, f, sort_keys=True)
                code, message = run_headless(
                    "SELFTEST: same-user fake authorization", CLAIM30, fake_job
                )
                cases["same_user_unsigned_authorization"] = {
                    "code": code,
                    "message": message,
                }

                with open(EXECUTION_PAUSE, "w", encoding="utf-8") as f:
                    json.dump({"state": "PAUSED"}, f)
                code, message = run_headless(
                    "SELFTEST: pause overrides authorization", CLAIM30, fake_job
                )
                cases["pause_overrides_authorization"] = {
                    "code": code,
                    "message": message,
                }

                os.unlink(EXECUTION_PAUSE)
                os.unlink(EXECUTION_AUTHORIZATION)
                with patch.object(god_jobs, "run_allowlisted") as mocked_allowlist:
                    process_one(fake_allowlist_job)
                cases["allowlist_pause_deleted_no_authorization"] = {
                    "code": 126,
                    "message": "BLOCKED before god_jobs.run_allowlisted",
                    "allowlist_calls": mocked_allowlist.call_count,
                }

                refusal = record_execution_refusal(
                    fake_job,
                    "self-test proves default-deny without launching a subprocess",
                )
                subprocess_calls = mocked_run.call_count
    finally:
        (
            EXECUTION_PAUSE,
            EXECUTION_AUTHORIZATION,
            AUTHORIZATION_TRUST_ROOT,
            REFUSAL_LOG,
        ) = original_paths

    passed = (
        all(case["code"] == 126 for case in cases.values())
        and subprocess_calls == 0
        and cases["allowlist_pause_deleted_no_authorization"][
            "allowlist_calls"
        ] == 0
        and refusal.get("execution_authorized") is False
    )
    report = {
        "production_pause_marker_present": execution_paused(),
        "production_authorization_marker_present": os.path.exists(
            EXECUTION_AUTHORIZATION
        ),
        "independent_trust_root_present": os.path.exists(
            AUTHORIZATION_TRUST_ROOT
        ),
        "pause_receipt": pause_receipt(),
        "candidate_is_auto": is_auto(fake_job),
        "execution_authorized_default": False,
        "cases": cases,
        "subprocess_calls": subprocess_calls,
        "refusal_recorded": refusal.get("execution_authorized") is False,
        "refusal_key": refusal.get("refusal_key"),
        "passed": passed,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    if "--self-test-pause" in sys.argv or "--self-test-authorization" in sys.argv:
        raise SystemExit(self_test_authorization())
    main()
