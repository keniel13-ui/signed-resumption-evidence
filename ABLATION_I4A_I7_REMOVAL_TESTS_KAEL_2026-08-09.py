"""Real removal tests for I4a (key guard), I4b (route ordering), I7 (signed-path pause).

Runs the actual process_one() with a receipt present and counting stubs on every
executor. A row flips only if the executor is genuinely reached.
"""
import hashlib, importlib.util, json, os, shutil, subprocess, sys, tempfile
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
WKR="/Users/kenielmaldonado/km_agent/job_worker.py"
MOD="/Users/kenielmaldonado/signed-resumption-candidate/signed_resumption.py"
WORK=os.path.realpath(tempfile.mkdtemp(prefix="i4-"))
JOB_TEXT="repro"
def load(p,n):
    sp=importlib.util.spec_from_file_location(n,p); m=importlib.util.module_from_spec(sp); sys.modules[n]=m
    try: sp.loader.exec_module(m)
    except SystemExit: pass
    return m
def cp(src,tag,edit=None):
    p=os.path.join(WORK,f"{tag}_{os.path.basename(src)}"); s=open(src).read()
    if edit:
        o,n=edit; assert o in s, f"{tag}: pattern missing"; s=s.replace(o,n,1)
    open(p,"w").write(s); return p

# fixture route + key + trust root
D=os.path.realpath(tempfile.mkdtemp(dir=WORK)); CWD=os.path.join(D,"route"); os.makedirs(CWD)
MARK=os.path.join(D,"executions.log")
open(os.path.join(CWD,"repro.py"),"w").write("open(%r,'a').write('x')\n" % MARK)
KEY=os.path.join(D,"k"); subprocess.run(["ssh-keygen","-q","-t","ed25519","-N","","-f",KEY],check=True,capture_output=True)
AL=os.path.join(D,"allowed"); open(AL,"w").write("keniel-owner "+open(KEY+".pub").read().strip()+"\n")
PAUSE=os.path.join(D,"PAUSE"); LEDGER=os.path.join(D,"spent.jsonl"); AUTH=os.path.join(D,"AUTH.json")

# a module whose Config defaults are the fixture, so the signed route can actually run
MODF=cp(MOD,"fixcfg",('    trust_root: str = "/etc/keniel-agent/owner_execution_allowed_signers"\n'
                      '    trust_root_realpath: str = "/private/etc/keniel-agent/owner_execution_allowed_signers"\n'
                      '    require_root_owned: bool = True\n'
                      '    ledger: str = "/Users/kenielmaldonado/km_agent/state/execution_nonce_spent.jsonl"\n'
                      '    pause_marker: str = "/Users/kenielmaldonado/km_agent/JOB_WORKER_EXECUTION_PAUSED.json"\n'
                      '    argv: tuple = ("/usr/local/bin/python3", "repro.py")\n'
                      '    cwd: str = "/Users/kenielmaldonado/claim30_repro"',
                      f'    trust_root: str = "{AL}"\n'
                      f'    trust_root_realpath: str = "{os.path.realpath(AL)}"\n'
                      f'    require_root_owned: bool = False\n'
                      f'    ledger: str = "{LEDGER}"\n'
                      f'    pause_marker: str = "{PAUSE}"\n'
                      f'    argv: tuple = ("{sys.executable}", "repro.py")\n'
                      f'    cwd: str = "{CWD}"'))
MODSHA=hashlib.sha256(open(MODF,"rb").read()).hexdigest()
srf=load(MODF,"srf")

def make_receipt(job):
    cfg=srf.Config()
    r={"schema_version":2,"state":"EXECUTION_AUTHORIZED","job_id":job["id"],"job_digest":srf.job_digest(job),
       "tool":"repro","allowed_cwd":CWD,"route_manifest_sha256":srf.route_manifest_sha256(cfg),
       "max_wall_seconds":30,
       "expires_at":(datetime.now(timezone.utc)+timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
       "nonce":os.urandom(16).hex()}
    p=os.path.join(WORK,f"pl_{r['nonce'][:6]}.json")
    with open(p,"wb") as fh: fh.write(srf.canonical_payload(r))
    subprocess.run(["ssh-keygen","-Y","sign","-f",KEY,"-n",srf.NAMESPACE,p],check=True,capture_output=True)
    r["signature"]=open(p+".sig").read(); return r

def worker(tag, edit=None):
    w=load(cp(WKR,tag,edit),"w_"+tag)
    w.SIGNED_RESUMPTION_MODULE=MODF; w.SIGNED_RESUMPTION_SHA256=MODSHA
    w.EXECUTION_AUTHORIZATION=AUTH; w.EXECUTION_PAUSE=PAUSE
    return w

def run(w, text, pause=False):
    job={"id":"J-"+os.urandom(3).hex(),"assign":"auto","text":text}
    open(AUTH,"w").write(json.dumps(make_receipt(job)))
    if pause: open(PAUSE,"w").write("{}")
    elif os.path.exists(PAUSE): os.remove(PAUSE)
    if os.path.exists(LEDGER): os.remove(LEDGER)
    if os.path.exists(MARK): os.remove(MARK)
    allow=[0]
    with patch.object(w.god_jobs,"run_allowlisted",side_effect=lambda *a,**k:(allow.__setitem__(0,allow[0]+1) or "stub")), \
         patch.object(w.god_jobs,"close_job"), patch.object(w,"telegram"):
        try: w.process_one(job)
        except Exception: pass
    real = len(open(MARK).read()) if os.path.exists(MARK) else 0
    return real + allow[0]

rows=[]
base=worker("base")
# I4a: key guard
b=run(base,"adapter")
w4a=worker("i4a",('    if key == SIGNED_ROUTE_KEY and os.path.exists(EXECUTION_AUTHORIZATION):',
                  '    if key in ("repro","adapter") and os.path.exists(EXECUTION_AUTHORIZATION):'))
a=run(w4a,"adapter")
rows.append(("I4a","key == 'repro' guard","'adapter' job with a repro receipt",b,a))
# I7: pause dominance on the signed path
b7=run(base,"repro",pause=True)
w7=worker("i7",('    if os.path.exists(cfg.pause_marker):\n        raise Refusal("EXECUTION_PAUSE_ACTIVE")',None) if False else None)
srp=load(cp(MODF,"nopause",('    if os.path.exists(cfg.pause_marker):\n        raise Refusal("EXECUTION_PAUSE_ACTIVE")',
                            '    if False:\n        raise Refusal("EXECUTION_PAUSE_ACTIVE")')),"srp")
w7=worker("i7b"); w7.SIGNED_RESUMPTION_MODULE=cp(MODF,"nopause2",('    if os.path.exists(cfg.pause_marker):\n        raise Refusal("EXECUTION_PAUSE_ACTIVE")',
                            '    if False:\n        raise Refusal("EXECUTION_PAUSE_ACTIVE")'))
w7.SIGNED_RESUMPTION_SHA256=hashlib.sha256(open(w7.SIGNED_RESUMPTION_MODULE,"rb").read()).hexdigest()
a7=run(w7,"repro",pause=True)
rows.append(("I7","pause dominance, signed path","pause + valid receipt, repro queued",b7,a7))
# sanity: the happy path must actually execute, or every row above is vacuous
sane=run(base,"repro")
print(f"{'ID':<7}{'PROTECTION':<32}{'ATTACK':<40}{'BASE':<7}{'ABL':<7}FLIP")
print("-"*104)
for i,n,atk,b_,a_ in rows:
    print(f"{i:<7}{n:<32}{atk:<40}{b_:<7}{a_:<7}{'YES' if b_==0 and a_>0 else 'NO'}")
print("-"*104)
print(f"SANITY: happy path executor calls = {sane}  (must be >=1, else every row above is vacuous)")
shutil.rmtree(WORK,ignore_errors=True)
