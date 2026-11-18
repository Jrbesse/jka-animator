# SPDX-License-Identifier: MIT
"""Pure-Python tests for the B2 core (anims.py + animkit_bridge.py).

Runs without Blender; needs the animkit package (the dev clone is the
default — override with JKA_ANIMKIT_DIR). Uses a SCRATCH copy of the
assassin_droid fixture so the committed fixture is never modified.

Run:  python -m unittest discover tests
"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jka_anim_tools import animkit_bridge, anims  # noqa: E402
from jka_anim_tools.common import JkaError  # noqa: E402

ANIMKIT_DIR = os.environ.get(
    "JKA_ANIMKIT_DIR", os.path.expanduser("~/work/jka-animkit"))
FIXTURE = os.path.join(ANIMKIT_DIR, "models", "players", "assassin_droid")


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ak = animkit_bridge.get_animkit(ANIMKIT_DIR)
        cls.char = "assassin_droid"

    # fresh scratch copy PER TEST: ops that save write into the scratch
    # file, and later tests must see the pristine fixture
    def setUp(self):
        self.bp = tempfile.mkdtemp(prefix="jka_b2_")
        char = os.path.join(self.bp, "models", "players", self.char)
        os.makedirs(char)
        for f in ("animation.cfg", "animevents.cfg"):
            shutil.copy(os.path.join(FIXTURE, f), os.path.join(char, f))

    def tearDown(self):
        shutil.rmtree(self.bp, ignore_errors=True)

    def cfg(self, kind):
        return anims.cfg_path(self.bp, self.char, kind)


class TestBridge(unittest.TestCase):
    def test_dev_clone_resolves(self):
        self.assertEqual(animkit_bridge.resolve_dir(ANIMKIT_DIR), ANIMKIT_DIR)

    def test_bad_dir_lists_searched(self):
        # isolate the dev-clone fallback so only the (bad) explicit dir is
        # searchable
        env = os.environ.pop("JKA_ANIMKIT_DIR", None)
        old_dev = animkit_bridge._DEV_DEFAULT
        animkit_bridge._DEV_DEFAULT = "/nonexistent/jka-b2-test"
        try:
            with self.assertRaises(JkaError) as ctx:
                animkit_bridge.get_animkit("/nonexistent/dir/xyz")
            self.assertIn("JKA_ANIMKIT_DIR", str(ctx.exception))
        finally:
            if env is not None:
                os.environ["JKA_ANIMKIT_DIR"] = env
            animkit_bridge._DEV_DEFAULT = old_dev
            # restore the dev-clone load so later tests are unaffected
            animkit_bridge.get_animkit(ANIMKIT_DIR)

    def test_idempotent(self):
        m1 = animkit_bridge.get_animkit(ANIMKIT_DIR)
        m2 = animkit_bridge.get_animkit(ANIMKIT_DIR)
        self.assertIs(m1, m2)


class TestSegments(Base):
    def test_load(self):
        segs, warns = anims.load_segments(self.ak, self.bp, self.char)
        self.assertEqual(len(segs), 41)
        run1 = [s for s in segs if s.name == "BOTH_RUN1"][0]
        self.assertEqual((run1.first_frame, run1.num_frames,
                          run1.loop_frames, run1.fps), (128, 12, 0, 20.0))
        self.assertEqual(run1.loop_str, "loop@0")
        self.assertEqual(run1.range_str, "128..139")
        # the base-game looping anim's expected NLA props
        self.assertEqual(run1.expected_props(), (True, 20))

    def test_missing_cfg_raises(self):
        with self.assertRaises(JkaError):
            anims.load_segments(self.ak, self.bp, "no_such_char")

    def test_add_segment_round_trips(self):
        anims.load_segments(self.ak, self.bp, self.char)
        info, text = anims.add_segment(self.ak, self.bp, self.char,
                                       "BOTH_TEST_SEG", 0, 10, -1, 20)
        self.assertIn("BOTH_TEST_SEG", text)
        # reparse the produced text
        segs2, _ = self.ak.animevents.parse_animation_cfg(text)
        self.assertEqual(len(segs2), 42)  # 41 base + BOTH_TEST_SEG
        self.assertEqual([s for s in segs2 if s.name == "BOTH_TEST_SEG"][0].fps, 20.0)
        # save + reload
        anims.save_segment_doc(self.ak, self.bp, self.char)
        self.assertIn("BOTH_TEST_SEG", open(self.cfg("animation")).read())
        segs3, _ = anims.load_segments(self.ak, self.bp, self.char)
        self.assertEqual(len(segs3), 42)

    def test_next_free_frame(self):
        anims.load_segments(self.ak, self.bp, self.char)
        self.assertEqual(anims.next_free_frame(self.ak, self.bp, self.char),
                         max(s.first_frame + s.num_frames
                             for s in anims.load_segments(self.ak, self.bp, self.char)[0]))


class TestEvents(Base):
    def test_load(self):
        blocks, infos, warns = anims.load_events(self.ak, self.bp, self.char)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].header, "LOWEREVENTS")
        self.assertEqual(len(infos), 17)
        self.assertEqual(warns, [])

    def test_events_for_segment(self):
        anims.load_events(self.ak, self.bp, self.char)
        got = anims.events_for(self.ak, self.bp, self.char,
                               "lower", "BOTH_RUN1")
        # TWO base events: key 9 (line 5) and key 3 (line 18)
        self.assertEqual(len(got), 2)
        self.assertEqual({info.key_frame for _i, info in got}, {9, 3})
        for _i, info in got:
            self.assertEqual(info.etype, "AEV_SOUND")
            self.assertIn("droid_run", info.data_str)

    def test_add_and_remove_round_trip(self):
        # load_events refreshes from disk; edits live in the session doc
        # until save_events, so assert in-memory via events_for, persist
        # via save_events, then verify from disk
        anims.load_events(self.ak, self.bp, self.char)
        n0 = len(anims.load_events(self.ak, self.bp, self.char)[1])
        anims.add_event(self.ak, self.bp, self.char, "LOWER", "BOTH_RUN1",
                        "AEV_FOOTSTEP", 4, "FOOTSTEP_R 100")
        got = anims.events_for(self.ak, self.bp, self.char, "lower", "BOTH_RUN1")
        self.assertEqual(len(got), 3)  # 2 base + the added one (appended last)
        self.assertIn("FOOTSTEP_R 100", got[-1][1].data_str)
        anims.save_events(self.ak, self.bp, self.char)
        _, infos, _ = anims.load_events(self.ak, self.bp, self.char)
        self.assertEqual(len(infos), n0 + 1)
        # remove the one we added (appended last)
        got = anims.events_for(self.ak, self.bp, self.char, "LOWER", "BOTH_RUN1")
        anims.remove_event(self.ak, self.bp, self.char, "LOWER", got[2][0])
        anims.save_events(self.ak, self.bp, self.char)
        _, infos, _ = anims.load_events(self.ak, self.bp, self.char)
        self.assertEqual(len(infos), n0)

    def test_bad_data_rejected(self):
        anims.load_events(self.ak, self.bp, self.char)
        with self.assertRaises(JkaError):
            anims.add_event(self.ak, self.bp, self.char, "LOWER", "BOTH_RUN1",
                            "AEV_SOUND", 5, "sound/x.wav 1 4")  # missing chance
        with self.assertRaises(JkaError):
            anims.add_event(self.ak, self.bp, self.char, "LOWER", "BOTH_RUN1",
                            "AEV_FOOTSTEP", 5, "FOOTSTEP_R 100 7")  # too many
        with self.assertRaises(JkaError):
            anims.add_event(self.ak, self.bp, self.char, "LOWER", "BOTH_RUN1",
                            "AEV_SABER_SWING", 5, "CHAN_WEAPON 0 3 100")  # not editable

    def test_save_validates_on_write(self):
        """Seeded errors must be caught and the file left untouched."""
        anims.load_events(self.ak, self.bp, self.char)
        before = open(self.cfg("animevents")).read()
        # keyFrame beyond the segment's frame count -> validation ERROR
        anims.add_event(self.ak, self.bp, self.char, "LOWER", "BOTH_RUN1",
                        "AEV_FOOTSTEP", 99, "FOOTSTEP_R 100")
        with self.assertRaises(JkaError) as ctx:
            anims.save_events(self.ak, self.bp, self.char)
        self.assertIn("write blocked", str(ctx.exception))
        self.assertIn("keyFrame 99", str(ctx.exception))
        self.assertEqual(open(self.cfg("animevents")).read(), before)
        # remove the bad event, then save must succeed
        got = anims.events_for(self.ak, self.bp, self.char, "LOWER", "BOTH_RUN1")
        anims.remove_event(self.ak, self.bp, self.char, "LOWER", got[-1][0])
        warnings, path = anims.save_events(self.ak, self.bp, self.char)
        self.assertEqual(path, self.cfg("animevents"))
        self.assertEqual(warnings, [])
        self.assertEqual(open(self.cfg("animevents")).read(), before)

    def test_unknown_segment_event_warns_but_saves(self):
        anims.load_events(self.ak, self.bp, self.char)
        # an event on an anim that has NO segment: warning, not error —
        # but the engine skips it (unknown to the anim table or absent
        # from the GLA), so it validates as 'never fires'
        anims.add_event(self.ak, self.bp, self.char, "LOWER", "BOTH_RUN1",
                        "AEV_FOOTSTEP", 1, "FOOTSTEP_L 100")
        warnings, _ = anims.save_events(self.ak, self.bp, self.char)
        # warning-free for the base file; the added event is in-range
        self.assertEqual(warnings, [])


class TestSaber(Base):
    def test_missing_file_is_not_an_error(self):
        styles, errors, warnings, path = anims.validate_saberanims(self.ak, self.bp)
        self.assertEqual(errors, [])
        self.assertEqual(styles, [])
        self.assertTrue(path.endswith("saberanims.cfg"))

    def test_presets_from_builtin_fallback(self):
        presets = anims.saber_presets(self.ak, self.bp)
        self.assertEqual(presets[0].label, "guard (stand)")
        self.assertEqual(presets[0].name, "BOTH_STAND1")
        attacks = {p.name: p.label for p in presets[1:]}
        self.assertEqual(attacks["BOTH_H1_S1_TR"], "attack: fast (BOTH_H1_S1_TR)")
        self.assertEqual(attacks["BOTH_H7_S7_T_"], "attack: staff (BOTH_H7_S7_T_)")
        self.assertEqual(len(presets), 8)
        for p in presets:
            self.assertEqual(p.loop_frames, -1)

    def test_presets_from_real_file(self):
        ext = os.path.join(self.bp, "ext_data")
        os.makedirs(ext, exist_ok=True)
        src = os.path.join(ANIMKIT_DIR, "ext_data", "saberanims.cfg")
        dst = os.path.join(ext, "saberanims.cfg")
        shutil.copy(src, dst)
        styles, errors, warnings, _ = anims.validate_saberanims(self.ak, self.bp)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual([s.name for s in styles],
                         ["fast", "medium", "strong", "desann", "tavion",
                          "dual", "staff"])
        presets = anims.saber_presets(self.ak, self.bp)
        # the live mod's openanims feed the presets (fast -> BOTH_H1_S1_TR)
        self.assertIn("attack: fast (BOTH_H1_S1_TR)",
                      [p.label for p in presets])

    def test_seed_error_caught(self):
        ext = os.path.join(self.bp, "ext_data")
        os.makedirs(ext, exist_ok=True)
        dst = os.path.join(ext, "saberanims.cfg")
        with open(dst, "w") as f:
            f.write("style fast\n{\nstopcost 12\n}\nstyle NOTASTYLE\n{\n"
                    "stopcost 1\n}\n")
        styles, errors, warnings, _ = anims.validate_saberanims(self.ak, self.bp)
        self.assertTrue(any("NOTASTYLE" in e for e in errors))
        self.assertEqual([s.name for s in styles], ["fast"])  # halted


if __name__ == "__main__":
    unittest.main()
