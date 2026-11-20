# SPDX-License-Identifier: MIT
"""Pure-Python tests for the B3 check core (checkop.py).

Runs without Blender; needs the animkit package (the dev clone is the
default — override with JKA_ANIMKIT_DIR). Scratch copies only — the
committed fixtures are never modified.

Run:  python -m unittest discover tests
"""
import os
import shutil
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jka_anim_tools import animkit_bridge, checkop  # noqa: E402
from jka_anim_tools.common import JkaError  # noqa: E402

ANIMKIT_DIR = os.environ.get(
    "JKA_ANIMKIT_DIR", os.path.expanduser("~/work/jka-animkit"))
SKELETON_FIXTURE = os.path.join(ANIMKIT_DIR, "models", "players", "_humanoid")
CHAR_FIXTURE = os.path.join(ANIMKIT_DIR, "models", "players", "assassin_droid")


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ak = animkit_bridge.get_animkit(ANIMKIT_DIR)

    # fresh scratch base PER TEST (a seeded test must not leak into others)
    def setUp(self):
        self.bp = tempfile.mkdtemp(prefix="jka_b3_")

    def tearDown(self):
        shutil.rmtree(self.bp, ignore_errors=True)

    def stage_skeleton(self):
        d = os.path.join(self.bp, "models", "players", "_humanoid")
        shutil.copytree(SKELETON_FIXTURE, d)
        return d

    def stage_char(self):
        d = os.path.join(self.bp, "models", "players", "assassin_droid")
        shutil.copytree(CHAR_FIXTURE, d)
        return d


class TestResolve(unittest.TestCase):
    def test_char_dir(self):
        bp = tempfile.mkdtemp(prefix="jka_b3r_")
        try:
            os.makedirs(os.path.join(bp, "models", "players", "_humanoid"))
            d = checkop.resolve_char_dir(bp, "_humanoid")
            self.assertEqual(d, os.path.join(bp, "models", "players", "_humanoid"))
        finally:
            shutil.rmtree(bp, ignore_errors=True)

    def test_empty_base(self):
        with self.assertRaises(JkaError):
            checkop.resolve_char_dir("", "_humanoid")

    def test_empty_character(self):
        bp = tempfile.mkdtemp(prefix="jka_b3r_")
        try:
            with self.assertRaises(JkaError):
                checkop.resolve_char_dir(bp, "")
        finally:
            shutil.rmtree(bp, ignore_errors=True)

    def test_missing_dir(self):
        bp = tempfile.mkdtemp(prefix="jka_b3r_")
        try:
            with self.assertRaises(JkaError) as ctx:
                checkop.resolve_char_dir(bp, "no_such_char")
            self.assertIn("no_such_char", str(ctx.exception))
        finally:
            shutil.rmtree(bp, ignore_errors=True)


class TestCheck(Base):
    def test_skeleton_dir_clean(self):
        d = self.stage_skeleton()
        r = checkop.check_dir(self.ak, d)
        self.assertTrue(r.ok, r.errors)
        self.assertEqual(r.errors, [])
        self.assertGreater(len(r.warnings), 0)  # the live cfg carries warnings
        self.assertEqual(r.name, "_humanoid")
        self.assertIn("OK", r.summary())

    def test_character_dir_clean(self):
        d = self.stage_char()
        r = checkop.check_dir(self.ak, d)
        self.assertTrue(r.ok, r.errors)
        self.assertEqual(r.errors, [])

    def test_missing_dir_raises(self):
        with self.assertRaises(JkaError):
            checkop.check_dir(self.ak, "/nonexistent/jka_b3_dir")

    def test_crash_is_error_not_result(self):
        # a dir that exists but holds neither model.glm nor a .gla → check
        # itself records the finding (model.glm not found) — that is a
        # FAILED result, not a crash
        d = os.path.join(self.bp, "models", "players", "empty_char")
        os.makedirs(d)
        r = checkop.check_dir(self.ak, d)
        self.assertFalse(r.ok)
        self.assertTrue(any("model.glm not found" in e for e in r.errors))

    def test_seeded_cfg_error(self):
        d = self.stage_skeleton()
        with open(os.path.join(d, "animation.cfg"), "a") as f:
            f.write("\nBOTH_FAKE_XYZ 999999 10 0 20\n")
        r = checkop.check_dir(self.ak, d)
        self.assertFalse(r.ok)
        self.assertTrue(
            any("BOTH_FAKE_XYZ" in e for e in r.errors), r.errors)

    def test_seeded_gla_corrupt(self):
        d = self.stage_skeleton()
        p = os.path.join(d, "_humanoid.gla")
        with open(p, "r+b") as f:
            # GLA header <ii64sf6i>: numBones is the 8th field @ offset 84
            f.seek(84)
            f.write(struct.pack("<i", 60))  # 53 -> 60: skeleton/frames disagree
        r = checkop.check_dir(self.ak, d)
        self.assertFalse(r.ok)
        self.assertGreaterEqual(len(r.errors), 1)


class TestLines(Base):
    def _failed(self):
        d = self.stage_skeleton()
        with open(os.path.join(d, "animation.cfg"), "a") as f:
            f.write("\nBOTH_FAKE_XYZ 999999 10 0 20\n")
        return checkop.check_dir(self.ak, d)

    def test_counts(self):
        r = self._failed()
        lines = r.lines()
        # summary + one line per error + one line per condensed warning
        # group (warnings collapse per (file, type), Sheng retest #5)
        self.assertEqual(len(lines),
                         1 + len(r.errors) + len(r.condensed_warnings()))

    def test_order_and_flags(self):
        r = self._failed()
        lines = r.lines()
        # summary first, marked as an error line because the check failed
        self.assertEqual(lines[0][1], True)
        self.assertIn("FAILED", lines[0][0])
        body = lines[1:]
        n_err, n_cwarn = len(r.errors), len(r.condensed_warnings())
        for text, is_err in body[:n_err]:
            self.assertTrue(is_err)
        for text, is_err in body[n_err:]:
            self.assertFalse(is_err)
        self.assertEqual(len(body), n_err + n_cwarn)

    def test_ok_summary(self):
        d = self.stage_skeleton()
        r = checkop.check_dir(self.ak, d)
        lines = r.lines()
        self.assertFalse(lines[0][1])
        self.assertIn("OK", lines[0][0])
        if r.warnings:
            self.assertIn(str(len(r.warnings)), lines[0][0])


class TestCondense(unittest.TestCase):
    """The display condensing — pure CheckResult objects, no fixtures."""

    def _res(self, warnings=(), errors=()):
        return checkop.CheckResult("/tmp/char", not errors,
                                   list(errors), list(warnings))

    def test_single_warning_passes_through(self):
        w = ("[animation.cfg] line 5: 'BOTH_X' is not a known engine anim "
             "name — the game will WARN and IGNORE this segment")
        r = self._res(warnings=[w])
        self.assertEqual(r.lines()[1], (w, False))

    def test_group_collapses_to_count_and_range(self):
        w = [f"[animation.cfg] line {n}: 'BOTH_{i}' is not a known engine "
             f"anim name — the game will WARN and IGNORE this segment"
             for i, n in enumerate(range(1453, 1463))]
        r = self._res(warnings=w)
        warns = r.lines()[1:]
        self.assertEqual(len(warns), 1)
        text, is_err = warns[0]
        self.assertIn("×10", text)
        self.assertIn("lines 1453-1462", text)
        self.assertIn("BOTH_0", text)  # first message shown verbatim
        self.assertFalse(is_err)

    def test_nonconsecutive_ranges(self):
        w = [f"[animevents.cfg] line {n}: duplicate segment 'X' "
             f"(last one wins)" for n in (18, 12, 13, 21, 20)]
        r = self._res(warnings=w)
        text = r.lines()[1][0]
        self.assertIn("12-13, 18, 20-21", text)

    def test_same_type_different_numbers_group(self):
        w = ("[animevents.cfg] line 3: AEV_MOVE speed=5 outside the "
             "engine's 0..255",
             "[animevents.cfg] line 9: AEV_MOVE speed=99 outside the "
             "engine's 0..255")
        r = self._res(warnings=list(w))
        warns = r.lines()[1:]
        self.assertEqual(len(warns), 1)
        self.assertIn("lines 3, 9", warns[0][0])

    def test_different_types_stay_separate(self):
        w = ("[animation.cfg] line 5: 'A' is not a known engine anim name",
             "[animation.cfg] line 6: 'B' is not a known engine anim name",
             "[animation.cfg] line 7: 'C' has numFrames=0 (treated as "
             "empty by engine)")
        r = self._res(warnings=list(w))
        self.assertEqual(len(r.lines()[1:]), 2)

    def test_identical_noline_warnings_group(self):
        w = ("[model.glm] surface 'head' has no geometry in any LOD",
             "[model.glm] surface 'leg' has no geometry in any LOD")
        r = self._res(warnings=list(w))
        warns = r.lines()[1:]
        self.assertEqual(len(warns), 1)
        self.assertIn("×2", warns[0][0])
        self.assertNotIn("(lines", warns[0][0])

    def test_errors_never_condensed(self):
        warns = ("[animation.cfg] line 1: 'A' is not a known engine anim "
                 "name",
                 "[animation.cfg] line 2: 'B' is not a known engine anim "
                 "name")
        r = self._res(errors=["[a.gla] bad", "[a.gla] bad"],
                      warnings=list(warns))
        lines = r.lines()
        # summary + both errors verbatim + one condensed warning group
        self.assertEqual(len(lines), 4)
        self.assertEqual(lines[1], ("[a.gla] bad", True))
        self.assertEqual(lines[2], ("[a.gla] bad", True))


if __name__ == "__main__":
    unittest.main()
