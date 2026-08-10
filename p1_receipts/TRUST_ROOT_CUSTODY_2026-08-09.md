# Trust-root custody readback

Run as the worker account on 2026-08-09. Every line read back from the machine.

```text
worker account          : kenielmaldonado (euid 501)
worker euid != 0        : True
declared path           : /etc/keniel-agent/owner_execution_allowed_signers
resolved path           : /private/etc/keniel-agent/owner_execution_allowed_signers
final component symlink : False
regular file            : True
uid                     : 0 (root)
mode                    : 0o644
group/world writable    : False
worker writable (file)  : False
```

Full path chain, every component:

```text
/private                                                   uid=0 mode=0o755 worker_writable=False
/private/etc                                               uid=0 mode=0o755 worker_writable=False
/private/etc/keniel-agent                                  uid=0 mode=0o755 worker_writable=False
/private/etc/keniel-agent/owner_execution_allowed_signers  uid=0 mode=0o644 worker_writable=False
ENTIRE CHAIN NON-WRITABLE BY WORKER: True
```

Live attempts from the worker account, all refused:

```text
touch /etc/keniel-agent/x                                          rc=1  Permission denied
echo evil >> .../owner_execution_allowed_signers                   rc=1  Permission denied
mv .../owner_execution_allowed_signers /tmp/stolen                 rc=1  Permission denied
rm -f .../owner_execution_allowed_signers                          rc=1  Permission denied
file intact afterwards: True, 107 bytes
```

The `mv` row matters as much as the write rows: replacement by rename through a
worker-writable parent is the way a trust root gets substituted without ever being written
to. The parent directory is root-owned and mode 755, so that path is closed too.
