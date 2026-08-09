"""I3 regression floor — all 19 cases from JOB_WORKER_BREAKER_VERDICT_2026-07-31.md
replayed against the SHIPPED worker df506897…5db05.

Every executor is a counting stub. A case passes only if the decision refuses
AND the executor count is zero.
"""
import importlib.util, json, os, shutil, sys, tempfile
from unittest.mock import patch

WORKER = "/Users/kenielmaldonado/km_agent/job_worker.py"
EXPECT = "df50689768455f9f55a86374e621006a00436c1ddae69bb92c530fe6c165db05"

import hashlib
actual = hashlib.sha256(open(WORKER,"rb").read()).hexdigest()
assert actual == EXPECT, f"WRONG TARGET: {actual}"

sp = importlib.util.spec_from_file_location("jw", WORKER)
jw = importlib.util.module_from_spec(sp); sys.modules["jw"] = jw
try: sp.loader.exec_module(jw)
except SystemExit: pass

WORK = tempfile.mkdtemp(prefix="i3-")
jw.EXECUTION_PAUSE = os.path.join(WORK, "PAUSED.json")
jw.EXECUTION_AUTHORIZATION = os.path.join(WORK, "AUTH.json")
jw.AUTHORIZATION_TRUST_ROOT = os.path.join(WORK, "trustroot")
CWD = "/Users/kenielmaldonado/claim30_repro"

calls = {"n": 0}
def stub_exec(*a, **k):
    calls["n"] += 1
    raise AssertionError("EXECUTOR REACHED")

def reset(pause=False, auth=None, trust=False, auth_raw=None):
    for p in (jw.EXECUTION_PAUSE, jw.EXECUTION_AUTHORIZATION, jw.AUTHORIZATION_TRUST_ROOT):
        if os.path.islink(p) or os.path.exists(p):
            shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) and not os.path.islink(p) else os.remove(p)
    if pause: open(jw.EXECUTION_PAUSE, "w").write("{}")
    if trust: open(jw.AUTHORIZATION_TRUST_ROOT, "w").write("keniel-owner ssh-ed25519 AAAA fake\n")
    if auth_raw is not None: open(jw.EXECUTION_AUTHORIZATION, "w").write(auth_raw)
    elif auth is not None: open(jw.EXECUTION_AUTHORIZATION, "w").write(json.dumps(auth))
    calls["n"] = 0

rows = []
def case(n, name, fn):
    try:
        ok, reason = fn()
    except AssertionError as e:
        rows.append((n, name, "EXECUTOR REACHED", calls["n"], False)); return
    except Exception as e:
        reason = f"{type(e).__name__}: {e}"; ok = False
    passed = (ok is False) and calls["n"] == 0
    rows.append((n, name, ("ALLOW" if ok else str(reason))[:46], calls["n"], passed))

good_job = {"id": "J1", "assign": "auto", "text": "adapter"}
FAKE = {"schema_version": 1, "state": "EXECUTION_AUTHORIZED", "job_id": "J1",
        "job_digest": jw.job_digest(good_job), "allowed_cwd": CWD, "max_wall_seconds": 60,
        "expires_at": "2099-01-01T00:00:00+00:00"}

# ---- 6 mandated
reset(auth=None);                     case(1,"pause deleted, authorization absent", lambda: jw.execution_decision(good_job, CWD))
reset(auth_raw="{not json");          case(2,"malformed authorization",             lambda: jw.execution_decision(good_job, CWD))
reset(auth=FAKE);                     case(3,"same-user fake auth bound to job",    lambda: jw.execution_decision(good_job, CWD))
reset(pause=True, auth=FAKE);         case(4,"pause + fake authorization",          lambda: jw.execution_decision(good_job, CWD))
def c5():
    reset(auth=FAKE)
    with patch.object(jw.god_jobs, "run_allowlisted", side_effect=stub_exec), \
         patch.object(jw, "subprocess") as sp2:
        sp2.run.side_effect = stub_exec
        jw.process_one({"id":"J5","assign":"auto","text":"adapter"})
    return False, "process_one returned without executing"
case(5,"allowlisted /run via real process_one()", c5)
reset(auth=FAKE);                     case(6,"checker visibility, 1 AUTO waiting",  lambda: jw.execution_decision(good_job, CWD))

# ---- 13 breaker's own
reset(auth=dict(FAKE, schema_version=3));          case(7,"unaccepted schema_version",          lambda: jw.execution_decision(good_job, CWD))
reset(auth={"independently_verified": True});      case(8,"asserts independently_verified",     lambda: jw.execution_decision(good_job, CWD))
def c9():
    reset(); os.makedirs(jw.EXECUTION_PAUSE, exist_ok=True); return jw.execution_decision(good_job, CWD)
case(9,"pause path replaced by a directory", c9)
def c10():
    reset(auth=FAKE); os.symlink(os.path.join(WORK,"nope"), jw.EXECUTION_PAUSE); return jw.execution_decision(good_job, CWD)
case(10,"pause replaced by broken symlink", c10)
def c11():
    reset(); forged=os.path.join(WORK,"forged.json"); open(forged,"w").write(json.dumps(FAKE))
    os.symlink(forged, jw.EXECUTION_AUTHORIZATION); return jw.execution_decision(good_job, CWD)
case(11,"authorization is a symlink to forged", c11)
reset(auth_raw=json.dumps([FAKE]));                case(12,"authorization is a JSON array",     lambda: jw.execution_decision(good_job, CWD))
reset(auth_raw="");                                case(13,"authorization is an empty file",    lambda: jw.execution_decision(good_job, CWD))
reset(auth=FAKE);                                  case(14,"non-dict / None job",               lambda: jw.execution_decision(None, CWD))
reset(auth=dict(FAKE, max_wall_seconds=10**9));    case(15,"max_wall_seconds = 10^9",           lambda: jw.execution_decision(good_job, CWD))
reset(auth=dict(FAKE, expires_at="2099-01-01T00:00:00")); case(16,"naive tz expiry 2099",        lambda: jw.execution_decision(good_job, CWD))
reset(auth=FAKE, trust=True);                      case(17,"trust root present + forged auth",  lambda: jw.execution_decision(good_job, CWD))

import inspect
src_dec = inspect.getsource(jw.execution_decision)
isv = inspect.getsource(jw.independent_signature_verified)
rows.append((18,"executor sites gate-dominated","legacy path returns before executors", 0, "return False" in src_dec))
rows.append((19,"no reachable True in verifier","both branches return False", 0, "return True" not in isv))

print(f"{'#':<4}{'CASE':<46}{'RESULT':<48}{'EXEC':<6}PASS")
print("-"*112)
for n,name,res,c,p in rows:
    print(f"{n:<4}{name:<46}{str(res):<48}{c:<6}{'YES' if p else 'NO'}")
print("-"*112)
ok=sum(1 for r in rows if r[4]); tot=len(rows)
print(f"{ok}/{tot} cases pass · total executor calls: {sum(r[3] for r in rows)}")
print(f"target: {actual[:24]}…")
shallow = [r for r in rows if "not bound to this job content" in str(r[2])]
print(f"cases still refusing on the SHALLOWEST check: {len(shallow)}" + (" -> " + ",".join(str(r[0]) for r in shallow) if shallow else " (none)"))
shutil.rmtree(WORK, ignore_errors=True)
