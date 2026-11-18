"""b2_cfg_check.py — B2 headless functional driver (the v18 handoff's
gate, step 2).

Exercises the NEW bpy layer — registers the addon and drives the cfgops
operators via bpy.ops exactly like the N-panel would — on a real mod
tree. Runs in `--background` Blender 5.3.

  blender --background RIG.blend --python blender/b2_cfg_check.py -- \
      --base /path/to/mod-folder --character assassin_droid \
      [--animkit-dir DIR] [--addon-dir DIR] [--in-place]

--base must stage models/players/<character>/{animation,animevents}.cfg
and ext_data/saberanims.cfg. By default the check runs on a SCRATCH copy
so the given base is never modified (--in-place edits it). RIG.blend
supplies the armature (an armature must exist; 'skeleton_root' is
preferred).

Checks (each via bpy.ops; exit 0 + 'B2 CHECK PASSED' when all hold):
  1. segments_load    41 segments; BOTH_RUN1 128..139 loop 0; BOTH_STAND1
                      loop 0 (a looping 2-frame segment)
  2. events_load      LOWER/BOTH_RUN1 has exactly TWO events (keys 9 and
                      3 — the engine fires both; not a dup)
  3. saber_validate   the built-in 7 styles present, 0 error lines
  4. preset guard     BOTH_STAND1 already in the cfg -> no cfg change,
                      action with cfg loop/fps + NLA strip created
  5. preset attack    a NEW segment: cfg gains the line (saved), action
                      g2_sequence_prop (loop=False, fps=20), NLA strip
                      on a 'Sequences Layer' track, frame set
  6. round-trip       the untouched animevents.cfg re-emits
                      byte-identical (modulo nothing — no comments here)
  7. seeded error     AEV_FIRE @ 9999 on the 12-frame BOTH_ATTACK1:
                      events_save CANCELLED, file byte-identical, error
                      line in the Results collection
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))


def _arg(args, name, default):
    if name in args:
        i = args.index(name)
        if i + 1 < len(args):
            return args[i + 1]
    return default


def main():
    import bpy
    import jka_anim_tools
    from jka_anim_tools import anims, animkit_bridge, nla
    import jka_anim_tools.panel as jka_panel

    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    base = _arg(args, "--base", "")
    character = _arg(args, "--character", "assassin_droid")
    animkit_dir = _arg(args, "--animkit-dir", os.environ.get("JKA_ANIMKIT_DIR", ""))
    addon_dir = _arg(args, "--addon-dir", "")
    in_place = "--in-place" in args
    if not base:
        raise SystemExit("b2_cfg_check: pass --base <mod folder>")

    # scratch copy unless told to work in place
    work_root = ""
    if not in_place:
        work_root = tempfile.mkdtemp(prefix="jka_b2_check_")
        char_dst = os.path.join(work_root, "models", "players", character)
        shutil.copytree(os.path.join(base, "models", "players", character),
                        char_dst)
        ext_src = os.path.join(base, "ext_data")
        if os.path.isdir(ext_src):
            shutil.copytree(ext_src, os.path.join(work_root, "ext_data"))
        base = work_root

    jka_anim_tools.register()
    p = bpy.context.scene.jka_anim
    p.cfg_basepath = base
    p.cfg_character = character
    p.animkit_dir = animkit_dir
    p.addon_dir = addon_dir

    cfg_anim = anims.cfg_path(base, character, "animation")
    cfg_evt = anims.cfg_path(base, character, "animevents")
    failures = []

    def check(num, what, cond, detail=""):
        status = "ok " if cond else "FAIL"
        print(f"  [{status}] {num}. {what}" + (f" — {detail}" if detail and not cond else ""),
              flush=True)
        if not cond:
            failures.append(what)

    # 1. segments
    ret = bpy.ops.jka_anim.segments_load()
    segs = [(s.name, s.first_frame, s.num_frames, s.loop_frames, s.fps)
            for s in p.segments]
    run1 = next((s for s in segs if s[0] == "BOTH_RUN1"), None)
    stand1 = next((s for s in segs if s[0] == "BOTH_STAND1"), None)
    check(1, "segments_load", "FINISHED" in ret and len(segs) == 41
          and run1 == ("BOTH_RUN1", 128, 12, 0, 20)
          and stand1 is not None and stand1[3] == 0,
          f"ret={ret} n={len(segs)} run1={run1} stand1={stand1}")
    before_names = [s[0] for s in segs]

    # 2. events (BOTH_RUN1 keeps its two base events)
    run1_i = next(i for i, s in enumerate(segs) if s[0] == "BOTH_RUN1")
    p.evt_segment = str(run1_i)
    p.evt_block = "LOWER"
    ret = bpy.ops.jka_anim.events_load()
    keys = sorted(e.key_frame for e in p.events)
    check(2, "events_load LOWER/BOTH_RUN1", "FINISHED" in ret and keys == [3, 9],
          f"ret={ret} keys={keys}")

    # 3. saber validate
    ret = bpy.ops.jka_anim.saber_validate()
    err_lines = [r.text for r in p.results if r.is_error]
    style_lines = [r.text for r in p.results if r.text.startswith("style ")]
    names = [l.split()[1].rstrip(":") for l in style_lines]
    built_in = {"fast", "medium", "strong", "desann", "tavion", "dual", "staff"}
    check(3, "saber_validate", "FINISHED" in ret and not err_lines
          and built_in.issubset(set(names)),
          f"ret={ret} errors={err_lines} styles={names}")

    items = jka_panel._saber_preset_items(bpy.context, None)

    # 4. preset guard (BOTH_STAND1 exists in the cfg -> unchanged)
    guard_i = next(i for i, (_id, label, _d) in enumerate(items)
                   if label.startswith("guard"))
    p.saber_preset = str(guard_i)
    ret = bpy.ops.jka_anim.saber_preset_apply()
    now_names = [s.name for s in p.segments]
    act = bpy.data.actions.get("BOTH_STAND1")
    props = nla.action_props(act)
    arm = nla.find_armature(bpy.context)
    check(4, "preset guard (existing segment)",
          "FINISHED" in ret and now_names == before_names
          and act is not None and props == (True, 20)
          and nla.strip_for_action(arm, act) is not None,
          f"ret={ret} names_changed={now_names != before_names} "
          f"act={act.name if act else None} props={props}")

    # 5. preset attack:fast (a NEW segment)
    fast_i = next(i for i, (_id, label, _d) in enumerate(items)
                  if label.startswith("attack: fast"))
    p.saber_preset = str(fast_i)
    ret = bpy.ops.jka_anim.saber_preset_apply()
    new = [s.name for s in p.segments if s.name not in before_names]
    row = p.segments[p.seg_selected]
    text = open(cfg_anim, "r", newline="").read()
    act = bpy.data.actions.get(new[0]) if new else None
    props = nla.action_props(act)
    strip = nla.strip_for_action(arm, act) if act else None
    track = None
    if strip is not None and arm.animation_data is not None:
        for t in arm.animation_data.nla_tracks:
            if any(s == strip for s in t.strips):
                track = t
                break
    check(5, "preset attack:fast (new segment)",
          "FINISHED" in ret and len(new) == 1
          and new[0] in text and row.name == new[0]
          and act is not None and props == (False, 20)
          and strip is not None and track.name.startswith("Sequences Layer")
          and bpy.context.scene.frame_current == row.first_frame,
          f"ret={ret} new={new} props={props} "
          f"strip={strip} track={track.name if track else None}")

    # 6. round-trip of the untouched animevents.cfg
    ak = animkit_bridge.get_animkit(animkit_dir)
    raw = open(cfg_evt, "r", newline="").read()
    check(6, "animevents round-trip", ak.cfgwrite.AnimEventsDoc(raw).text() == raw)

    # 7. seeded error: keyFrame 9999 on the 12-frame BOTH_ATTACK1
    atk_i = next(i for i, s in enumerate(p.segments) if s.name == "BOTH_ATTACK1")
    p.evt_segment = str(atk_i)
    p.evt_block = "LOWER"
    ret = bpy.ops.jka_anim.events_load()
    p.evt_new_type = "AEV_FIRE"
    p.evt_new_key = 9999
    p.evt_new_data = "0 100"
    ret_add = bpy.ops.jka_anim.event_add()
    before = open(cfg_evt, "rb").read()
    # a CANCELLED op with an error report makes bpy.ops raise RuntimeError
    try:
        ret_save = bpy.ops.jka_anim.events_save()
    except RuntimeError as e:
        ret_save = {"CANCELLED"}
        save_msg = str(e)
    else:
        save_msg = ""
    after = open(cfg_evt, "rb").read()
    errs = [r.text for r in p.results if r.is_error]
    check(7, "seeded error blocks the write",
          "FINISHED" in ret_add and "CANCELLED" in ret_save
          and before == after and any("9999" in e for e in errs),
          f"add={ret_add} save={ret_save} save_msg={save_msg} "
          f"file_changed={before != after} errs={errs}")

    if work_root:
        shutil.rmtree(work_root, ignore_errors=True)

    if failures:
        print(f"B2 CHECK FAILED: {len(failures)} check(s): {failures}")
        raise SystemExit(1)
    print("B2 CHECK PASSED (7/7)")


if __name__ == "__main__":
    main()
