# SPDX-License-Identifier: MIT
"""Pure-Python tests for the B3 finger preset core (fingers.py).

Runs without Blender. The tables are HAND-RELATIVE data (derived on
the gdesk VM through the verified importer — see the core's
docstring); these tests pin their structural invariants: 12 bones x
16 floats with the parent chain intact, orthonormal rotation parts
(det +1), the EXACT mirror symmetry of the fist table (its left side
was built as the right side's D-conjugate, finding F5), the preset
sources on record, and the grasp = slerp midpoint property.

Run:  python -m unittest discover tests
"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jka_anim_tools import fingers  # noqa: E402
from jka_anim_tools.common import JkaError  # noqa: E402

# the F5 mirror conjugator, 4x4 diag(1,1,-1,1)
D = (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, -1, 0, 0, 0, 0, 1)


def _mm(a, b):
    out = [0.0] * 16
    for r in range(4):
        for c in range(4):
            out[r * 4 + c] = sum(a[r * 4 + k] * b[k * 4 + c] for k in range(4))
    return tuple(out)


def _quat_angle(a, b):
    """Angle between two 16-float matrices (double-cover safe)."""
    qa = fingers.quat_from_rot(fingers._rot_of(a))
    qb = fingers.quat_from_rot(fingers._rot_of(b))
    d = abs(sum(x * y for x, y in zip(qa, qb)))
    return math.acos(min(1.0, d))


class TestTables(unittest.TestCase):
    def test_shape(self):
        for table in (fingers.FIST, fingers.OPEN):
            self.assertEqual(set(table), set(fingers.FINGER_BONES))
            for bone, m in table.items():
                self.assertEqual(len(m), 16, bone)
                self.assertEqual(m[12:], (0.0, 0.0, 0.0, 1.0), bone)

    def test_rotation_parts_orthonormal(self):
        # worst error in the committed tables is < 1e-5 (FIST 6.9e-6,
        # OPEN 8.2e-6) — places=4 (5e-5) leaves margin
        for table in (fingers.FIST, fingers.OPEN):
            for bone, m in table.items():
                r = fingers._rot_of(m)
                rows = [r[i * 3:i * 3 + 3] for i in range(3)]
                for a in rows:
                    self.assertAlmostEqual(
                        math.sqrt(sum(v * v for v in a)), 1.0, places=4,
                        msg=bone)
                for i in range(3):
                    for j in range(i + 1, 3):
                        self.assertAlmostEqual(
                            sum(x * y for x, y in zip(rows[i], rows[j])),
                            0.0, places=4, msg=bone)
                det = (rows[0][0] * (rows[1][1] * rows[2][2]
                                     - rows[1][2] * rows[2][1])
                       - rows[0][1] * (rows[1][0] * rows[2][2]
                                      - rows[1][2] * rows[2][0])
                       + rows[0][2] * (rows[1][0] * rows[2][1]
                                      - rows[1][1] * rows[2][0]))
                self.assertAlmostEqual(det, 1.0, places=4, msg=bone)

    def test_parent_chain(self):
        # _j1 parent = the hand, _j2 parent = its _j1; every parent is
        # a known bone and precedes its children in FINGER_BONES
        for bone in fingers.FINGER_BONES:
            parent = fingers.PARENT_BONE[bone]
            if bone.endswith("_j2"):
                self.assertEqual(parent, bone[:-3] + "_j1", bone)
            else:
                self.assertIn(parent, fingers.HAND_BONES, bone)
            self.assertIn(parent, fingers.HAND_BONES + fingers.FINGER_BONES,
                          bone)
            if parent in fingers.FINGER_BONES:
                self.assertLess(fingers.FINGER_BONES.index(parent),
                                fingers.FINGER_BONES.index(bone), bone)

    def test_fist_is_mirrored(self):
        # F5: the fist's left side was built as D·REL_right·D — exact
        # (the tables were built that way), not approximate
        for bone in fingers.FINGER_BONES:
            if not bone.startswith("l_"):
                continue
            r = "r_" + bone[2:]
            self.assertEqual(fingers.FIST[bone],
                             _mm(D, _mm(fingers.FIST[r], D)), bone)

    def test_fist_and_open_differ(self):
        self.assertEqual(
            sum(1 for b in fingers.FINGER_BONES
                if fingers.FIST[b] != fingers.OPEN[b]), 12)

    def test_sources_on_record(self):
        # decision #18: the reference selection, pinned
        self.assertEqual(fingers.PRESET_SOURCES["fist"],
                         ("BOTH_P6_S6_TR", 10370))
        self.assertEqual(fingers.PRESET_SOURCES["open"],
                         ("BOTH_STAND1", 14578))


class TestQuaternion(unittest.TestCase):
    def test_round_trip_on_every_table_entry(self):
        for table in (fingers.FIST, fingers.OPEN):
            for m in table.values():
                r = fingers._rot_of(m)
                r2 = fingers.quat_to_rot(fingers.quat_from_rot(r))
                for a, b in zip(r, r2):
                    self.assertAlmostEqual(a, b, places=5)

    def test_slerp_endpoints(self):
        q1 = fingers.quat_from_rot((1, 0, 0, 0, 1, 0, 0, 0, 1))
        # 90 degrees about Z (proper rotation, det +1)
        q2 = fingers.quat_from_rot((0, -1, 0, 1, 0, 0, 0, 0, 1))
        for t, q in ((0.0, q1), (1.0, q2)):
            out = fingers.slerp(q1, q2, t)
            for a, b in zip(out, q):
                self.assertAlmostEqual(a, b, places=5)

    def test_slerp_midpoint_angle_halved(self):
        q1 = fingers.quat_from_rot((1, 0, 0, 0, 1, 0, 0, 0, 1))
        # 90 degrees about Z (proper rotation, det +1)
        q2 = fingers.quat_from_rot((0, -1, 0, 1, 0, 0, 0, 0, 1))
        d_full = abs(sum(x * y for x, y in zip(q1, q2)))
        # pin the test data: a 90-degree rotation is pi/4 in quaternion space
        self.assertAlmostEqual(math.acos(min(1.0, d_full)), math.pi / 4.0,
                               places=5)
        mid = fingers.slerp(q1, q2, 0.5)
        d_mid = abs(sum(x * y for x, y in zip(q1, mid)))
        # the midpoint sits exactly halfway along the arc
        self.assertAlmostEqual(math.acos(min(1.0, d_mid)),
                               math.acos(min(1.0, d_full)) / 2.0, places=5)


class TestGrasp(unittest.TestCase):
    def test_rotation_parts_orthonormal(self):
        # guards the 4x4 layout: a mis-placed 3x3 is not orthonormal
        for bone in fingers.FINGER_BONES:
            m = fingers.preset_matrix("grasp", bone)
            r = fingers._rot_of(m)
            rows = [r[i * 3:i * 3 + 3] for i in range(3)]
            for a in rows:
                self.assertAlmostEqual(
                    math.sqrt(sum(v * v for v in a)), 1.0, places=4, msg=bone)
            for i in range(3):
                for j in range(i + 1, 3):
                    self.assertAlmostEqual(
                        sum(x * y for x, y in zip(rows[i], rows[j])),
                        0.0, places=4, msg=bone)

    def test_midpoint_property(self):
        # well-conditioned (FIST<->OPEN 8.7-50.9 deg per bone): the
        # midpoint sits exactly halfway on both sides
        for bone in fingers.FINGER_BONES:
            f = fingers.preset_matrix("fist", bone)
            o = fingers.preset_matrix("open", bone)
            g = fingers.preset_matrix("grasp", bone)
            self.assertEqual(len(g), 16, bone)
            for i in (3, 7, 11):
                self.assertAlmostEqual(g[i], 0.5 * (f[i] + o[i]), places=6,
                                       msg=bone)
            af, ao = _quat_angle(f, g), _quat_angle(o, g)
            self.assertAlmostEqual(af, ao, places=5, msg=bone)
            self.assertAlmostEqual(af, _quat_angle(f, o) / 2.0, places=4,
                                   msg=bone)

    def test_table_passthrough(self):
        for bone in fingers.FINGER_BONES:
            self.assertEqual(fingers.preset_matrix("fist", bone),
                             fingers.FIST[bone])
            self.assertEqual(fingers.preset_matrix("open", bone),
                             fingers.OPEN[bone])

    def test_errors(self):
        with self.assertRaises(JkaError):
            fingers.preset_matrix("nope", "l_d1_j1")
        with self.assertRaises(JkaError):
            fingers.preset_matrix("fist", "pelvis")


if __name__ == "__main__":
    unittest.main()
