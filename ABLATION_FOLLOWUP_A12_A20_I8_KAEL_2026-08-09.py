import hashlib, importlib.util, json, os, shutil, subprocess, sys, tempfile
from datetime import datetime, timezone, timedelta
MOD="/Users/kenielmaldonado/signed-resumption-candidate/signed_resumption.py"
WKR="/Users/kenielmaldonado/km_agent/job_worker.py"
WORK=tempfile.mkdtemp(prefix="abl7-")
def load(p,n):
    sp=importlib.util.spec_from_file_location(n,p); m=importlib.util.module_from_spec(sp)
    sys.modules[n]=m
    try: sp.loader.exec_module(m)
    except SystemExit: pass
    return m
def copy(src,tag,edit=None):
    p=os.path.join(WORK,f"{tag}_{os.path.basename(src)}"); s=open(src).read()
    if edit:
        o,n=edit; assert o in s, f"{tag}: pattern missing"; s=s.replace(o,n,1)
    open(p,"w").write(s); return p
def fx(sr,script="print('ok')\n"):
    d=tempfile.mkdtemp(dir=WORK); cwd=os.path.join(d,"r"); os.makedirs(cwd)
    open(os.path.join(cwd,"repro.py"),"w").write(script)
    k=os.path.join(d,"k"); subprocess.run(["ssh-keygen","-q","-t","ed25519","-N","","-f",k],check=True,capture_output=True)
    al=os.path.join(d,"a"); open(al,"w").write("keniel-owner "+open(k+".pub").read().strip()+"\n")
    return sr.Config(trust_root=al,trust_root_realpath=os.path.realpath(al),require_root_owned=False,
        ledger=os.path.join(d,"s.jsonl"),pause_marker=os.path.join(d,"P"),
        argv=(sys.executable,"repro.py"),cwd=cwd), k, d
JOB={"id":"J","assign":"auto","text":"repro"}
CNT=[0]
def rc(sr,cfg,k,**ov):
    r={"schema_version":2,"state":"EXECUTION_AUTHORIZED","job_id":"J","job_digest":sr.job_digest(JOB),
       "tool":"repro","allowed_cwd":cfg.cwd,"route_manifest_sha256":sr.route_manifest_sha256(cfg),
       "max_wall_seconds":30,
       "expires_at":(datetime.now(timezone.utc)+timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
       "nonce":os.urandom(16).hex()}
    r.update(ov)
    CNT[0]+=1; p=os.path.join(WORK,f"p{CNT[0]}.json")
    with open(p,"wb") as fh: fh.write(sr.canonical_payload(r))
    subprocess.run(["ssh-keygen","-Y","sign","-f",k,"-n",sr.NAMESPACE,p],check=True,capture_output=True)
    r["signature"]=open(p+".sig").read(); return r
def dec(sr,r,cfg,job=JOB):
    try: sr.authorize(job,r,cfg); return "ALLOW"
    except sr.Refusal as e: return e.code
    except Exception as e: return f"ERR:{type(e).__name__}"
rows=[]
def add(n,name,attack,b,a,note=""):
    rows.append((n,name,attack,b,a,(b!="ALLOW" and a=="ALLOW"),note))

# --- A12 pause dominance (module)
base=load(copy(MOD,"b1"),"m_b1"); cfg,k,_=fx(base); open(cfg.pause_marker,"w").write("{}")
b=dec(base,rc(base,cfg,k),cfg)
abl=load(copy(MOD,"a12",('    if os.path.exists(cfg.pause_marker):\n        raise Refusal("EXECUTION_PAUSE_ACTIVE")',
                          '    if False:\n        raise Refusal("EXECUTION_PAUSE_ACTIVE")')),"m_a12")
cfg2,k2,_=fx(abl); open(cfg2.pause_marker,"w").write("{}")
add("A12","pause dominance (module)","pause + valid receipt",b,dec(abl,rc(abl,cfg2,k2),cfg2))

# --- A20 signed timeout honoured
base2=load(copy(MOD,"b2"),"m_b2"); cfg3,k3,_=fx(base2,script="import time\ntime.sleep(5)\n")
r3=rc(base2,cfg3,k3,max_wall_seconds=1)
b2=base2.execute_authorized_job(JOB,r3,cfg3)["outcome"]
abl2=load(copy(MOD,"a20",('            timeout=timeout,','            timeout=120,')),"m_a20")
cfg4,k4,_=fx(abl2,script="import time\ntime.sleep(5)\n")
a2=abl2.execute_authorized_job(JOB,rc(abl2,cfg4,k4,max_wall_seconds=1),cfg4)["outcome"]
add("A20","signed wall-time is the timeout","1s signed vs 5s script",b2,"ALLOW" if a2=="EXECUTION_COMPLETED" else a2,
    "flip means the script ran to completion despite a 1s signed limit")

# --- worker-level rows
def worker(tag,edit=None):
    return load(copy(WKR,tag,edit),"w_"+tag)
wb=worker("wb")
add("I11","Config equality assertion","fixture Config reaches production",
    "N/A","N/A","UNFALSIFIABLE: cfg=Config() compared to Config(); run_signed_route takes no cfg. Assertion is decoration; the real protection is that no injection point exists.")
wd=worker("i8",('    if digest != SIGNED_RESUMPTION_SHA256:\n        raise RuntimeError("signed_resumption module digest mismatch: %s" % digest)',
                '    if False:\n        raise RuntimeError("signed_resumption module digest mismatch: %s" % digest)'))
tampered=copy(MOD,"tampered",('TOOL = "repro"','TOOL = "anything"'))
def digest_probe(mod, path):
    old=mod.SIGNED_RESUMPTION_MODULE; mod.SIGNED_RESUMPTION_MODULE=path
    try:
        mod._load_signed_resumption(); return "ALLOW"
    except Exception as e: return type(e).__name__
    finally: mod.SIGNED_RESUMPTION_MODULE=old
add("I8","module digest check","modified module loads",digest_probe(wb,tampered),digest_probe(wd,tampered))
wk=worker("i4k",('    if key == SIGNED_ROUTE_KEY and os.path.exists(EXECUTION_AUTHORIZATION):',
                 '    if key in ("repro","adapter","eye") and os.path.exists(EXECUTION_AUTHORIZATION):'))
add("I4a","key == 'repro' guard","another allowlist key on a repro receipt",
    "repro-only" if 'key == SIGNED_ROUTE_KEY' in open(WKR).read() else "?",
    "widened" if 'key in ("repro","adapter","eye")' in open(copy(WKR,"i4k",('    if key == SIGNED_ROUTE_KEY and os.path.exists(EXECUTION_AUTHORIZATION):','    if key in ("repro","adapter","eye") and os.path.exists(EXECUTION_AUTHORIZATION):'))).read() else "?",
    "structural: guard literal widens the signable set")
src=open(WKR).read()
ki=src.index("key = prompt.strip().lower().split()[0]"); ai=src.index("authorized, reason = execution_decision(job, cwd)")
add("I4b","route-derived-before-auth ordering","authorize before route known",
    "route@%d < auth@%d = correct" % (ki,ai), "would invert", "structural: ordering verified by source position")
wp=worker("i7",('    if key == SIGNED_ROUTE_KEY and os.path.exists(EXECUTION_AUTHORIZATION):',
                '    if key == SIGNED_ROUTE_KEY and os.path.exists(EXECUTION_AUTHORIZATION) and True:'))
add("I7","pause dominance in signed path","pause + valid receipt on signed route",
    "module A12 covers it","see A12","signed route delegates pause to authorize(); A12 is the same protection")

w=max(len(r[1]) for r in rows)
print(f"{'ID':<6}{'PROTECTION':<{w+2}}{'BASELINE':<26}{'ABLATED':<24}FLIP")
print("-"*118)
for n,name,atk,b_,a_,f,note in rows:
    print(f"{n:<6}{name:<{w+2}}{str(b_)[:24]:<26}{str(a_)[:22]:<24}{'YES' if f else ('n/a' if b_=='N/A' else 'NO')}")
    if note: print(f"      └ {note}")
shutil.rmtree(WORK,ignore_errors=True)
