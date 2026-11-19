# SPDX-License-Identifier: MIT
"""b3_finger_apply_check.py — B3 headless apply driver (the gate that
proves the finger preset apply).

Registers the addon and drives jka_anim.finger_preset via bpy.ops exactly
like the N-panel would, on the rig's armature (nla.find_armature — the
object named 'skeleton_root'), then reads back the evaluated joint
rotation for each of the 12 finger bones and asserts it equals the
target REL rotation from the core tables. Optionally renders the posed
rig (--view mesh, solid) so the hand shape can be vision-judged.

  blender --background RIG.blend \
      --addon-dir /home/hermes/.config/blender/5.3/scripts/addons \
      --python blender/b3_finger_apply_check.py -- \
      [--frame N] [--render OUTDIR]

Why the read-back uses the tables' ASSUMED parent (not the live Blender
parent): the REL tables are hand-relative with a chained convention
(j1 relative to the hand, j2 relative to its j1). Applied as
M_hand @ REL[j1] @ REL[j2], they telescope to the correct ABSOLUTE
matrix on ANY rig (flat or chained hierarchy), because pb.matrix sets the
absolute transform and Blender re-derives the local against the live
parent. Reading back with the ASSUMED parent (hand for _j1, the _j1 for
_j2) therefore recovers the REL exactly for a correct apply, on any rig;
reading back with the live parent would only match a chained rig and is
the wrong check here.

Checks (each via bpy.ops; exit 0 + 'B3 FINGER APPLY PASSED' when all hold):
  1. fist  applied, all 12 bones' read-back rotation == FIST REL
  2. open  applied, all 12 bones' read-back rotation == OPEN REL
  3. grasp applied, all 12 bones' read-back rotation == GRASP REL
  4. the hand bones were NOT touched (their matrix is unchanged by the op)
  --render: write fist/open/grasp solid renders of the posed rig for
            vision-judging (fist must read as a clenched grip).
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

FINGERS = ("l_d1_j1", "l_d1_j2", "l_d2_j1", "l_d2_j2", "l_d4_j1", "l_d4_j2",
           "r_d1_j1", "r_d1_j2", "r_d2_j1", "r_d2_j2", "r_d4_j1", "r_d4_j2")
HANDS = ("lhand", "rhand")
# per-finger (j1, j2) pairs, per hand — the chained convention
PAIRS = (("d1_j1", "d1_j2"), ("d2_j1", "d2_j2"), ("d4_j1", "d4_j2"))


def _arg(args, name, default):
    if name in args:
        i = args.index(name)
        if i + 1 < len(args):
            return args[i + 1]
    return default


def _rot3x3(m4):
    return (m4[0][0], m4[0][1], m4[0][2],
            m4[1][0], m4[1][1], m4[1][2],
            m4[2][0], m4[2][1], m4[2][2])


def _mat4(m16):
    """4x4 (mathutils-compatible tuple-of-tuples) from a flat row-major 16."""
    from mathutils import Matrix
    return Matrix((
        (m16[0], m16[1], m16[2], m16[3]),
        (m16[4], m16[5], m16[6], m16[7]),
        (m16[8], m16[9], m16[10], m16[11]),
        (m16[12], m16[13], m16[14], m16[15]),
    ))


def _angle_deg(a, b):
    """Degrees between two row-major 3x3 rotations (quaternion-dot)."""
    from jka_anim_tools import fingers
    qa = fingers.quat_from_rot(a)
    qb = fingers.quat_from_rot(b)
    d = abs(sum(x * y for x, y in zip(qa, qb)))
    d = max(-1.0, min(1.0, d))
    return math.degrees(math.acos(d))


def main():
    import bpy
    from mathutils import Matrix
    import jka_anim_tools
    from jka_anim_tools import fingers, nla, fingerops

    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    frame = _arg(args, "--frame", None)
    render_dir = _arg(args, "--render", "")

    jka_anim_tools.register()
    bind = nla.find_armature(bpy.context)
    arm = fingerops._driver_armature(bind)
    print(f"bind armature: {bind.name!r}", flush=True)
    print(f"apply/read-back armature (driver): {arm.name!r} "
          f"(data {arm.data.name!r}, {len(arm.data.bones)} bones)", flush=True)
    missing = [b for b in FINGERS + HANDS if arm.pose.bones.get(b) is None]
    if missing:
        raise SystemExit(f"apply: missing bones in {arm.name!r}: {missing}")

    if frame is not None:
        bpy.context.scene.frame_set(int(frame))

    # snapshot the hand + finger rest transforms (to prove the hands are
    # untouched and to reset between presets)
    hand_before = {h: arm.pose.bones[h].matrix.copy() for h in HANDS}
    finger_basis_before = {b: arm.pose.bones[b].matrix_basis.copy()
                           for b in FINGERS}

    failures = []

    def check(what, ok, detail=""):
        print(f"  [{'ok ' if ok else 'FAIL'}] {what}"
              + (f" — {detail}" if detail and not ok else ""), flush=True)
        if not ok:
            failures.append(what)

    def readback(preset):
        """Per-bone read-back rotation (assumed-parent convention) vs the
        core table. Returns (all_ok, worst_angle_deg, per_bone)."""
        bpy.context.view_layer.update()
        worst = 0.0
        per = {}
        for hand in HANDS:
            side = "r_" if hand == "rhand" else "l_"
            m_hand = arm.pose.bones[hand].matrix.to_4x4()
            for j1, j2 in PAIRS:
                b1, b2 = side + j1, side + j2
                m1 = arm.pose.bones[b1].matrix.to_4x4()
                m2 = arm.pose.bones[b2].matrix.to_4x4()
                # assumed parent: j1 <- hand, j2 <- its j1 (evaluated)
                rb1 = _rot3x3((m_hand.inverted() @ m1))
                rb2 = _rot3x3((m1.inverted() @ m2))
                t1 = _rot3x3(_mat4(fingers.preset_matrix(preset, b1)))
                t2 = _rot3x3(_mat4(fingers.preset_matrix(preset, b2)))
                a1 = _angle_deg(rb1, t1)
                a2 = _angle_deg(rb2, t2)
                per[b1] = a1
                per[b2] = a2
                worst = max(worst, a1, a2)
        return worst < 0.01, worst, per

    def apply_op(preset):
        bpy.context.view_layer.update()
        try:
            ret = bpy.ops.jka_anim.finger_preset(preset=preset)
            return set(ret), ""
        except RuntimeError as e:
            return {"CANCELLED"}, str(e)

    EPS = 0.01  # degrees — the read-back is a telescoping tautology, so
    # a correct apply matches to float precision; 0.01 deg is generous.

    for preset in ("fist", "open", "grasp"):
        # reset the finger bones to their snapshot basis first, so each
        # preset starts from the same base (the op is hand-relative and
        # idempotent in the hand, but reset keeps the reads clean)
        for b in FINGERS:
            arm.pose.bones[b].matrix_basis = finger_basis_before[b]
        bpy.context.view_layer.update()
        ret, msg = apply_op(preset.upper())
        check(f"{preset}: operator FINISHED",
              "FINISHED" in ret, f"ret={ret} msg={msg!r}")
        ok, worst, per = readback(preset)
        check(f"{preset}: 12-bone read-back == REL (worst {worst:.4f} deg)",
              ok, f"per-bone={ {k: round(v,4) for k,v in per.items()} }")
        if render_dir:
            _render(preset, os.path.join(render_dir, f"finger_{preset}.png"))

    # the hand bones must be unchanged (the op never touches them)
    hand_worst = 0.0
    for h in HANDS:
        a = hand_before[h]
        b = arm.pose.bones[h].matrix
        d = max(abs(a[i][j] - b[i][j]) for i in range(4) for j in range(4))
        hand_worst = max(hand_worst, d)
    check("hand bones untouched (max matrix drift)", hand_worst < 1e-4,
          f"drift={hand_worst:.3e}")

    if failures:
        print(f"B3 FINGER APPLY FAILED: {len(failures)} check(s): {failures}")
        raise SystemExit(1)
    print("B3 FINGER APPLY PASSED")


def _render(preset, out_path):
    import bpy
    # solid (BLENDER_WORKBENCH) mesh render, no wireframe, framed on the
    # character so the hands are visible
    scene = bpy.context.scene
    # hide everything except the armature-bound meshes + the armature
    for o in scene.objects:
        if o.type == 'MESH':
            o.hide_render = all(
                m.type != 'ARMATURE' for m in o.modifiers) and not any(
                g.name in FINGERS + HANDS for g in o.vertex_groups)
        elif o.type == 'CAMERA':
            o.hide_render = True
    # a camera that frames the full bounding box of the shown meshes from
    # the side (profile) so the weapon-holding hands are in frame
    import mathutils
    from mathutils import Vector
    mn = Vector((1e9, 1e9, 1e9))
    mx = Vector((-1e9, -1e9, -1e9))
    n = 0
    for o in scene.objects:
        if o.type == 'MESH' and not o.hide_render and o.data.vertices:
            for v in o.data.vertices:
                w = o.matrix_world @ v.co
                mn = Vector(map(min, mn, w))
                mx = Vector(map(max, mx, w))
                n += 1
    ctr = (mn + mx) * 0.5 if n else Vector((0, 0, 0))
    size = (mx - mn).length if n else 10.0
    cam_data = bpy.data.cameras.get("_jka_cam") or bpy.data.cameras.new("_jka_cam")
    cam_data.lens = 50
    cam = bpy.data.objects.get("_jka_cam")
    if cam is None:
        cam = bpy.data.objects.new("_jka_cam", cam_data)
        scene.collection.objects.link(cam)
    cam.hide_render = False
    # side view (along -Y looking toward +Y) with a bit of X offset so the
    # profile + weapon hands are visible; distance scales to the box
    dist = size * 1.4
    cam.location = (ctr.x + dist * 0.35, ctr.y - dist, ctr.z)
    direction = ctr - cam.location
    rot_quat = direction.to_track_quat('-Z', 'Y')
    cam.rotation_euler = rot_quat.to_euler()
    scene.camera = cam
    scene.render.engine = 'BLENDER_WORKBENCH'
    try:
        scene.display.shading.light = 'FLAT'
        scene.display.shading.color_type = 'MATERIAL'
        scene.display.shading.show_cavity = False
        scene.display.shading.show_wireframes = False
    except Exception:
        pass
    scene.render.resolution_x = 900
    scene.render.resolution_y = 900
    scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    print(f"  render: {out_path}", flush=True)


if __name__ == "__main__":
    main()
