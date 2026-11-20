"""b5_import_check.py — named-animation import (Sheng retest #2/#3/#4 +
the timeline-marker labels) headless functional driver.

Runs in `--background` Blender 5.3 on the JustJordyn IK-rig fixture
(scene holds the working skeleton: object 'skeleton_root', 53 bones,
and the IK rig: object 'IK_Rig', 64 bones with the chained finger
hierarchy):

  blender --background IKRIG.blend --factory-startup \
      --python blender/b5_import_check.py -- \
      --base /path/to/mod-folder --character assassin_droid \
      [--animkit-dir DIR] [--addon-dir DIR]

Checks (each via bpy.ops where the panel would; exit 0 +
'B5 CHECK PASSED' when all hold):
  1. named import into the working skeleton: BOTH_RUN1 -> action with
     the cfg's g2 props, NLA strip on the mirror (the name dance
     renamed it to 'rig_armature'), timeline marker at the first frame,
     no throwaway left behind
  2. fidelity: per-bone fcurve values on the target equal a fresh
     direct RANGE import for every bone that shares its parent in both
     rigs (the exact-copy path; tolerance for the matrix round-trip)
  3. custom range: typed name/first/frames -> action created, cfg file
     byte-identical, marker at the typed first frame, g2 (False, fps)
  4. IK rig target: re-import onto 'IK_Rig' -> shared-hierarchy bones
     exact vs the direct import, the re-aimed finger bones keyed, the
     IK control bones untouched
  5. saber preset + jump honor 'Rig target' (the strip lands on the
     chosen armature, not the active one)
  6. markers from segments: one per segment on the first frame (offset
     0), offset 1 moves them all, clear removes them
  7. re-import replaces: still exactly one action per name (no .001)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))


def _arg(args, name, default):
    if name in args:
        i = args.index(name)
        if i + 1 < len(args):
            return args[i + 1]
    return default


def _action_fcurves(action):
    """All of an action's fcurves, version-tolerant: 4.x keeps
    ``action.fcurves``; 5.x moved them into the layered action
    (``action.layers[].strips[].channelbags[].fcurves``)."""
    fcs = getattr(action, "fcurves", None)
    if fcs is not None:
        return fcs
    out = []
    for layer in (getattr(action, "layers", None) or []):
        for strip in (getattr(layer, "strips", None) or []):
            for bag in (getattr(strip, "channelbags", None) or []):
                out.extend(bag.fcurves)
    return out


def _fc_value(action, bone, prop, frame):
    """The action's fcurve value for (bone, property) at ``frame``:
    one fcurve per array index (location = 3, quaternion = 4) — returns
    the tuple of component values, or None when the channel is unkeyed."""
    want = f'pose.bones["{bone}"].{prop}'
    vals = {}
    for fc in _action_fcurves(action):
        if fc.data_path == want:
            vals[fc.array_index] = fc.evaluate(frame)
    if not vals:
        return None
    return tuple(vals[i] for i in range(max(vals) + 1))


def _exact_bones(src_arm, tgt_arm):
    """Bones present in both rigs whose PARENT NAME matches in both
    (needed but not sufficient for the exact-copy path)."""
    out = []
    for b in src_arm.data.bones:
        tb = tgt_arm.data.bones.get(b.name)
        if tb is None:
            continue
        sp = b.parent.name if b.parent else None
        tp = tb.parent.name if tb.parent else None
        if sp == tp:
            out.append(b.name)
    return out


def _chain_bones(src_arm, tgt_arm):
    """Bones whose ENTIRE ancestor chain matches name-for-name in both
    rigs — only for these does the retarget formula reduce to an exact
    copy (a parent-name match with a diverging higher chain still
    re-aims through the divergence)."""
    out = []
    for b in src_arm.data.bones:
        if b.name not in tgt_arm.data.bones:
            continue
        s, t = b, tgt_arm.data.bones[b.name]
        chain_ok = True
        while s.parent is not None:
            tp = t.parent.name if t.parent else None
            if tp != s.parent.name:
                chain_ok = False
                break
            s, t = s.parent, t.parent
        if chain_ok:
            out.append(b.name)
    return out


def _strip_on(arm, action):
    if arm is None or arm.animation_data is None:
        return 0
    n = 0
    for t in arm.animation_data.nla_tracks:
        for s in t.strips:
            if s.action is action:
                n += 1
    return n


def main():
    import bpy
    import jka_anim_tools
    from jka_anim_tools import anims, nla
    import jka_anim_tools.panel as jka_panel
    from jka_anim_tools.common import RIG_NAME

    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    base = _arg(args, "--base", "")
    character = _arg(args, "--character", "assassin_droid")
    animkit_dir = _arg(args, "--animkit-dir",
                       os.environ.get("JKA_ANIMKIT_DIR", ""))
    addon_dir = _arg(args, "--addon-dir", "")
    if not base:
        raise SystemExit("b5_import_check: pass --base <mod folder>")

    jka_anim_tools.register()
    p = bpy.context.scene.jka_anim
    p.basepath = base
    p.character = character
    p.animkit_dir = animkit_dir
    p.addon_dir = addon_dir

    scene = bpy.context.scene
    mirror = scene.objects.get("skeleton_root")
    ik = scene.objects.get("IK_Rig")
    if mirror is None or mirror.type != "ARMATURE":
        raise SystemExit("b5_import_check: no 'skeleton_root' armature")
    if ik is None or ik.type != "ARMATURE":
        raise SystemExit("b5_import_check: no 'IK_Rig' armature")

    failures = []

    def check(num, what, cond, detail=""):
        status = "ok " if cond else "FAIL"
        print(f"  [{status}] {num}. {what}"
              + (f" — {detail}" if detail and not cond else ""), flush=True)
        if not cond:
            failures.append(what)

    # 1. named import into the working skeleton (default target)
    ret = bpy.ops.jka_anim.segments_load()
    segs = [(s.name, s.first_frame, s.num_frames, s.loop_frames, s.fps)
            for s in p.segments]
    run1 = next((s for s in segs if s[0] == "BOTH_RUN1"), None)
    if run1 is None:
        raise SystemExit(f"BOTH_RUN1 missing from the {character} cfg")
    run1_i = next(i for i, s in enumerate(segs) if s[0] == "BOTH_RUN1")
    p.target_arm = "AUTO"  # resolver default: the working skeleton
    p.imp_segment = str(run1_i)
    ret = bpy.ops.jka_anim.anim_import()
    act = bpy.data.actions.get("BOTH_RUN1")
    props = nla.action_props(act)
    m2 = scene.objects.get(RIG_NAME)  # the mirror after the name dance
    strip_n = _strip_on(m2, act) if act else 0
    marker = next((m for m in scene.timeline_markers
                   if m.name == "BOTH_RUN1"), None)
    check(1, "named import -> working skeleton",
          "FINISHED" in ret and act is not None
          and props == (run1[3] != -1, run1[4])
          and m2 is not None and m2.type == "ARMATURE" and strip_n == 1
          and marker is not None and marker.frame == run1[1]
          and scene.objects.get("skeleton_root") is None
          and scene.objects.get("_jka_import_tmp") is None,
          f"ret={ret} act={act.name if act else None} props={props} "
          f"strip_n={strip_n} marker={marker.frame if marker else None} "
          f"mirror={m2.name if m2 else None}")
    if act is None:
        raise SystemExit("check 1 failed hard — cannot continue")

    # scratch direct import for the fidelity reference (local 0..num-1)
    from jka_anim_tools import paths
    gla = paths.derive_ref_gla(base, character, p.ref_gla)
    from jka_anim_tools import animimport
    animimport.free_mirror_name()  # no-op now; name already free
    from jka_anim_tools import addon_bridge
    addon_bridge.ensure_addon(addon_dir, "import_scene.gla")
    bpy.ops.import_scene.gla(filepath=gla, basepath="",
                             loadAnimations="RANGE",
                             startFrame=run1[1], numFrames=run1[2])
    scratch = scene.objects.get("skeleton_root")
    scratch.name = "_jka_scratch"
    sact = scratch.animation_data.action
    if sact is None:
        for t in scratch.animation_data.nla_tracks:
            for s in t.strips:
                sact = s.action
                break
            if sact:
                break
    exact = _chain_bones(scratch, m2)

    def fidelity(tgt_arm, action, offset, bones, frames, tol=1e-5):
        for f in frames:
            for b in bones:
                for prop in ("location", "rotation_quaternion"):
                    a = _fc_value(action, b, prop, offset + f)
                    z = _fc_value(sact, b, prop, f)
                    if a is None or z is None:
                        return False, f"{b}.{prop}@{f}: {a} vs {z}"
                    if max(abs(x - y) for x, y in zip(a, z)) > tol:
                        return False, f"{b}.{prop}@{f}: {a} vs {z}"
        return True, ""

    fr = [0, run1[2] // 2, run1[2] - 1]
    ok, why = fidelity(m2, act, run1[1], exact, fr)
    check(2, "fidelity: full-chain bones exact vs direct import",
          sact is not None and len(exact) >= 35 and ok,
          f"sact={sact.name if sact else None} "
          f"exact_bones={len(exact)} fidelity={why}")

    # 3. custom range (not in the cfg)
    cfg_anim = anims.cfg_path(base, character, "animation")
    before = open(cfg_anim, "rb").read()
    p.imp_name = "MY_CUSTOM"
    p.imp_first = 3
    p.imp_frames = 8
    p.imp_fps = 20
    ret = bpy.ops.jka_anim.anim_import(custom=True)
    cact = bpy.data.actions.get("MY_CUSTOM")
    cprops = nla.action_props(cact)
    cmarker = next((m for m in scene.timeline_markers
                    if m.name == "MY_CUSTOM"), None)
    nkeys = 0
    if cact is not None:
        for fc in _action_fcurves(cact):
            if fc.data_path == 'pose.bones["pelvis"].location':
                nkeys = len(fc.keyframe_points)
    after = open(cfg_anim, "rb").read()
    check(3, "custom range import (cfg untouched)",
          "FINISHED" in ret and cact is not None and cprops == (False, 20)
          and nkeys == 8 and cmarker is not None and cmarker.frame == 3
          and before == after,
          f"ret={ret} act={cact.name if cact else None} "
          f"props={cprops} nkeys={nkeys} "
          f"marker={cmarker.frame if cmarker else None} "
          f"cfg_changed={before != after}")

    # 4. IK rig target (finger re-aim)
    p.target_arm = ik.name
    p.imp_segment = str(run1_i)
    ret = bpy.ops.jka_anim.anim_import()
    iact = bpy.data.actions.get("BOTH_RUN1")
    exact_ik = _chain_bones(scratch, ik)
    ok, why = fidelity(ik, iact, run1[1], exact_ik, fr)
    ik_bone_names = {b.name for b in ik.data.bones}
    src_bone_names = {b.name for b in scratch.data.bones}
    controls = ik_bone_names - src_bone_names
    reaimed = [b.name for b in scratch.data.bones
               if b.name in ik_bone_names
               and ((b.parent.name if b.parent else None)
                    != (ik.data.bones[b.name].parent.name
                        if ik.data.bones[b.name].parent else None))]
    keyed_reaimed = control_dirty = None
    if iact is not None:
        keyed_reaimed = all(
            _fc_value(iact, b, "rotation_quaternion", run1[1] + 1) is not None
            for b in reaimed)
        control_dirty = any(
            _fc_value(iact, b, "rotation_quaternion", run1[1] + 1) is not None
            or _fc_value(iact, b, "location", run1[1] + 1) is not None
            for b in controls)
    ik_strip = _strip_on(ik, iact) if iact else 0
    mirror_strip = _strip_on(m2, iact) if iact else 0
    check(4, "IK rig target: exact shared + re-aimed fingers + clean "
             "controls",
          "FINISHED" in ret and iact is not None and ok and ik_strip == 1
          and mirror_strip == 0 and len(reaimed) >= 8
          and keyed_reaimed is True and control_dirty is False,
          f"ret={ret} fidelity={why} ik_strip={ik_strip} "
          f"mirror_strip={mirror_strip} reaimed={len(reaimed)} "
          f"keyed={keyed_reaimed} control_dirty={control_dirty}")

    # 5. saber preset + jump honor the Rig target
    p.target_arm = m2.name
    items = jka_panel._saber_preset_items(bpy.context, None)
    guard_i = next(i for i, (_id, label, _d) in enumerate(items)
                   if label.startswith("guard"))
    p.saber_preset = str(guard_i)
    ret = bpy.ops.jka_anim.saber_preset_apply()
    gact = bpy.data.actions.get("BOTH_STAND1")
    g_on_m2 = _strip_on(m2, gact) if gact else 0
    p.target_arm = ik.name
    walk = next((s for s in segs
                 if s[0] not in {a.name for a in bpy.data.actions}), None)
    p.seg_selected = next(i for i, s in enumerate(segs) if s == walk)
    p.seg_jump_create = True
    ret = bpy.ops.jka_anim.segment_jump()
    wact = bpy.data.actions.get(walk[0])
    w_on_ik = _strip_on(ik, wact) if wact else 0
    check(5, "saber + jump honor the Rig target",
          "FINISHED" in ret and g_on_m2 == 1 and wact is not None
          and w_on_ik == 1,
          f"ret={ret} guard_on_mirror={g_on_m2} "
          f"walk={walk[0] if walk else None} walk_on_ik={w_on_ik}")

    # 6. markers from segments (offsets + clear)
    ret = bpy.ops.jka_anim.markers_clear()
    p.marker_offset = 0
    ret = bpy.ops.jka_anim.markers_from_segments()
    mk = {m.name: m.frame for m in scene.timeline_markers}
    first_ok = all(mk.get(s[0]) == s[1] for s in segs)
    p.marker_offset = 1
    ret = bpy.ops.jka_anim.markers_from_segments()
    mk = {m.name: m.frame for m in scene.timeline_markers}
    off_ok = all(mk.get(s[0]) == s[1] + 1 for s in segs) and len(mk) == len(segs)
    ret = bpy.ops.jka_anim.markers_clear()
    mk = {m.name: m.frame for m in scene.timeline_markers}
    check(6, "markers from segments / offset / clear",
          "FINISHED" in ret and len(mk) == 0 and first_ok and off_ok,
          f"first_ok={first_ok} off_ok={off_ok} after_clear={len(mk)}")

    # 7. re-import replaces (no .001)
    p.imp_segment = str(run1_i)
    ret = bpy.ops.jka_anim.anim_import()
    n_names = len([a for a in bpy.data.actions if a.name.startswith("BOTH_RUN1")])
    ract = bpy.data.actions.get("BOTH_RUN1")
    r_strip = _strip_on(ik, ract) if ract else 0
    n_markers = len([m for m in scene.timeline_markers if m.name == "BOTH_RUN1"])
    check(7, "re-import replaces the action (no .001, one strip, one "
             "marker)",
          "FINISHED" in ret and n_names == 1 and r_strip == 1
          and n_markers == 1,
          f"ret={ret} n_actions={n_names} strip={r_strip} "
          f"markers={n_markers}")

    # cleanup the scratch armature (its data + action lose their last user)
    sdata = scratch.data
    bpy.data.objects.remove(scratch, do_unlink=True)
    if sact is not None and sact.users == 0:
        bpy.data.actions.remove(sact)
    if sdata is not None and sdata.users == 0:
        bpy.data.armatures.remove(sdata)

    if failures:
        print(f"B5 CHECK FAILED: {len(failures)} check(s): {failures}")
        raise SystemExit(1)
    print("B5 CHECK PASSED (7/7)")


if __name__ == "__main__":
    main()
