# SPDX-License-Identifier: MIT
"""B3: finger preset core (bpy-free).

The 12 engine finger bones (6 per hand: d1/d2/d4 x j1/j2) are fiddly to
key by hand, so the suite presets them to three canonical positions.

The tables hold HAND-RELATIVE joint matrices (4x4, row-major, 16
floats): REL_b = M_parent^-1 @ M_b with M in absolute armature space,
parent = the hand bone (lhand/rhand) for _j1 bones and the _j1 bone
for _j2 bones. Absolute matrices are the WRONG representation (finding
F1): they embed the authoring segment's hand/arm placement, so applied
to a rig whose arm is posed differently they teleport the fingers off
the hand. Hand-relative matrices curl the fingers around wherever the
hand currently is.

Provenance (decision #18): derived on the gdesk VM through the suite's
verified importer (blender/b3_finger_derive.py, Blender 5.3.0), then
built in-container from the printed absolute tables by
openjk-support plans/artifacts/finger_build.py. Do not recompute
unless the derive is re-run.
- fist = BOTH_P6_S6_TR @ pool frame 10370 — the right hand grips the
  blaster (render-verified clenched grip; the most-closed clean hand
  in the stock library). The left side is the rig's mirror (F5), not
  the segment's own left hand (which reads deformed at that frame).
- open = BOTH_STAND1 @ pool frame 14578 — the stock relaxed
  weapon-stand hand, both hands from data (render-verified: drooping,
  slightly curled, clean).
- grasp = per-bone quaternion slerp midpoint (t=0.5) of the FIST/OPEN
  rotations + translation midpoint, computed here (bpy-free). FIST
  <-> OPEN angles are 8.7-50.9 degrees per bone: well-conditioned, no
  antipodal quaternions.

Apply contract (the bpy face, fingerops.py): per hand, in
topological order [d1_j1, d1_j2, d2_j1, d2_j2, d4_j1, d4_j2],
M_target = M_parent @ REL_b where M_parent is the hand's evaluated
pose matrix (read once before the hand's loop) for _j1 bones and the
bone's j1 TARGET for _j2 bones (a deterministic chain, not the live
parent); pb.matrix = M_target. The hand bones are never touched.

Findings on the record (2026-11-18 VM derivation; condensed — they
prevent the next person from re-deriving the wrong thing):
- F1: absolute armature-space tables are wrong — the hand placement
  leaks into the finger data; the first (absolute) design failed on a
  posed rig. Hand-relative is the fix.
- F2: BOTH_STAND1 and BOTH_WALK1 have IDENTICAL finger poses (the
  hand-relative tables derived from them are equal to 6 decimals for
  all 12 bones; raw GLA locals differ by 0.00 degrees). The visible
  difference between those segments is hand orientation, not finger
  flexion — the earlier "fist vs open" render verdict was expectation
  bias. Judge hands on fresh renders each time.
- F3: the GLA pool local matrix L_b IS the joint curl — the parent is
  already baked in. L_b @ L_p^-1 (bone vs grandparent) measures the
  HAND rotation, not the finger: the first re-selection scan ranked
  by hand orientation and produced a rigid-hand fingerprint (~89
  degrees uniform per hand, mirror pairs scoring as "different" —
  e.g. FORCEWALLRELEASE_FORWARD vs _RIGHT). The corrected local-based
  scan found 61-104 distinct rotations per bone across the 1663
  segments' first frames.
- F4: no stock segment poses both hands clenched — one hand always
  grips, the other stays open/relaxed (candidate renders, vision-
  judged on the sheng_roshdark model: force-hold frames read
  deformed, FORCEWALLRELEASE hands claw-splayed, THROW blocky).
  Hence fist = the clean right-hand blaster grip of P6_S6_TR @ 10370
  + its rig mirror (F5).
- F5: the IK_Rig rest matrices mirror exactly: M_r = C M_l D for all
  14 bones (12 fingers + 2 hands), C = diag(-1,1,1), D = diag(1,1,-1)
  (a consistent per-bone axis-convention flip). For hand-relative
  targets this reduces to REL_l = D4 REL_r D4 with D4 = 4x4
  diag(1,1,-1,1) — the FIST table's left side was built that way (the
  tests pin it exactly).
"""
import math

from .common import JkaError

FINGER_BONES = (
    "l_d1_j1", "l_d1_j2", "l_d2_j1", "l_d2_j2", "l_d4_j1", "l_d4_j2",
    "r_d1_j1", "r_d1_j2", "r_d2_j1", "r_d2_j2", "r_d4_j1", "r_d4_j2",
)

# The bone each finger bone's REL table is relative to: _j1 parent =
# the hand, _j2 parent = its _j1 (topological order: FINGER_BONES).
PARENT_BONE = {
    "l_d1_j1": "lhand", "l_d1_j2": "l_d1_j1",
    "l_d2_j1": "lhand", "l_d2_j2": "l_d2_j1",
    "l_d4_j1": "lhand", "l_d4_j2": "l_d4_j1",
    "r_d1_j1": "rhand", "r_d1_j2": "r_d1_j1",
    "r_d2_j1": "rhand", "r_d2_j2": "r_d2_j1",
    "r_d4_j1": "rhand", "r_d4_j2": "r_d4_j1",
}

HAND_BONES = ("lhand", "rhand")

# provenance: (segment, pool frame) in models/players/_humanoid (LIVE
# GLA, current per Sheng 2026-11-18 — no changes since 11-17)
PRESET_SOURCES = {
    "fist": ("BOTH_P6_S6_TR", 10370),
    "open": ("BOTH_STAND1", 14578),
}

# Hand-relative tables (see module docstring): 4x4 row-major, REL_b =
# M_parent^-1 @ M_b. Built by plans/artifacts/finger_build.py from the
# VM-derived absolute matrices.
FIST = {
    "l_d1_j1": (-0.712440, -0.013435, -0.701605, 0.855628, 0.496811, 0.696450, -0.517820, 0.778434, 0.495590, -0.717480, -0.489504, -0.288027, 0.000000, 0.000000, 0.000000, 1.000000),
    "l_d1_j2": (0.662258, 0.664940, -0.345358, -0.001472, -0.615820, 0.745598, 0.254655, 1.538287, 0.426827, 0.044031, 0.903261, 0.004465, 0.000000, 0.000000, 0.000000, 1.000000),
    "l_d2_j1": (-0.025802, 0.053978, 0.998209, 0.705402, -0.994411, 0.100885, -0.031159, 3.409515, -0.102387, -0.993434, 0.051073, 0.124120, 0.000000, 0.000000, 0.000000, 1.000000),
    "l_d2_j2": (-0.388800, 0.921323, -0.000175, 0.008021, -0.921249, -0.388769, -0.012712, 1.316693, -0.011781, -0.004782, 0.999919, 0.001765, 0.000000, 0.000000, 0.000000, 1.000000),
    "l_d4_j1": (0.082333, 0.148725, 0.985446, -0.625405, -0.995806, -0.027311, 0.087321, 3.380314, 0.039900, -0.988502, 0.145851, -0.017069, 0.000000, 0.000000, 0.000000, 1.000000),
    "l_d4_j2": (-0.476732, 0.879049, 0.000230, 0.004877, -0.878601, -0.476480, -0.032057, 1.259748, -0.028071, -0.015485, 0.999486, 0.008096, 0.000000, 0.000000, 0.000000, 1.000000),
    "r_d1_j1": (-0.712440, -0.013435, 0.701605, 0.855628, 0.496811, 0.696450, 0.517820, 0.778434, -0.495590, 0.717480, -0.489504, 0.288027, 0.000000, 0.000000, 0.000000, 1.000000),
    "r_d1_j2": (0.662258, 0.664940, 0.345358, -0.001472, -0.615820, 0.745598, -0.254655, 1.538287, -0.426827, -0.044031, 0.903261, -0.004465, 0.000000, 0.000000, 0.000000, 1.000000),
    "r_d2_j1": (-0.025802, 0.053978, -0.998209, 0.705402, -0.994411, 0.100885, 0.031159, 3.409515, 0.102387, 0.993434, 0.051073, -0.124120, 0.000000, 0.000000, 0.000000, 1.000000),
    "r_d2_j2": (-0.388800, 0.921323, 0.000175, 0.008021, -0.921249, -0.388769, 0.012712, 1.316693, 0.011781, 0.004782, 0.999919, -0.001765, 0.000000, 0.000000, 0.000000, 1.000000),
    "r_d4_j1": (0.082333, 0.148725, -0.985446, -0.625405, -0.995806, -0.027311, -0.087321, 3.380314, -0.039900, 0.988502, 0.145851, 0.017069, 0.000000, 0.000000, 0.000000, 1.000000),
    "r_d4_j2": (-0.476732, 0.879049, -0.000230, 0.004877, -0.878601, -0.476480, 0.032057, 1.259748, 0.028071, 0.015485, 0.999486, -0.008096, 0.000000, 0.000000, 0.000000, 1.000000),
}

OPEN = {
    "l_d1_j1": (-0.797302, 0.374974, -0.472975, 0.847669, 0.566426, 0.735522, -0.371711, 0.759650, 0.208502, -0.564271, -0.798827, -0.296788, 0.000000, 0.000000, 0.000000, 1.000000),
    "l_d1_j2": (0.802316, 0.422330, -0.421815, 0.006826, -0.364544, 0.906266, 0.213987, 1.535381, 0.472648, -0.017914, 0.881069, -0.000627, 0.000000, 0.000000, 0.000000, 1.000000),
    "l_d2_j1": (-0.030134, 0.073944, 0.996807, 0.710982, -0.700658, 0.709667, -0.073826, 3.379818, -0.712861, -0.700646, 0.030425, 0.112050, 0.000000, 0.000000, 0.000000, 1.000000),
    "l_d2_j2": (0.981022, 0.193900, -0.000353, -0.014974, -0.193887, 0.980940, -0.012835, 1.309090, -0.002142, 0.012658, 0.999918, -0.004728, 0.000000, 0.000000, 0.000000, 1.000000),
    "l_d4_j1": (0.187658, -0.019997, 0.982031, -0.626717, -0.812565, 0.558540, 0.166646, 3.358666, -0.551836, -0.829236, 0.088565, -0.031590, 0.000000, 0.000000, 0.000000, 1.000000),
    "l_d4_j2": (0.821290, 0.570510, 0.000161, -0.014850, -0.570208, 0.820864, -0.032360, 1.261786, -0.018592, 0.026485, 0.999476, -0.003676, 0.000000, 0.000000, 0.000000, 1.000000),
    "r_d1_j1": (-0.797304, 0.374988, 0.472960, 0.846797, 0.566454, 0.735454, 0.371804, 0.764273, -0.208418, 0.564350, -0.798795, 0.294337, 0.000000, 0.000000, 0.000000, 1.000000),
    "r_d1_j2": (0.802279, 0.422477, 0.421737, 0.000002, -0.364671, 0.906196, -0.214065, 1.535950, -0.472613, 0.017944, 0.881089, 0.000003, 0.000000, 0.000000, 0.000000, 1.000000),
    "r_d2_j1": (-0.030014, 0.073962, -0.996810, 0.706452, -0.700650, 0.709683, 0.073754, 3.388525, 0.712875, 0.700628, 0.030522, -0.124594, 0.000000, 0.000000, 0.000000, 1.000000),
    "r_d2_j2": (0.981017, 0.193924, 0.000236, -0.000012, -0.193910, 0.980936, 0.012819, 1.311953, 0.002255, -0.012620, 0.999918, 0.000005, 0.000000, 0.000000, 0.000000, 1.000000),
    "r_d4_j1": (0.187658, -0.019996, -0.982031, -0.628690, -0.812565, 0.558540, -0.166649, 3.367731, 0.551837, 0.829237, 0.088568, 0.019039, 0.000000, 0.000000, 0.000000, 1.000000),
    "r_d4_j2": (0.821296, 0.570504, -0.000121, -0.000010, -0.570203, 0.820872, 0.032246, 1.267176, 0.018496, -0.026414, 0.999480, 0.000002, 0.000000, 0.000000, 0.000000, 1.000000),
}

_TABLES = {"fist": FIST, "open": OPEN}
NAMES = tuple(_TABLES) + ("grasp",)


def _rot_of(m16):
    """The 3x3 rotation part of a row-major 16-float 4x4 (9-tuple)."""
    return tuple(m16[i] for i in (0, 1, 2, 4, 5, 6, 8, 9, 10))


def quat_from_rot(r):
    """(w, x, y, z) from a row-major 3x3 (9-tuple), Shepperd's method."""
    m00, m01, m02, m10, m11, m12, m20, m21, m22 = r
    tr = m00 + m11 + m22
    if tr > 0.0:
        s = math.sqrt(tr + 1.0) * 2.0
        w = 0.25 * s
        x = (m21 - m12) / s
        y = (m02 - m20) / s
        z = (m10 - m01) / s
    elif m00 > m11 and m00 > m22:
        s = math.sqrt(1.0 + m00 - m11 - m22) * 2.0
        w = (m21 - m12) / s
        x = 0.25 * s
        y = (m01 + m10) / s
        z = (m02 + m20) / s
    elif m11 > m22:
        s = math.sqrt(1.0 + m11 - m00 - m22) * 2.0
        w = (m02 - m20) / s
        x = (m01 + m10) / s
        y = 0.25 * s
        z = (m12 + m21) / s
    else:
        s = math.sqrt(1.0 + m22 - m00 - m11) * 2.0
        w = (m10 - m01) / s
        x = (m02 + m20) / s
        y = (m12 + m21) / s
        z = 0.25 * s
    n = math.sqrt(w * w + x * x + y * y + z * z)
    return (w / n, x / n, y / n, z / n)


def quat_to_rot(q):
    """Row-major 3x3 (9-tuple) from (w, x, y, z)."""
    w, x, y, z = q
    return (
        1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - w * z),
        2.0 * (x * z + w * y),
        2.0 * (x * y + w * z), 1.0 - 2.0 * (x * x + z * z),
        2.0 * (y * z - w * x),
        2.0 * (x * z - w * y), 2.0 * (y * z + w * x),
        1.0 - 2.0 * (x * x + y * y),
    )


def slerp(qa, qb, t):
    """Quaternion slerp at t (0..1), shortest arc."""
    dot = qa[0] * qb[0] + qa[1] * qb[1] + qa[2] * qb[2] + qa[3] * qb[3]
    if dot < 0.0:
        qb = tuple(-v for v in qb)
        dot = -dot
    if dot > 0.9995:  # nearly parallel: lerp + normalize
        out = tuple(a + t * (b - a) for a, b in zip(qa, qb))
    else:
        th = math.acos(max(-1.0, min(1.0, dot)))
        s = math.sin(th)
        w0 = math.sin((1.0 - t) * th) / s
        w1 = math.sin(t * th) / s
        out = tuple(w0 * a + w1 * b for a, b in zip(qa, qb))
    n = math.sqrt(sum(v * v for v in out))
    return tuple(v / n for v in out)


def preset_matrix(name, bone):
    """The target REL 16-float row-major matrix for `bone` under
    `name` ('fist' / 'open' / 'grasp'). JkaError on unknown
    preset/bone. The value is the hand-relative joint matrix — apply
    it per the contract in the module docstring (fingerops does)."""
    if name not in NAMES:
        raise JkaError(f"unknown finger preset: {name!r} "
                       f"(expected one of {', '.join(NAMES)})")
    if bone not in FINGER_BONES:
        raise JkaError(f"not an engine finger bone: {bone!r}")
    if name == "grasp":
        f, o = FIST[bone], OPEN[bone]
        q = slerp(quat_from_rot(_rot_of(f)), quat_from_rot(_rot_of(o)), 0.5)
        r = quat_to_rot(q)
        # row-major 4x4: rotation @ 0,1,2,4,5,6,8,9,10; translation @ 3,7,11
        out = [0.0] * 16
        out[0], out[1], out[2] = r[0], r[1], r[2]
        out[4], out[5], out[6] = r[3], r[4], r[5]
        out[8], out[9], out[10] = r[6], r[7], r[8]
        out[3] = 0.5 * (f[3] + o[3])
        out[7] = 0.5 * (f[7] + o[7])
        out[11] = 0.5 * (f[11] + o[11])
        out[12], out[13], out[14], out[15] = 0.0, 0.0, 0.0, 1.0
        return tuple(out)
    return _TABLES[name][bone]
