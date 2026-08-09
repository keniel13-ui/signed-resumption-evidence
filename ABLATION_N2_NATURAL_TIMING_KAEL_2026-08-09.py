import importlib.util, os, shutil, subprocess, sys, tempfile, time
from datetime import datetime, timezone, timedelta
from multiprocessing import Process, Value
SRC="/Users/kenielmaldonado/signed-resumption-candidate/signed_resumption.py"
JOB={"id":"J","assign":"auto","text":"repro"}
def load(p,n):
    sp=importlib.util.spec_from_file_location(n,p); m=importlib.util.module_from_spec(sp)
    sys.modules[n]=m; sp.loader.exec_module(m); return m
def worker(path,cfgargs,r,start,counter):
    sr=load(path,"srw")
    cfg=sr.Config(**cfgargs)
    while time.time()<start: pass
    try:
        sr.authorize(JOB,r,cfg)
        with counter.get_lock(): counter.value+=1
    except Exception: pass
def main():
    WORK=tempfile.mkdtemp(prefix="n2-")
    def mk(tag,edit=None):
        p=os.path.join(WORK,f"sr_{tag}.py"); s=open(SRC).read()
        if edit:
            o,n=edit; assert o in s; s=s.replace(o,n,1)
        open(p,"w").write(s); return p
    def build(path,tag):
        d=tempfile.mkdtemp(dir=WORK); sr=load(path,tag)
        cwd=os.path.join(d,"r"); os.makedirs(cwd)
        open(os.path.join(cwd,"repro.py"),"w").write("print('ok')\n")
        k=os.path.join(d,"k"); subprocess.run(["ssh-keygen","-q","-t","ed25519","-N","","-f",k],check=True,capture_output=True)
        al=os.path.join(d,"a"); open(al,"w").write("keniel-owner "+open(k+".pub").read().strip()+"\n")
        cfgargs=dict(trust_root=al,trust_root_realpath=os.path.realpath(al),require_root_owned=False,
                     ledger=os.path.join(d,"s.jsonl"),pause_marker=os.path.join(d,"P"),
                     argv=(sys.executable,"repro.py"),cwd=cwd)
        cfg=sr.Config(**cfgargs)
        r={"schema_version":2,"state":"EXECUTION_AUTHORIZED","job_id":"J","job_digest":sr.job_digest(JOB),
           "tool":"repro","allowed_cwd":cwd,"route_manifest_sha256":sr.route_manifest_sha256(cfg),
           "max_wall_seconds":30,
           "expires_at":(datetime.now(timezone.utc)+timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
           "nonce":os.urandom(16).hex()}
        pl=os.path.join(d,"pl.json")
        with open(pl,"wb") as fh: fh.write(sr.canonical_payload(r))
        subprocess.run(["ssh-keygen","-Y","sign","-f",k,"-n",sr.NAMESPACE,pl],check=True,capture_output=True)
        r["signature"]=open(pl+".sig").read()
        return cfgargs,r
    def run(path,tag,N=10):
        cfgargs,r=build(path,tag); c=Value('i',0); start=time.time()+1.5
        ps=[Process(target=worker,args=(path,cfgargs,r,start,c)) for _ in range(N)]
        [p.start() for p in ps]; [p.join() for p in ps]
        return c.value
    base=mk("base")
    nolock=mk("nolock",('        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)\n        try:\n            if nonce in _read_ledger(fh):',
                        '        try:\n            if nonce in _read_ledger(fh):'))
    b=run(base,"b"); a=run(nolock,"nl")
    print("=== N2: remove ONLY the lock, 10 true parallel processes ===")
    print(f"  baseline (flock present) : {b} ALLOW(s)   <- must be 1")
    print(f"  ablated  (flock removed) : {a} ALLOW(s)   <- must be >1 to flip")
    print(f"  FLIP: {'YES - the lock is load-bearing' if b==1 and a>1 else 'NOT DEMONSTRATED'}")
    shutil.rmtree(WORK,ignore_errors=True)
if __name__=="__main__":
    main()
