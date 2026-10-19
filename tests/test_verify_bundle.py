"""Tests for tools/verify_bundle.py.

The positive test runs every check against the committed bundle. The negative
tests copy the bundle to a temporary directory, change one thing, and require
the matching check (and only a relevant check) to fail. The committed bundle is
never written to.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import verify_bundle as vb  # noqa: E402

HAVE_SSH_KEYGEN = shutil.which("ssh-keygen") is not None


def failed(results) -> set:
    return {name for name, ok, _ in results if not ok}


@unittest.skipUnless(HAVE_SSH_KEYGEN, "ssh-keygen not on PATH")
class CommittedBundle(unittest.TestCase):
    def test_every_check_passes(self):
        results = vb.run_checks(REPO)
        self.assertEqual(failed(results), set(), results)
        self.assertEqual(len(results), len(vb.CHECKS))

    def test_manifest_covers_every_evidence_file(self):
        listed = {
            line.split(None, 1)[1] for line in (REPO / vb.SUMS).read_text(encoding="utf-8").splitlines() if line.strip()
        }
        actual = {p.relative_to(REPO).as_posix() for p in vb.evidence_files(REPO)}
        self.assertEqual(listed, actual)
        self.assertIn("p1_receipts/JOB_WORKER_EXECUTION_AUTHORIZED.json", listed)
        self.assertEqual(sum(1 for n in listed if n.startswith("verdicts/")), 12)


@unittest.skipUnless(HAVE_SSH_KEYGEN, "ssh-keygen not on PATH")
class TamperedCopies(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="sr-test-")
        self.copy = Path(self._tmp.name) / "bundle"
        shutil.copytree(REPO, self.copy, ignore=shutil.ignore_patterns(".git", "__pycache__"))

    def tearDown(self):
        self._tmp.cleanup()

    def edit_json(self, rel, indent=2, **changes):
        path = self.copy / rel
        data = json.loads(path.read_text(encoding="utf-8"))
        data.update(changes)
        path.write_text(json.dumps(data, indent=indent, sort_keys=True), encoding="utf-8")

    def test_changed_receipt_field_breaks_signature(self):
        self.edit_json(vb.RECEIPT, max_wall_seconds=601)
        bad = failed(vb.run_checks(self.copy))
        self.assertIn("payload", bad)
        self.assertIn("evidence-sums", bad)

    def test_reformatted_receipt_still_verifies(self):
        # Whitespace in the envelope is not signed; only the canonical payload is.
        # The manifest still flags the byte change, which is the point of it.
        self.edit_json(vb.RECEIPT, indent=4)
        bad = failed(vb.run_checks(self.copy))
        self.assertEqual(bad, {"evidence-sums"})

    def test_second_ledger_entry_is_caught(self):
        path = self.copy / vb.LEDGER
        line = path.read_text(encoding="utf-8").splitlines()[0]
        path.write_text(line + "\n" + line + "\n", encoding="utf-8")
        bad = failed(vb.run_checks(self.copy))
        self.assertIn("p1-consistency", bad)

    def test_changed_shipped_module_is_caught(self):
        path = self.copy / "signed_resumption.py"
        path.write_bytes(path.read_bytes() + b"\n")
        bad = failed(vb.run_checks(self.copy))
        self.assertIn("shipped-bytes", bad)
        self.assertIn("evidence-sums", bad)

    def test_changed_contract_is_caught(self):
        path = self.copy / "JOB_WORKER_SIGNED_RESUMPTION_PREREG_V2_2026-08-09.md"
        path.write_bytes(path.read_bytes().replace(b"Frozen", b"Frozn", 1))
        self.assertIn("frozen-contracts", failed(vb.run_checks(self.copy)))

    def test_flipped_verdict_is_caught(self):
        path = next((self.copy / "verdicts").glob("*PREREG_BREAKER_VERDICT_KAIROS*"))
        path.write_text(
            path.read_text(encoding="utf-8").replace("## Verdict: **BLOCK**", "## Verdict: **PASS**"), encoding="utf-8"
        )
        bad = failed(vb.run_checks(self.copy))
        self.assertIn("verdict-inventory", bad)
        self.assertIn("evidence-sums", bad)

    def test_substituted_key_is_caught(self):
        keygen = shutil.which("ssh-keygen")
        key = Path(self._tmp.name) / "k"
        import subprocess

        subprocess.run(
            [keygen, "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True, capture_output=True, timeout=30
        )
        (self.copy / vb.SIGNERS).write_text(
            "keniel-owner " + key.with_suffix(".pub").read_text().strip() + "\n", encoding="utf-8"
        )
        bad = failed(vb.run_checks(self.copy))
        self.assertTrue({"signature", "key-fingerprint", "module-accepts"} <= bad, bad)

    def test_new_untracked_evidence_file_is_caught(self):
        (self.copy / "verdicts" / "EXTRA_VERDICT.md").write_text("## Verdict: **PASS**\n")
        bad = failed(vb.run_checks(self.copy))
        self.assertIn("evidence-sums", bad)
        self.assertIn("verdict-inventory", bad)


if __name__ == "__main__":
    unittest.main()
