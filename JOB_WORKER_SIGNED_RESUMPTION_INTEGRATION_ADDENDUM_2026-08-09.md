# Integration Addendum — closes I-B1 and I-B2

**Frozen:** 2026-08-09. **Maker:** Ka'el. **CONTRACT ONLY. NO WORKER EDIT EXISTS.**
**Body unchanged:** `JOB_WORKER_SIGNED_RESUMPTION_INTEGRATION_FREEZE_2026-08-09.md`
sha256 `74fcec1591c5dac30efd3b768583ff4808a391b40e01a08c95d23e95068fadf8`.

Closes the two hard seams from
`JOB_WORKER_SIGNED_RESUMPTION_INTEGRATION_FREEZE_BREAKER_VERDICT_AETHAR_2026-08-09.md`
(`a134d765…6d11`), **as the breaker itself re-graded them.** Aethar published four B-ids, then
demoted two on a colder second pass. This addendum follows the re-grade, not the original
count. Treating four as equal would re-inflate exactly what the breaker deflated.

| ID | Breaker's final grade | Handled here as |
|---|---|---|
| I-B1 receipt path | BLOCK | **IR1**, hard repair |
| I-B2 production Config | BLOCK, strongest | **IR2**, hard repair |
| I-B3 key derivation | demoted to residual | **IR3**, narrow binding |
| I-B4 legacy True-branch | demoted to advisory | **IR4**, restatement only |

**Verified against live source before repairing:**
- `EXECUTION_AUTHORIZATION` exists in the live worker at line 37. The freeze body names it
  **zero** times. The breaker is right: "fixed in worker constants" without naming the constant
  lets glue invent a path and still be freeze-compliant.
- The freeze body mentions `cfg` **once**, inside a call signature, and never says how it is
  built. Confirmed.
- `strip_auto_prefix` exists at line 321. Confirmed.

---

## IR1 (closes I-B1) — the receipt path is named, and it is the existing one

The signed route reads its receipt from **exactly** the constant already in the live worker:

```
EXECUTION_AUTHORIZATION = os.path.join(AGENT_DIR, "JOB_WORKER_EXECUTION_AUTHORIZED.json")
                        = /Users/kenielmaldonado/km_agent/JOB_WORKER_EXECUTION_AUTHORIZED.json
```

**No new path is introduced.** This is the same file the 2026-07-31 breaker already attacked
across its 19 cases, so IR1 inherits that scrutiny rather than opening fresh ground.

- Read as **raw bytes**, handed to `parse_receipt()` so the size bound applies before parsing.
- The path is **never** derived from job text, the prompt, environment variables, argv, or any
  receipt field. A receipt that names its own location is a refusal, not a redirect.
- `os.path.realpath` of the opened file must equal the constant. A symlink pointing elsewhere
  refuses.

| # | Case | Expected | Executor calls |
|---|---|---|---|
| **I13** | receipt read from any path other than the constant | BLOCK | 0 |
| **I14** | the constant replaced by a symlink to a receipt elsewhere | BLOCK | 0 |

---

## IR2 (closes I-B2) — the production Config is frozen, and fixtures cannot reach production

This was the breaker's strongest finding and it was correct. `execute_authorized_job(job,
receipt, cfg)` with an unfrozen `cfg` is not an integration freeze: the `Config` **is** the
security boundary. It carries the trust root, `require_root_owned`, the ledger, the pause
marker, the argv, and the cwd. A glue author could pass `require_root_owned=False` with a
fixture trust root, watch I1 go green, and have proven nothing.

**The signed route constructs its Config in exactly one way, with no arguments:**

```python
cfg = signed_resumption.Config()          # all frozen production defaults
```

and the worker **asserts before use** that it received that value:

```python
if cfg != signed_resumption.Config():
    raise Refusal("NON_PRODUCTION_CONFIG_ON_SIGNED_ROUTE")
```

`Config` is a frozen dataclass, so equality is field-by-field. Any override — a fixture trust
root, `require_root_owned=False`, a different ledger, a different argv or cwd — is structurally
unable to reach the production path.

**Consequence for evidence, stated plainly:** any I1 obtained with a non-default Config is a
maker fixture and remains K5 stage 1. It does not become integration evidence by being run
through the worker.

| # | Case | Expected | Executor calls |
|---|---|---|---|
| **I11** | glue passes `Config(require_root_owned=False)` | BLOCK, `NON_PRODUCTION_CONFIG_ON_SIGNED_ROUTE` | 0 |
| **I12** | glue passes a Config with any other field overridden | BLOCK, same code | 0 |
| **I15** | glue passes the default `Config()` while the real trust root is absent | BLOCK, `TRUST_ROOT_ABSENT` | 0 |

**New ablation:** remove the Config equality assertion → **I11 must succeed** (a fixture trust
root reaches the production path).

---

## IR3 (residual, demoted by the breaker) — key derivation binds the live function

Key derivation on the signed route is exactly the live behaviour, bound by name:

```python
key = strip_auto_prefix(prompt).strip().lower().split()[0]
```

`strip_auto_prefix` is the function at live worker line 321. Naming it prevents a glue author
from re-implementing prefix handling and quietly widening what counts as `repro`.

This is a residual, not a seam. The freeze body already showed today's formula in its call-site
table; what was missing was the function name.

---

## IR4 (advisory, demoted by the breaker) — restatement, not a new requirement

`independent_signature_verified()` in the live worker still has no reachable `True`, and the
freeze body already forbids weakening `execution_decision()` for convenience. Reaffirmed here
so it is not lost: the legacy path stays fail-closed until a separate freeze says otherwise.
Nothing in this integration changes it.

---

## How this can come out wrong

- **The Config assertion is written but the glue constructs the Config inside the same function
  it guards**, so a fixture value is compared against itself. The assertion must compare against
  a freshly constructed `Config()`, not against the passed object.
- **IR1 is satisfied by a new constant that merely looks fixed.** It must be the existing
  `EXECUTION_AUTHORIZATION`, so the 07-31 attacks apply unchanged.
- **I11/I12 are tested with the assertion's own equality helper** rather than by actually
  passing a modified Config through the real call path.
- **The demotions are quietly re-inflated** to make this addendum look larger. I-B3 and I-B4 are
  a binding and a restatement. If either is presented as a seam, this document is wrong.

## Freeze rule

Body `74fcec15…adf8` unchanged. Re-break covers **I-B1 and I-B2 plus retained body invariants**;
I-B3 and I-B4 are checked as the residual and advisory they were re-graded to be. No worker edit
is authorized until PASS. Trust root, private key, live P1, extra routes, and articles all remain
forbidden.
