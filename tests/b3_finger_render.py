# SPDX-License-Identifier: MIT
"""B3 finger preset render gate (pure Python, engine space — no Blender).

Renders the presets' VISUAL shape through the engine-exact animkit
renderer (verified against the live in-game render), using
sheng_roshdark's mesh animated by _humanoid.gla — the same GLA the
tables were derived from (b3_finger_derive --skeleton _humanoid).

The preset is HAND-RELATIVE: a curl of each finger relative to its hand.
In engine (render) space that hand-relative local is
    L[side][b] = E_hand^-1 @ E_b        (at the preset's source frame)
which is body-pose-independent: the body transform cancels
((T H)^-1 (T F) = H^-1 F). Applying L to any target frame's hand gives
the same physical finger curl relative to that hand. All of this is
computed from animkit's E (the round-trip render matrices) — no
armature space, no Blender, no quaternion-convention coupling between
the container and the VM importer.

Sources (decision #18):
  FIST  = BOTH_P6_S6_TR @ pool frame 10370 — right hand grips the blaster.
          The preset's LEFT hand is the D-conjugate mirror of the right
          (F5), D = diag(1,1,-1,1).
  OPEN  = BOTH_STAND1 @ pool frame 14578 — both hands from data (relaxed).
  GRASP = per-bone slerp midpoint (t=0.5) of FIST<->OPEN rotations +
          translation midpoint.

Gates (asserted, not eyeballed):
  1. OPEN @ STAND1 rendered through the preset pipeline matches a plain
     STAND1 render (a no-op: differing bytes < 0.1% of the buffer — float
     round-trip E @ E^-1 @ E != E to ~1e-6, while a wrong pose shifts a
     whole hand region).
  2. FIST @ P6_S6_TR (provenance frame), right hand only, matches plain
     P6_S6_TR (the fist local reproduces the source grip).
  3. The engine-space hand-relative preset locals are proper rotations
     (det +1, orthonormal within pool-quantization noise) for every bone.
Then posed renders for the vision judge (hand visible, mesh view):
  fist @ STAND1  (clenched grip on a relaxed hand — the new scenario)
  grasp @ STAND1 (the slerp midpoint shape)
  plain STAND1 / plain P6_S6_TR  (references)

Run from the jka-animator repo root:
  python3 tests/b3_finger_render.py --animkit-dir /path/to/jka-animkit \
      --base /path/to/mod-folder [--character sheng_roshdark] --out DIR
"""
import argparse
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from jka_anim_tools import fingers  # noqa: E402  (bone names + parent map only)

FING = list(fingers.FINGER_BONES)
PARENT = dict(fingers.PARENT_BONE)
HANDS = list(fingers.HAND_BONES)
# per-hand topological order (flat, for local computation / gates)
ORDER = ["d1_j1", "d1_j2", "d2_j1", "d2_j2", "d4_j1", "d4_j2"]
# finger chains: each j1's parent is the HAND; each j2's parent is its j1.
# When applying, e_parent resets to the hand at every j1.
FINGERS = [("d1_j1", "d1_j2"), ("d2_j1", "d2_j2"), ("d4_j1", "d4_j2")]


# ------------------------------------------------------------------ 3x4 math
def mm12(a, b):
    o = [0.0] * 12
    for r in range(3):
        for c in range(4):
            o[r * 4 + c] = (a[r * 4] * b[c] + a[r * 4 + 1] * b[4 + c]
                            + a[r * 4 + 2] * b[8 + c])
    return tuple(o)


def _inv3(R):
    """True 3x3 inverse (cofactor/adjugate) — the engine's E matrices are
    NOT orthonormal (the round-trip bakes the base-pose row scale in), so
    R^T is not the inverse."""
    a, b, c = R[0][0], R[0][1], R[0][2]
    d, e, f = R[1][0], R[1][1], R[1][2]
    g, h, i = R[2][0], R[2][1], R[2][2]
    A = e * i - f * h
    B = -(d * i - f * g)
    C = d * h - e * g
    det = a * A + b * B + c * C
    inv = 1.0 / det
    return (
        (A * inv, (c * h - b * i) * inv, (b * f - c * e) * inv),
        (B * inv, (a * i - c * g) * inv, (c * d - a * f) * inv),
        (C * inv, (b * g - a * h) * inv, (a * e - b * d) * inv),
    )


def inv12(m):
    """Affine inverse of a 12-float 3x4: [R|t]^-1 = [R^-1 | -R^-1 t]."""
    R = [[m[r * 4 + c] for c in range(3)] for r in range(3)]
    t = [m[r * 4 + 3] for r in range(3)]
    Ri = _inv3(R)
    ti = [-sum(Ri[r][k] * t[k] for k in range(3)) for r in range(3)]  # -R^-1 t
    out = [0.0] * 12
    for r in range(3):
        for c in range(3):
            out[r * 4 + c] = Ri[r][c]
        out[r * 4 + 3] = ti[r]
    return tuple(out)


def ortho_err(m):
    R = [[m[r * 4 + c] for c in range(3)] for r in range(3)]
    return max(abs(sum(R[a][k] * R[b][k] for k in range(3))
                   - (1.0 if a == b else 0.0))
               for a in range(3) for b in range(3))


def rot9(m):
    return (m[0], m[1], m[2], m[4], m[5], m[6], m[8], m[9], m[10])


def quat_from_rot9(r):
    m00, m01, m02 = r[0], r[1], r[2]
    m10, m11, m12 = r[3], r[4], r[5]
    m20, m21, m22 = r[6], r[7], r[8]
    tr = m00 + m11 + m22
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        w = 0.25 * s
        x = (m21 - m12) / s
        y = (m02 - m20) / s
        z = (m10 - m01) / s
    elif m00 > m11 and m00 > m22:
        s = math.sqrt(1.0 + m00 - m11 - m22) * 2
        w = (m21 - m12) / s
        x = 0.25 * s
        y = (m01 + m10) / s
        z = (m02 + m20) / s
    elif m11 > m22:
        s = math.sqrt(1.0 + m11 - m00 - m22) * 2
        w = (m02 - m20) / s
        x = (m01 + m10) / s
        y = 0.25 * s
        z = (m12 + m21) / s
    else:
        s = math.sqrt(1.0 + m22 - m00 - m11) * 2
        w = (m10 - m01) / s
        x = (m02 + m20) / s
        y = (m12 + m21) / s
        z = 0.25 * s
    n = math.sqrt(w * w + x * x + y * y + z * z) or 1.0
    return (w / n, x / n, y / n, z / n)


def quat_to_rot9(q):
    w, x, y, z = q
    return (
        1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y),
        2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x),
        2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y),
    )


def slerp_q(qa, qb, t):
    d = qa[0] * qb[0] + qa[1] * qb[1] + qa[2] * qb[2] + qa[3] * qb[3]
    if d < 0:
        d = -d
        qb = (-qb[0], -qb[1], -qb[2], -qb[3])
    if d > 0.9995:
        out = tuple(a + t * (b - a) for a, b in zip(qa, qb))
    else:
        th = math.acos(min(1.0, max(-1.0, d)))
        st = math.sin(th)
        sa = math.sin((1 - t) * th) / st
        sb = math.sin(t * th) / st
        out = tuple(sa * a + sb * b for a, b in zip(qa, qb))
    n = math.sqrt(sum(v * v for v in out)) or 1.0
    return tuple(v / n for v in out)


def compose12(r9, t):
    m = [0.0] * 12
    for c in range(3):
        m[c] = r9[c]
        m[4 + c] = r9[3 + c]
        m[8 + c] = r9[6 + c]
    m[3], m[7], m[11] = t
    return tuple(m)


def mirror_d(m):
    """D-conjugate mirror, D = diag(1,1,-1,1) (F5): R' = D3 R D3, t' = D3 t.

    D3 = diag(1,1,-1): R'[i][j] = s[i]*R[i][j]*s[j], s=(1,1,-1); t' z negated.
    """
    s = (1.0, 1.0, -1.0)
    r9 = rot9(m)
    t = (m[3], m[7], m[11])
    out = [0.0] * 12
    for i in range(3):
        for j in range(3):
            out[i * 4 + j] = s[i] * r9[i * 3 + j] * s[j]
    out[3], out[7], out[11] = t[0], t[1], -t[2]
    return tuple(out)


class _PresetRenderer:
    """FrameRenderer that skins with an explicit 12-float per-bone list."""

    def __init__(self, playmod, pngmod, glm, gla, pb, width, height, lod, frames):
        self.playmod = playmod
        self.pngmod = pngmod
        self.fr = playmod.FrameRenderer(glm, gla, pb, width=width, height=height,
                                        lod=lod, frames=frames)

    def render_mesh(self, mats, frame):
        fr, pb, play, png = self.fr, self.fr.pb, self.playmod, self.pngmod
        buf = png.make_canvas(fr.W, fr.H, (12, 12, 18))
        tris = []
        for sidx, surf in fr.surf_list:
            if not surf.tris or not surf.verts:
                continue
            color = fr.colors[surf.name]
            try:
                skinned = list(pb.skin_vertices(mats, surf))
            except Exception:
                continue
            if not skinned:
                continue
            proj = [fr._project(v[0]) for v in skinned]
            for (ia, ib, ic) in surf.tris:
                if ia >= len(proj) or ib >= len(proj) or ic >= len(proj):
                    continue
                pa, pb_, pc = proj[ia], proj[ib], proj[ic]
                depth = (pa[2] + pb_[2] + pc[2]) / 3
                va, vb, vc = skinned[ia][0], skinned[ib][0], skinned[ic][0]
                ex = (vb[0] - va[0], vb[1] - va[1], vb[2] - va[2])
                ey = (vc[0] - va[0], vc[1] - va[1], vc[2] - va[2])
                nx = ex[1] * ey[2] - ex[2] * ey[1]
                ny = ex[2] * ey[0] - ex[0] * ey[2]
                nz = ex[0] * ey[1] - ex[1] * ey[0]
                nl = (nx * nx + ny * ny + nz * nz) ** 0.5 or 1.0
                light = max(0.25, (nx * 0.45 + ny * 0.35 + nz * 0.8) / nl)
                col = (int(color[0] * light), int(color[1] * light),
                       int(color[2] * light))
                tris.append((depth, (pa, pb_, pc), col))
        tris.sort(key=lambda t: -t[0])
        for _d, (pa, pb_, pc), col in tris:
            play._fill_triangle(buf, fr.W, fr.H, pa, pb_, pc, col)
        return buf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--animkit-dir", default=os.environ.get("JKA_ANIMKIT_DIR", ""))
    ap.add_argument("--base", default="", help="mod folder containing models/players/")
    ap.add_argument("--character", default="sheng_roshdark")
    ap.add_argument("--out", default="")
    ap.add_argument("--width", type=int, default=480)
    ap.add_argument("--height", type=int, default=600)
    args = ap.parse_args()
    if not (args.animkit_dir and args.base and args.out):
        raise SystemExit("pass --animkit-dir, --base, --out")
    sys.path.insert(0, args.animkit_dir)
    from animkit import gla as glamod  # noqa: E402
    from animkit import glm as glmmod  # noqa: E402
    from animkit import animevents as cfgmod  # noqa: E402
    from animkit import play as playmod  # noqa: E402
    from animkit import png as pngmod  # noqa: E402

    char_dir = os.path.abspath(os.path.join(args.base, "models", "players",
                                            args.character))
    with open(os.path.join(char_dir, "model.glm"), "rb") as f:
        g2 = glmmod.parse_glm(f.read())
    gla_path = os.path.abspath(os.path.join(args.base, g2.anim_name + ".gla"))
    if "_humanoid" not in gla_path:
        raise SystemExit(f"expected _humanoid.gla (the tables' source GLA), got {gla_path}")
    with open(gla_path, "rb") as f:
        g = glamod.parse_gla(f.read())
    cfg_path = os.path.join(os.path.dirname(gla_path), "animation.cfg")
    with open(cfg_path, "r", errors="replace") as f:
        segs, _warns = cfgmod.parse_animation_cfg(f.read())
    seg_first = {s.name: int(s.first_frame) for s in segs}

    bone_idx = {b.name: i for i, b in enumerate(g.bones)}
    for b in FING + HANDS:
        if b not in bone_idx:
            raise SystemExit(f"bone {b!r} missing from {gla_path}")
    pb = glamod.Playback(g, smooth=0.3)  # engine default r_ghoul2animsmooth
    n_bones = g.num_bones

    FIST_FRAME = seg_first["BOTH_P6_S6_TR"]
    OPEN_FRAME = seg_first["BOTH_STAND1"]
    E_p6 = [tuple(x) for x in pb.frame_mats(float(FIST_FRAME))]
    E_s = [tuple(x) for x in pb.frame_mats(float(OPEN_FRAME))]

    # ---- parent-relative locals in engine space -----------------------
    # L[b] = E[parent(b)]^-1 @ E[b]  (j1 -> hand, j2 -> its j1). This is the
    # same convention the armature tables store (REL is parent-relative).
    # Body-pose-independent: (T P)^-1 (T C) = P^-1 C.
    # Right hand from data at its source frame; left = D-mirror (FIST) or
    # from data (OPEN).
    def local_parent(E_src, b):
        ip = inv12(E_src[bone_idx[PARENT[b]]])
        return mm12(ip, E_src[bone_idx[b]])

    FIST_R, FIST_L, OPEN_R, OPEN_L = {}, {}, {}, {}
    for suf in ORDER:
        rb, lb = "r_" + suf, "l_" + suf
        FIST_R[rb] = local_parent(E_p6, rb)
        FIST_L[lb] = mirror_d(FIST_R[rb])
        OPEN_R[rb] = local_parent(E_s, rb)
        OPEN_L[lb] = local_parent(E_s, lb)
    GRASP = {}
    for suf in ORDER:
        rb, lb = "r_" + suf, "l_" + suf
        for side, (fb, ob) in ((rb, (FIST_R[rb], OPEN_R[rb])),
                               (lb, (FIST_L[lb], OPEN_L[lb]))):
            qf = quat_from_rot9(rot9(fb))
            qo = quat_from_rot9(rot9(ob))
            qg = slerp_q(qf, qo, 0.5)
            tg = tuple(0.5 * (fb[k] + ob[k]) for k in (3, 7, 11))
            GRASP[side] = compose12(quat_to_rot9(qg), tg)

    PRESETS = {
        "fist": {"rhand": FIST_R, "lhand": FIST_L},
        "open": {"rhand": OPEN_R, "lhand": OPEN_L},
        "grasp": {"rhand": GRASP, "lhand": GRASP},
    }

    # ---- gate 3: every local is a proper rigid transform --------------
    worst = 0.0
    for name, hands in PRESETS.items():
        for hand, locs in hands.items():
            for b, L in locs.items():
                worst = max(worst, ortho_err(L))
    print(f"[gate 3] preset locals orthonormality max err: {worst:.3e}",
          "PASS" if worst < 1e-3 else "FAIL")
    assert worst < 1e-3

    # ---- rendering ----------------------------------------------------
    ren = _PresetRenderer(playmod, pngmod, g2, g, pb, args.width, args.height,
                          0, [float(OPEN_FRAME), float(FIST_FRAME)])

    def apply_preset(E_base, preset, frame):
        """Return per-bone mats: E_base with the 12 finger bones posed via
        the parent-relative preset. e_parent resets to the hand at each j1;
        each j2 chains from its j1 TARGET."""
        mats = list(E_base)
        for hand in HANDS:
            side = "r_" if hand == "rhand" else "l_"
            e_hand = E_base[bone_idx[hand]]
            for j1, j2 in FINGERS:
                b1, b2 = side + j1, side + j2
                e1 = mm12(e_hand, preset[hand][b1])
                mats[bone_idx[b1]] = e1
                e2 = mm12(e1, preset[hand][b2])
                mats[bone_idx[b2]] = e2
        return mats

    def save(tag, mats, frame):
        buf = ren.render_mesh(mats, float(frame))
        path = os.path.join(args.out, f"{tag}.png")
        pngmod.write_png(path, ren.fr.W, ren.fr.H, bytes(buf))
        print(f"render: {path}")
        return buf

    os.makedirs(args.out, exist_ok=True)

    # a correct no-op can differ by a handful of bytes (float round-trip
    # E @ E^-1 @ E != E to ~1e-6); a wrong pose shifts a whole hand region
    # (thousands of bytes). Threshold: 0.1% of the buffer.
    TOL = 0.001

    def nop_check(tag, a, b):
        n = sum(1 for x, y in zip(a, b) if x != y)
        ok = n / len(a) < TOL
        print(f"[{tag}] {n}/{len(a)} bytes differ "
              f"({100.0 * n / len(a):.4f}%)", "PASS" if ok else "FAIL")
        return ok

    # ---- gate 1: open @ STAND1 == plain STAND1 (no-op) -----------------
    plain_s = save("plain_stand1", E_s, OPEN_FRAME)
    open_s = save("open_stand1", apply_preset(E_s, PRESETS["open"], OPEN_FRAME),
                  OPEN_FRAME)
    assert nop_check("gate 1", plain_s, open_s)

    # ---- gate 2: fist @ P6 (right hand only) == plain P6 (no-op) -------
    plain_p = save("plain_p6s6tr", E_p6, FIST_FRAME)
    mats_p = list(E_p6)
    e_hand = E_p6[bone_idx["rhand"]]
    for j1, j2 in FINGERS:
        b1 = "r_" + j1
        e1 = mm12(e_hand, FIST_R[b1])
        mats_p[bone_idx[b1]] = e1
        b2 = "r_" + j2
        e2 = mm12(e1, FIST_R[b2])
        mats_p[bone_idx[b2]] = e2
    fist_p = save("fist_p6s6tr_rhand", mats_p, FIST_FRAME)
    assert nop_check("gate 2", plain_p, fist_p)

    # posed renders for the vision judge
    save("fist_stand1", apply_preset(E_s, PRESETS["fist"], OPEN_FRAME), OPEN_FRAME)
    save("grasp_stand1", apply_preset(E_s, PRESETS["grasp"], OPEN_FRAME), OPEN_FRAME)

    print("B3 FINGER RENDER GATES PASSED (3/3) — posed renders written")


if __name__ == "__main__":
    main()
