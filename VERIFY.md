# Verify the P1 receipt yourself

You do not have to trust anything in this repository. The operator signature can be checked
against the published public key with stock OpenSSH. These exact commands were run before this
file was written.

## 1. Rebuild the signed payload

The signature covers the receipt **minus** the `signature` field, serialized as UTF-8 JSON with
`sort_keys=True` and `separators=(",",":")`, no trailing newline.

```bash
python3 - <<'PY'
import json
r = json.load(open("p1_receipts/JOB_WORKER_EXECUTION_AUTHORIZED.json"))
p = {k: v for k, v in r.items() if k != "signature"}
open("payload.json", "wb").write(
    json.dumps(p, sort_keys=True, separators=(",", ":")).encode())
open("payload.sig", "w").write(r["signature"])
PY
```

`payload.json` should be **433 bytes**, SHA-256
`4ed5ecff82def7098f604c39d95a62ace61f4850f035ba8088b8c49637c6b64f`.

That is the same digest that was compared by eye across two machines before signing.

## 2. Verify

```bash
ssh-keygen -Y verify -f owner_execution_allowed_signers \
  -I keniel-owner -n km-agent-execution-authorization \
  -s payload.sig < payload.json
```

Expected:

```
Good "km-agent-execution-authorization" signature for keniel-owner with ED25519 key
SHA256:EsftjEQJF0z4+fBDDZNEXmIUUK0ydtyijHqfsmRyfpA
```

## 3. Confirm it is not vacuous

Change one byte and it must fail:

```bash
sed 's/"max_wall_seconds":600/"max_wall_seconds":601/' payload.json > bad.json
ssh-keygen -Y verify -f owner_execution_allowed_signers \
  -I keniel-owner -n km-agent-execution-authorization \
  -s payload.sig < bad.json
```

Expected: `Signature verification failed: incorrect signature`.

## What this does and does not establish

Verifying this signature proves the receipt was signed by the holder of the private half of
`owner_execution_allowed_signers`, and that the receipt bytes have not changed since.

It does **not** prove where that private key was kept. Key custody is an operational property of
how the run was conducted, not something the receipt can attest. The claim is that the private
half was generated on a physically separate machine and never copied to the machine the agents
run on — that is a statement about procedure, and you should read it as one.

It also does not prove the host was uncompromised. See the limits section of the article.
