"""Tests for tools/run_harness.py.

Unit tests cover the path rewrite and the refusals. The reproduction tests run
the deterministic harnesses end to end against the shipped bytes and check
that the printed tables say what the recorded verdicts say. The two N2
harnesses are race experiments and are not asserted here (the recorded verdict
itself reports natural-timing N2 as "not demonstrated").
"""

from __future__ import annotations

import io
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import run_harness as rh  # noqa: E402

HAVE_SSH_KEYGEN = shutil.which("ssh-keygen") is not None


class Rewrite(unittest.TestCase):
    def test_only_quoted_input_paths_are_rewritten(self):
        src = (
            f'MOD="{rh.AUTHOR_MODULE_PATH}"\nWKR="{rh.AUTHOR_WORKER_PATH}"\n'
            "PAT='    ledger: str = \"/Users/kenielmaldonado/km_agent/state/x.jsonl\"'\n"
        )
        out, reps = rh.rewrite(src, "/sb/m.py", "/sb/w.py")
        self.assertIn('MOD="/sb/m.py"', out)
        self.assertIn('WKR="/sb/w.py"', out)
        self.assertIn("/Users/kenielmaldonado/km_agent/state/x.jsonl", out)
        self.assertEqual([(r[0], r[2]) for r in reps], [(rh.AUTHOR_MODULE_PATH, 1), (rh.AUTHOR_WORKER_PATH, 1)])

    def test_committed_harness_files_are_untouched_by_a_run(self):
        harness = REPO / "ABLATION_HARNESS_KAEL_2026-08-09.py"
        before = harness.read_bytes()
        rh.rewrite(before.decode("utf-8"), "/a", "/b")
        self.assertEqual(harness.read_bytes(), before)

    def test_pinned_target_detected(self):
        src = (REPO / "I3_REGRESSION_FLOOR_HARNESS_KAEL_2026-08-09.py").read_text(encoding="utf-8")
        self.assertEqual(rh.pinned_target(src), "df50689768455f9f55a86374e621006a00436c1ddae69bb92c530fe6c165db05")

    def test_retarget_replaces_only_the_pin(self):
        src = 'EXPECT = "' + "a" * 64 + '"\nOTHER = "' + "a" * 64 + '"\n'
        out, _ = rh.rewrite(src, "/m", "/w", retarget_to="b" * 64)
        self.assertIn('EXPECT = "' + "b" * 64 + '"', out)
        self.assertIn('OTHER = "' + "a" * 64 + '"', out)


class Refusals(unittest.TestCase):
    def test_refuses_unpublished_worker_target_without_retarget(self):
        with self.assertRaises(rh.RunnerError) as cm:
            rh.run(REPO / "I3_REGRESSION_FLOOR_HARNESS_KAEL_2026-08-09.py", out=io.StringIO())
        self.assertIn("not in this bundle", str(cm.exception))

    def test_refuses_changed_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp)
            for name in rh.EXPECTED:
                shutil.copyfile(REPO / name, copy / name)
            (copy / rh.MODULE_FILE).write_text("# not the shipped bytes\n")
            with self.assertRaises(rh.RunnerError) as cm:
                rh.check_inputs(copy)
            self.assertIn("README publishes", str(cm.exception))

    def test_missing_harness(self):
        with self.assertRaises(rh.RunnerError):
            rh.run(REPO / "NO_SUCH_HARNESS.py", out=io.StringIO())

    def test_god_jobs_stand_in_refuses_unpatched_calls(self):
        ns = {}
        exec(compile(rh.GOD_JOBS_STUB, "god_jobs", "exec"), ns)
        with self.assertRaises(RuntimeError):
            ns["run_allowlisted"]("repro")


@unittest.skipUnless(HAVE_SSH_KEYGEN, "ssh-keygen not on PATH")
class Reproduction(unittest.TestCase):
    def run_harness(self, name, **kw):
        buf = io.StringIO()
        rc = rh.run(REPO / name, out=buf, timeout=300, **kw)
        return rc, buf.getvalue()

    def test_module_ablations_flip_8_of_8(self):
        rc, out = self.run_harness("ABLATION_HARNESS_KAEL_2026-08-09.py")
        self.assertEqual(rc, 0, out)
        self.assertIn("8/8 ablations flipped", out)

    def test_followup_rows(self):
        rc, out = self.run_harness("ABLATION_FOLLOWUP_A12_A20_I8_KAEL_2026-08-09.py")
        self.assertEqual(rc, 0, out)
        for row in ("A12", "A20", "I8"):
            line = next(ln for ln in out.splitlines() if ln.startswith(row))
            self.assertTrue(line.rstrip().endswith("YES"), line)

    def test_i4a_i7_removal_flip_with_live_happy_path(self):
        rc, out = self.run_harness("ABLATION_I4A_I7_REMOVAL_TESTS_KAEL_2026-08-09.py")
        self.assertEqual(rc, 0, out)
        for row in ("I4a", "I7"):
            line = next(ln for ln in out.splitlines() if ln.startswith(row))
            self.assertTrue(line.rstrip().endswith("YES"), line)
        self.assertIn("SANITY: happy path executor calls = 1", out)

    def test_i3_floor_retargeted_is_labelled(self):
        rc, out = self.run_harness("I3_REGRESSION_FLOOR_HARNESS_KAEL_2026-08-09.py", retarget=True)
        self.assertEqual(rc, 0, out)
        self.assertIn("RETARGETED RUN. Not the recorded experiment.", out)
        self.assertIn("19/19 cases pass", out)
        self.assertIn("total executor calls: 0", out)


if __name__ == "__main__":
    unittest.main()
