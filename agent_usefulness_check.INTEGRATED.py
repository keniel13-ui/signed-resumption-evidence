#!/usr/bin/env python3
"""
agent_usefulness_check.py — Liveness is not usefulness.

Practice what we preach: a process can be UP while its artifact is DEAD.
Reads AGENT_PURPOSE_LEDGER.json and reports the operational state that the
declared agent actually earns. A PID or a quiet event-listener log is not
enough evidence by itself.

  python3 scripts/agent_usefulness_check.py
  python3 scripts/agent_usefulness_check.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

LEDGER = Path("/Users/kenielmaldonado/agent_outputs/AGENT_PURPOSE_LEDGER.json")

HEALTHY_STATES = {"FUNCTIONAL", "READY", "IDLE", "PARKED"}
DEGRADED_STATES = {"DEGRADED", "BACKLOG"}
FAILED_STATES = {"FAILED", "UNKNOWN"}
LAUNCH_AGENTS_DIR = Path("/Users/kenielmaldonado/Library/LaunchAgents")


def newest_in_dir(dirpath: Path, glob_pat: str | None) -> Path | None:
    if not dirpath.is_dir():
        return None
    paths = list(dirpath.glob(glob_pat or "*")) if glob_pat else list(dirpath.iterdir())
    files = [p for p in paths if p.is_file()]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def age_hours(path: Path, now: float) -> float | None:
    if not path.exists():
        return None
    return (now - path.stat().st_mtime) / 3600.0


def base_row(agent: dict, **fields: object) -> dict:
    row = {
        "id": agent["id"],
        "purpose": agent.get("purpose", ""),
        "outbound": agent.get("outbound", "none"),
        "note": agent.get("status_note", ""),
    }
    row.update(fields)
    return row


def artifact_row(agent: dict, now: float) -> dict:
    art = Path(agent["artifact"])
    glob_pat = agent.get("artifact_glob")
    max_h = float(agent.get("max_age_hours", 24))
    path = art
    if art.is_dir() or glob_pat:
        path = newest_in_dir(art if art.is_dir() else art.parent, glob_pat)
        if path is None:
            return base_row(
                agent,
                state="FAILED",
                age_hours=None,
                path=str(art),
                reason="declared artifact is missing",
            )
    if not path.exists():
        return base_row(
            agent,
            state="FAILED",
            age_hours=None,
            path=str(path),
            reason="declared artifact is missing",
        )
    age_h = age_hours(path, now)
    assert age_h is not None
    if age_h <= max_h:
        state = "FUNCTIONAL"
        reason = "current purpose artifact"
    elif age_h <= max_h * 3:
        state = "DEGRADED"
        reason = "artifact is older than its declared interval"
    else:
        state = "FAILED"
        reason = "artifact is beyond three times its declared interval"
    return base_row(
        agent,
        state=state,
        age_hours=round(age_h, 1),
        max_age_hours=max_h,
        path=str(path),
        reason=reason,
    )


def event_listener_row(agent: dict, health: dict, now: float) -> dict:
    heartbeat = Path(health["heartbeat_artifact"])
    max_minutes = float(health.get("max_age_minutes", 5))
    age_h = age_hours(heartbeat, now)
    if age_h is None:
        return base_row(
            agent,
            state="FAILED",
            age_hours=None,
            path=str(heartbeat),
            reason="event-listener state receipt is missing",
        )
    if age_h * 60 <= max_minutes:
        state = "READY"
        reason = "event-listener state is advancing; a quiet conversation log is expected when idle"
    else:
        state = "FAILED"
        reason = "event-listener state stopped advancing"
    return base_row(
        agent,
        state=state,
        age_hours=round(age_h, 3),
        max_age_hours=round(max_minutes / 60.0, 3),
        path=str(heartbeat),
        reason=reason,
    )


def markdown_entry_row(agent: dict, health: dict, now: float) -> dict:
    heartbeat = Path(health["heartbeat_artifact"])
    title = str(health["entry_title"])
    required_text = [str(value) for value in health.get("required_text", [])]
    max_minutes = float(health.get("max_age_minutes", 75))
    if not heartbeat.exists():
        return base_row(
            agent,
            state="FAILED",
            age_hours=None,
            path=str(heartbeat),
            reason=f"markdown heartbeat file is missing for entry {title!r}",
        )
    text = heartbeat.read_text(encoding="utf-8", errors="replace")
    pattern = re.compile(
        rf"^## \[(\d{{4}}-\d{{2}}-\d{{2}} \d{{2}}:\d{{2}})\] - {re.escape(title)}\s*$",
        re.MULTILINE,
    )
    matches = list(pattern.finditer(text))
    if not matches:
        return base_row(
            agent,
            state="FAILED",
            age_hours=None,
            path=str(heartbeat),
            reason=f"no markdown heartbeat entry titled {title!r}",
        )
    match = matches[-1]
    block_end = text.find("\n---", match.end())
    block = text[match.end():] if block_end == -1 else text[match.end():block_end]
    missing = [value for value in required_text if value not in block]
    if missing:
        return base_row(
            agent,
            state="FAILED",
            age_hours=None,
            path=str(heartbeat),
            reason=f"latest {title!r} entry is incomplete; missing {missing}",
        )
    created = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M").replace(
        tzinfo=ZoneInfo(str(health.get("timezone", "America/New_York")))
    )
    age_h = max(0.0, (now - created.timestamp()) / 3600.0)
    if age_h * 60 <= max_minutes:
        state = "READY"
        reason = f"fresh non-skip {title!r} receipt contains its required fields"
    else:
        state = "FAILED"
        reason = f"latest non-skip {title!r} receipt is stale"
    return base_row(
        agent,
        state=state,
        age_hours=round(age_h, 3),
        max_age_hours=round(max_minutes / 60.0, 3),
        path=str(heartbeat),
        reason=reason,
    )


def recovery_listener_row(agent: dict, health: dict, now: float) -> dict:
    marker = Path(health["marker"])
    if marker.exists():
        return base_row(
            agent,
            state="PARKED",
            age_hours=age_hours(marker, now),
            path=str(marker),
            reason="declared recovery gate is present",
        )
    row = (
        markdown_entry_row(agent, health, now)
        if health.get("entry_title")
        else event_listener_row(agent, health, now)
    )
    if row["state"] == "READY":
        row["reason"] = f"recovery gate is clear; {row['reason']}"
    else:
        row["state"] = "UNKNOWN"
        row["reason"] = "recovery gate is clear, but the supervised loop receipt is stale or missing"
    return row


def latest_json_record(path: Path) -> dict | None:
    if not path.exists():
        return None
    for line in reversed(path.read_text(encoding="utf-8", errors="replace").splitlines()):
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    return None


def latest_matching_json_record(path: Path, match: dict) -> dict | None:
    if not path.exists():
        return None
    for line in reversed(path.read_text(encoding="utf-8", errors="replace").splitlines()):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if all(record.get(key) == value for key, value in match.items()):
            return record
    return None


def jsonl_heartbeat_row(agent: dict, health: dict, now: float) -> dict:
    path = Path(health["receipt_artifact"])
    match = health.get("match", {})
    max_minutes = float(health.get("max_age_minutes", 45))
    receipt = latest_matching_json_record(path, match)
    if receipt is None:
        return base_row(
            agent,
            state="FAILED",
            age_hours=None,
            path=str(path),
            reason=f"no structured heartbeat matches {match}",
        )
    created_at = receipt.get("created_at") or receipt.get("ts")
    try:
        created_ts = datetime.fromisoformat(str(created_at).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return base_row(
            agent,
            state="FAILED",
            age_hours=None,
            path=str(path),
            reason="matching heartbeat has no readable timestamp",
            receipt=receipt,
        )
    age_h = max(0.0, (now - created_ts) / 3600.0)
    if age_h * 60 <= max_minutes:
        state = "READY"
        reason = "structured heartbeat is current; a quiet briefing log is expected when idle"
    else:
        state = "FAILED"
        reason = "structured heartbeat is stale"
    return base_row(
        agent,
        state=state,
        age_hours=round(age_h, 3),
        max_age_hours=round(max_minutes / 60.0, 3),
        path=str(path),
        reason=reason,
        receipt=receipt,
    )


def coverage_row(agent: dict, health: dict, now: float) -> dict:
    path = Path(health["receipt_artifact"])
    max_h = float(agent.get("max_age_hours", 24))
    age_h = age_hours(path, now)
    receipt = latest_json_record(path)
    if age_h is None or receipt is None:
        return base_row(
            agent,
            state="FAILED",
            age_hours=None,
            path=str(path),
            reason="coverage receipt is missing or unreadable",
        )
    errors = int(receipt.get(health.get("error_field", "feeds_with_errors"), 0))
    max_errors = int(health.get("max_errors", 0))
    if age_h > max_h * 3:
        state, reason = "FAILED", "coverage receipt is beyond three times its declared interval"
    elif age_h > max_h or errors > max_errors:
        state = "DEGRADED"
        reason = f"coverage receipt is current but reports {errors} feed error(s) (budget {max_errors})"
    else:
        state, reason = "FUNCTIONAL", "current coverage receipt within error budget"
    return base_row(
        agent,
        state=state,
        age_hours=round(age_h, 3),
        max_age_hours=max_h,
        path=str(path),
        reason=reason,
        receipt=receipt,
    )


def pid_is_alive(path: Path) -> bool | None:
    try:
        pid = int(path.read_text(encoding="utf-8").strip())
        os.kill(pid, 0)
        return True
    except PermissionError:
        # Some restricted runtimes can read a lock file but cannot inspect its PID.
        # That is an observability limit, not proof the worker is dead.
        return None
    except (FileNotFoundError, ProcessLookupError, ValueError):
        return False


def queue_worker_row(agent: dict, health: dict, now: float) -> dict:
    pid_path = Path(health["pid_artifact"])
    queue_path = Path(health["queue_artifact"])
    pause_path = Path(health["execution_pause_marker"]) if health.get("execution_pause_marker") else None
    authorization_path = (
        Path(health["execution_authorization_marker"])
        if health.get("execution_authorization_marker")
        else None
    )
    trust_root_path = (
        Path(health["authorization_trust_root"])
        if health.get("authorization_trust_root")
        else None
    )
    liveness = pid_is_alive(pid_path)
    if liveness is None:
        return base_row(
            agent,
            state="UNKNOWN",
            age_hours=age_hours(pid_path, now),
            path=str(pid_path),
            reason="worker lock exists, but this runtime cannot inspect its PID",
        )
    if not liveness:
        return base_row(
            agent,
            state="FAILED",
            age_hours=age_hours(pid_path, now),
            path=str(pid_path),
            reason="worker lock does not identify a live process",
        )
    rows: list[dict] = []
    if queue_path.exists():
        for line in queue_path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    auto_open = [
        row for row in rows
        if row.get("status") == "open"
        and (
            row.get("assign") in {"auto", "executor", "run"}
            or str(row.get("text", "")).lower().startswith(("auto:", "exec:", "/auto "))
        )
    ]
    if pause_path is not None and pause_path.exists():
        state = "PARKED"
        reason = (
            f"fail-closed execution pause is active; {len(auto_open)} auto job(s) remain unexecuted"
        )
        authorized = False
    elif authorization_path is None or not authorization_path.exists():
        state = "PARKED"
        reason = (
            "default-deny: no explicit execution authorization exists; "
            f"{len(auto_open)} auto job(s) remain unexecuted"
        )
        authorized = False
    elif trust_root_path is None or not trust_root_path.exists():
        state = "PARKED"
        reason = (
            "default-deny: authorization marker exists without an independent "
            "trust root"
        )
        authorized = False
    else:
        # I10: one shared verification function. This checker no longer runs a
        # second signature policy of its own; it asks the same code the worker
        # asks, so the two cannot disagree by having different opinions.
        try:
            sr = _load_signed_resumption()
            verdict = sr.health_state(_read_authorization_receipt(), sr.Config())
            state = verdict["state"]
            reason = "signed_resumption.health_state: %s%s" % (
                state,
                " (tamper flag set)" if verdict.get("tamper") else "",
            )
            authorized = bool(verdict.get("allow"))
        except Exception as exc:
            state = "TAMPERED"
            reason = "shared verifier unavailable or refused: %s" % exc
            authorized = False
    return base_row(
        agent,
        state=state,
        age_hours=age_hours(pid_path, now),
        path=str(pid_path),
        reason=reason,
        execution_authorized=authorized,
    )


SIGNED_RESUMPTION_MODULE = "/Users/kenielmaldonado/signed-resumption-candidate/signed_resumption.py"
SIGNED_RESUMPTION_SHA256 = "bba4c1a4513db19475bdaec95348b03247f091081bbf89935d145f0c6cf32000"
EXECUTION_AUTHORIZATION = "/Users/kenielmaldonado/km_agent/JOB_WORKER_EXECUTION_AUTHORIZED.json"


def _load_signed_resumption():
    """Same digest pin as the worker. A checker that could load a different
    module would be a second policy wearing the first one's name."""
    import hashlib
    import importlib.util
    import sys

    with open(SIGNED_RESUMPTION_MODULE, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()
    if digest != SIGNED_RESUMPTION_SHA256:
        raise RuntimeError("signed_resumption module digest mismatch: %s" % digest)
    spec = importlib.util.spec_from_file_location(
        "_signed_resumption_reviewed_checker", SIGNED_RESUMPTION_MODULE
    )
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolves sys.modules[cls.__module__] while building the frozen
    # Config. Without this registration @dataclass raises and the signed route
    # refuses on every call — fail-closed, but a gate with no open position.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _read_authorization_receipt():
    import json
    import os

    if not os.path.exists(EXECUTION_AUTHORIZATION):
        return None
    try:
        with open(EXECUTION_AUTHORIZATION, "rb") as fh:
            return json.loads(fh.read().decode("utf-8"))
    except Exception:
        return {}


def classify(agent: dict, now: float) -> dict:
    health = agent.get("health", {})
    mode = health.get("mode", "artifact")
    if mode == "parked":
        marker = Path(health["marker"])
        state = "PARKED" if marker.exists() else "UNKNOWN"
        reason = "declared recovery gate is present" if marker.exists() else "declared park marker is absent"
        return base_row(agent, state=state, age_hours=age_hours(marker, now), path=str(marker), reason=reason)
    if mode == "recovery_gate":
        marker = Path(health["marker"])
        if marker.exists():
            return base_row(
                agent,
                state="PARKED",
                age_hours=age_hours(marker, now),
                path=str(marker),
                reason="declared recovery gate is present",
            )
        return base_row(
            agent,
            state="UNKNOWN",
            age_hours=age_hours(Path(agent["artifact"]), now),
            path=str(agent["artifact"]),
            reason="recovery gate was cleared, but no current functional receipt has been recorded",
        )
    if mode == "recovery_listener":
        return recovery_listener_row(agent, health, now)
    if mode == "event_listener":
        return event_listener_row(agent, health, now)
    if mode == "jsonl_heartbeat":
        return jsonl_heartbeat_row(agent, health, now)
    if mode == "coverage_jsonl":
        return coverage_row(agent, health, now)
    if mode == "queue_worker":
        return queue_worker_row(agent, health, now)
    return artifact_row(agent, now)


def launchagent_inventory(data: dict) -> dict:
    discovered: set[str] = set()
    for path in LAUNCH_AGENTS_DIR.glob("com.keniel.*.plist"):
        try:
            with path.open("rb") as handle:
                value = plistlib.load(handle)
        except (OSError, plistlib.InvalidFileException):
            continue
        label = value.get("Label")
        if isinstance(label, str):
            discovered.add(label)
    declared = {
        str(agent.get("label"))
        for agent in data.get("agents", [])
        if str(agent.get("label", "")).startswith("com.keniel.")
    }
    declared.update(
        str(component.get("label"))
        for component in data.get("scheduled_components", [])
        if str(component.get("label", "")).startswith("com.keniel.")
    )
    return {
        "discovered_count": len(discovered),
        "declared_count": len(discovered & declared),
        "unclassified": sorted(discovered - declared),
        "declared_without_plist": sorted(declared - discovered),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    data = json.loads(LEDGER.read_text())
    now = time.time()
    rows = [classify(a, now) for a in data["agents"]]
    inventory = launchagent_inventory(data)
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["state"]] = counts.get(r["state"], 0) + 1

    if args.json:
        print(json.dumps({"counts": counts, "inventory": inventory, "rows": rows}, indent=2))
        if any(counts.get(state, 0) for state in FAILED_STATES):
            return 1
        return 2 if inventory["unclassified"] else 0

    print("=" * 72)
    print("AGENT USEFULNESS CHECK — purpose evidence, not PID theater")
    print("=" * 72)
    print(f"ledger: {LEDGER}")
    print(f"law:    {data.get('law', '')}")
    print()
    for r in sorted(rows, key=lambda x: (x["state"], x["id"])):
        age = f"{r['age_hours']}h" if r["age_hours"] is not None else "n/a"
        print(f"  {r['state']:<11} {r['id']:<18} age={age:<10} max={r.get('max_age_hours', '-')}h")
        print(f"           reason: {r['reason']}")
        if r.get("note"):
            print(f"           note: {r['note'][:90]}")
    print()
    print(f"  counts: {counts}")
    print(
        "  LaunchAgent inventory: "
        f"{inventory['declared_count']}/{inventory['discovered_count']} classified"
    )
    if inventory["unclassified"]:
        print(f"  unclassified: {', '.join(inventory['unclassified'])}")
    print()
    if any(counts.get(state, 0) for state in FAILED_STATES):
        print("  VERDICT: USEFULNESS FAIL — at least one agent is FAILED or UNKNOWN.")
        print("  Next: repair, or explicitly park it with purpose — do not add new reach.")
        return 1
    if inventory["unclassified"] or any(counts.get(state, 0) for state in DEGRADED_STATES):
        print("  VERDICT: DEGRADED — runtime inventory or agent evidence is incomplete before new reach.")
        return 2
    print("  VERDICT: declared agents are either functional, ready, safely idle, or intentionally parked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
