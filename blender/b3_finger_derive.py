# SPDX-License-Identifier: MIT
"""b3_finger_derive.py — B3 finger preset angle derivation (headless).

Derives the finger preset table WITHOUT hand-rolled GLA->pose math: it
runs the VERIFIED importer (load_reference, RANGE mode) on a stock GLA
segment, scrubs to one frame, and reads back the 12 engine finger
bones' pose rotations from the imported reference armature (the
importer's output IS the engine pose, per the B1 verification).
Prints a Python-ready table (bone -> (x, y, z) Euler degrees) for
committing into the preset core.

  blender --background RIG.blend --python blender/b3_finger_derive.py -- \
      --base /path/to/mod-folder [--skeleton _humanoid] \
      --seg BOTH_STAND1 [--animkit-dir DIR] [--addon-dir DIR]

The segment's first POOL frame is resolved from animation.cfg (the cfg's
'first' is a global pool index, not 0). One run per reference pose
(fist / open / ...); judge the printed table against a --view both mesh
render of the same frame before committing it (render rule: never
verdict from a wireframe sheet).
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

FINGER_BONES = (
    "l_d1_j1", "l_d1_j2", "l_d2_j1", "l_d2_j2", "l_d4_j1", "l_d4_j2",
    "r_d1_j1", "r_d1_j2", "r_d2_j1", "r_d2_j2", "r_d4_j1", "r_d4_j2",
)

# also printed (parent context for the relative-matrix tables)
HAND_BONES = ("lhand", "rhand")


def _dump_table(tag, ref, bones):
    print(f"{tag} = {{", flush=True)
    for b in bones:
        pb = ref.pose.bones.get(b)
        if pb is None:
            print(f'    # missing {b}', flush=True)
            continue
        m4 = pb.matrix.to_4x4()
        rows = tuple(round(m4[r][c], 6) for r in range(4) for c in range(4))
        print(f'    "{b}": {rows},', flush=True)
    print("}", flush=True)


def _dump_rest(tag, arm, bones):
    print(f"{tag} = {{", flush=True)
    for b in bones:
        ab = arm.data.bones.get(b)
        if ab is None:
            print(f'    # missing {b}', flush=True)
            continue
        m4 = ab.matrix_local.copy().to_4x4()
        rows = tuple(round(m4[r][c], 6) for r in range(4) for c in range(4))
        print(f'    "{b}": {rows},', flush=True)
    print("}", flush=True)


def _arg(args, name, default):
    if name in args:
        i = args.index(name)
        if i + 1 < len(args):
            return args[i + 1]
    return default


def main():
    import bpy
    import jka_anim_tools
    from jka_anim_tools import animkit_bridge, anims

    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    base = _arg(args, "--base", "")
    skeleton = _arg(args, "--skeleton", "_humanoid")
    seg = _arg(args, "--seg", "BOTH_STAND1")
    animkit_dir = _arg(args, "--animkit-dir", os.environ.get("JKA_ANIMKIT_DIR", ""))
    addon_dir = _arg(args, "--addon-dir", "")
    if not base:
        raise SystemExit("b3_finger_derive: pass --base <mod folder>")

    # resolve the segment's FIRST POOL frame via the cfg layer — the GLA
    # frame pool is global; the cfg's 'first' is the pool index, not 0
    ak = animkit_bridge.get_animkit(animkit_dir)
    segs, _warns = anims.load_segments(ak, base, skeleton)
    info = next((s for s in segs if s.name == seg), None)
    if info is None:
        raise SystemExit(f"b3_finger_derive: segment {seg!r} not in the cfg")
    first = int(info.first_frame)

    jka_anim_tools.register()
    p = bpy.context.scene.jka_anim
    p.ref_gla = os.path.join(base, "models", "players", skeleton,
                             f"{skeleton}.gla")
    p.ref_basepath = base
    p.ref_mode = "RANGE"
    p.ref_start = first
    p.ref_frames = 1
    p.animkit_dir = animkit_dir
    p.addon_dir = addon_dir
    ret = bpy.ops.jka_anim.load_reference()
    if "FINISHED" not in set(ret):
        raise SystemExit(f"b3_finger_derive: load_reference failed: {ret}")

    bpy.context.scene.frame_set(first)

    # the reference armature: prefer the known name, else any armature
    # that is NOT the rig's skeleton_root
    ref = bpy.data.objects.get("reference_humanoid")
    if ref is None or not ref.type == "ARMATURE":
        cands = [o for o in bpy.data.objects if o.type == "ARMATURE"
                 and o.data.name != "skeleton_root"]
        ref = cands[0] if cands else None
    if ref is None:
        raise SystemExit("b3_finger_derive: reference armature not found")

    # --rig-rest also dumps the RIG (skeleton_root) rest matrices —
    # used to verify the armature-space x-mirror symmetry the fist
    # preset relies on (left side = mirror of the right-hand data)
    if "--rig-rest" in args:
        rig = bpy.data.objects.get("IK_Rig")
        if rig is not None and rig.type == "ARMATURE":
            _dump_rest("RIG_REST", rig, FINGER_BONES + HAND_BONES)
        else:
            print("# IK_Rig not found in this scene", flush=True)

    print(f"# {seg} @ pool frame {first} — reference armature {ref.name!r}",
          flush=True)
    print("# ABSOLUTE evaluated bone matrices (armature space), 4x4 row-major",
          flush=True)
    print("# (hands included: they are the parents for the relative tables.",
          flush=True)
    print("# A single-frame RANGE import sets the reference armature's rest",
          flush=True)
    print("# pose to the imported frame — pose OFFSETS read ~0; the data is",
          flush=True)
    print("# in the absolute matrix.)", flush=True)
    _dump_table("ABS_TABLE", ref, FINGER_BONES + HAND_BONES)


if __name__ == "__main__":
    main()
