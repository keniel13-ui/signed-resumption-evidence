#!/usr/bin/env python3
"""Ablation harness. Maker-run (Ka'el) => stage-1 evidence only; a breaker must re-run.

Each row removes exactly one protection from a COPY of the reviewed module and
requires the paired attack to FLIP from BLOCK to ALLOW. A protection whose
removal changes nothing is decoration and comes out of the claim.
"""
import importlib.util, itertools, json, os, shutil, subprocess, sys, tempfile, threading
from datetime import datetime, timezone, timedelta

SRC = "/Users/kenielmaldonado/signed-resumption-candidate/signed_resumption.py"
WORK = tempfile.mkdtemp(prefix="ablation-")
CTR = itertools.count()

def load(path, name):
    sp = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(sp); sys.modules[name] = m; sp.loader.exec_module(m)
    return m

def make_module(tag, edit=None):
    p = os.path.join(WORK, f"sr_{tag}.py")
    s = open(SRC).read()
    if edit:
        old, new = edit
        assert old in s, f"ablation pattern missing for {tag}"
        s = s.replace(old, new, 1)
    open(p, "w").write(s)
    return load(p, f"sr_{tag}")

def fixture(sr, *, root_owned=False, trust_realpath=None, script="print('ok')\n"):
    d = tempfile.mkdtemp(dir=WORK); cwd = os.path.join(d, "route"); os.makedirs(cwd)
    open(os.path.join(cwd, "repro.py"), "w").write(script)
    key = os.path.join(d, "k")
    subprocess.run(["ssh-keygen","-q","-t","ed25519","-N","","-f",key], check=True, capture_output=True)
    wrong = os.path.join(d, "w")
    subprocess.run(["ssh-keygen","-q","-t","ed25519","-N","","-f",wrong], check=True, capture_output=True)
    allowed = os.path.join(d, "allowed_signers")
    open(allowed,"w").write("keniel-owner " + open(key+".pub").read().strip() + "\n")
    cfg = sr.Config(trust_root=allowed,
                    trust_root_realpath=trust_realpath or os.path.realpath(allowed),
                    require_root_owned=root_owned,
                    ledger=os.path.join(d,"spent.jsonl"),
                    pause_marker=os.path.join(d,"PAUSE"),
                    argv=(sys.executable,"repro.py"), cwd=cwd)
    return cfg, key, wrong, cwd

def sign(sr, r, key):
    p = os.path.join(WORK, f"pl{next(CTR)}.json")
    with open(p,"wb") as fh: fh.write(sr.canonical_payload(r))
    subprocess.run(["ssh-keygen","-Y","sign","-f",key,"-n",sr.NAMESPACE,p], check=True, capture_output=True)
    return open(p+".sig").read()

def receipt(sr, cfg, key, job, **over):
    r = {"schema_version":2,"state":"EXECUTION_AUTHORIZED","job_id":job["id"],
         "job_digest":sr.job_digest(job),"tool":"repro","allowed_cwd":cfg.cwd,
         "route_manifest_sha256":sr.route_manifest_sha256(cfg),"max_wall_seconds":30,
         "expires_at":(datetime.now(timezone.utc)+timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
         "nonce":os.urandom(16).hex()}
    r.update(over)
    r["signature"] = sign(sr, r, key)
    return r

def decide(sr, job, r, cfg):
    try:
        sr.authorize(job, r, cfg); return "ALLOW"
    except sr.Refusal as e: return e.code
    except Exception as e: return f"ERR:{type(e).__name__}"

JOB = {"id":"J","assign":"auto","text":"repro"}
rows = []
def row(name, attack, baseline, ablated):
    flipped = baseline != "ALLOW" and ablated == "ALLOW"
    rows.append((name, attack, baseline, ablated, flipped))

# ---------- 1. signature verification -> A3 (wrong key)
base = make_module("base")
cfg,k,wrong,_ = fixture(base)
r = receipt(base,cfg,wrong,JOB)                     # signed by a key NOT in allowed_signers
b = decide(base,JOB,r,cfg)
abl = make_module("nosig", ('        if proc.returncode != 0:\n            raise Refusal("SIGNATURE_INVALID")',
                            '        if False:\n            raise Refusal("SIGNATURE_INVALID")'))
cfg2,k2,wrong2,_ = fixture(abl)
r2 = receipt(abl,cfg2,wrong2,JOB)
row("signature verification","A3 wrong key",b,decide(abl,JOB,r2,cfg2))

# ---------- 2. trust-root custody -> A11 (relocated/user-writable trust root)
base2 = make_module("base2")
cfgA,kA,_,_ = fixture(base2, trust_realpath="/private/etc/keniel-agent/owner_execution_allowed_signers")
rA = receipt(base2,cfgA,kA,JOB)
bA = decide(base2,JOB,rA,cfgA)
abl2 = make_module("nocustody", ('    real = os.path.realpath(cfg.trust_root)\n    if real != cfg.trust_root_realpath:\n        raise Refusal("TRUST_ROOT_PATH_UNEXPECTED")',
                                 '    real = os.path.realpath(cfg.trust_root)\n    if False:\n        raise Refusal("TRUST_ROOT_PATH_UNEXPECTED")'))
cfgB,kB,_,_ = fixture(abl2, trust_realpath="/private/etc/keniel-agent/owner_execution_allowed_signers")
rB = receipt(abl2,cfgB,kB,JOB)
row("trust-root custody","A11 relocated trust root",bA,decide(abl2,JOB,rB,cfgB))

# ---------- 3. job-digest binding -> A4 (changed job body)
base3 = make_module("base3"); cfgC,kC,_,_ = fixture(base3)
rC = receipt(base3,cfgC,kC,JOB); altered = dict(JOB, text="rm -rf /")
bC = decide(base3,JOB and altered,rC,cfgC)
abl3 = make_module("nodigest", ('    if receipt["job_digest"] != job_digest(job):\n        raise Refusal("RECEIPT_NOT_BOUND_TO_THIS_JOB_CONTENT")',
                                '    if False:\n        raise Refusal("RECEIPT_NOT_BOUND_TO_THIS_JOB_CONTENT")'))
cfgD,kD,_,_ = fixture(abl3); rD = receipt(abl3,cfgD,kD,JOB)
row("job-digest binding","A4 changed job body",bC,decide(abl3,dict(JOB,text="rm -rf /"),rD,cfgD))

# ---------- 4. cwd binding -> A5
base4 = make_module("base4"); cfgE,kE,_,_ = fixture(base4)
rE = receipt(base4,cfgE,kE,JOB, allowed_cwd="/tmp")
bE = decide(base4,JOB,rE,cfgE)
abl4 = make_module("nocwd", ('    if os.path.realpath(receipt["allowed_cwd"]) != os.path.realpath(cfg.cwd):\n        raise Refusal("ALLOWED_CWD_MISMATCH")',
                             '    if False:\n        raise Refusal("ALLOWED_CWD_MISMATCH")'))
cfgF,kF,_,_ = fixture(abl4); rF = receipt(abl4,cfgF,kF,JOB, allowed_cwd="/tmp")
row("cwd binding","A5 wrong allowed_cwd",bE,decide(abl4,JOB,rF,cfgF))

# ---------- 5. tool binding -> A6
base5 = make_module("base5"); cfgG,kG,_,_ = fixture(base5)
rG = receipt(base5,cfgG,kG,JOB, tool="eye")
bG = decide(base5,JOB,rG,cfgG)
abl5 = make_module("notool", ('    if receipt["tool"] != TOOL:\n        raise Refusal("TOOL_NOT_ON_THE_SIGNED_ROUTE")',
                              '    if False:\n        raise Refusal("TOOL_NOT_ON_THE_SIGNED_ROUTE")'))
cfgH,kH,_,_ = fixture(abl5); rH = receipt(abl5,cfgH,kH,JOB, tool="eye")
row("tool binding","A6 different allowlist key",bG,decide(abl5,JOB,rH,cfgH))

# ---------- 6. script_sha256 in route manifest -> A18 (script bytes changed)
base6 = make_module("base6"); cfgI,kI,_,cwdI = fixture(base6)
rI = receipt(base6,cfgI,kI,JOB)
open(os.path.join(cwdI,"repro.py"),"w").write("print('TAMPERED')\n")
bI = decide(base6,JOB,rI,cfgI)
abl6 = make_module("noscripthash", ('        "script_sha256": sha256_file(script),', '        "script_sha256": "removed",'))
cfgJ,kJ,_,cwdJ = fixture(abl6); rJ = receipt(abl6,cfgJ,kJ,JOB)
open(os.path.join(cwdJ,"repro.py"),"w").write("print('TAMPERED')\n")
row("script_sha256 binding","A18 script bytes swapped",bI,decide(abl6,JOB,rJ,cfgJ))

# ---------- 7a. N1 remove nonce check+spend -> P2 replay
base7 = make_module("base7"); cfgK,kK,_,_ = fixture(base7)
rK = receipt(base7,cfgK,kK,JOB); decide(base7,JOB,rK,cfgK)
bK = decide(base7,JOB,rK,cfgK)                       # second use
abl7 = make_module("nononce", ('    check_and_spend_nonce(receipt["nonce"], receipt["job_id"], cfg)',
                               '    pass  # nonce check and spend removed'))
cfgL,kL,_,_ = fixture(abl7); rL = receipt(abl7,cfgL,kL,JOB); decide(abl7,JOB,rL,cfgL)
row("nonce check+spend (N1)","P2 sequential replay",bK,decide(abl7,JOB,rL,cfgL))

# ---------- 8. expiry check -> A9
base8 = make_module("base8"); cfgM,kM,_,_ = fixture(base8)
past = (datetime.now(timezone.utc)-timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
rM = receipt(base8,cfgM,kM,JOB, expires_at=past)
bM = decide(base8,JOB,rM,cfgM)
abl8 = make_module("noexpiry", ('    if not not_expired(receipt, now):\n        raise Refusal("RECEIPT_EXPIRED")',
                                '    if False:\n        raise Refusal("RECEIPT_EXPIRED")'))
cfgN,kN,_,_ = fixture(abl8); rN = receipt(abl8,cfgN,kN,JOB, expires_at=past)
row("expiry check","A9 expired receipt",bM,decide(abl8,JOB,rN,cfgN))

print(f"{'PROTECTION REMOVED':<26} {'PAIRED ATTACK':<28} {'BASELINE':<34} {'ABLATED':<10} FLIP")
print("-"*112)
ok=0
for n,a,b_,ab,f in rows:
    print(f"{n:<26} {a:<28} {b_:<34} {ab:<10} {'YES' if f else 'NO'}")
    ok += f
print("-"*112)
print(f"{ok}/{len(rows)} ablations flipped")
shutil.rmtree(WORK, ignore_errors=True)
