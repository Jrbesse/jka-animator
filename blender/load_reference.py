"""load_reference.py — import a reference .gla into the rig scene as an overlay.

Builds the animation-matching setup: the rig's mirror armature + an animated
reference armature coexisting in one scene, so you can scrub the reference and
pose the rig to match.

Why the rename dance
--------------------
The addon's GLA importer REUSES any existing object or armature data-block
named "skeleton_root" (it would keyframe the reference onto the RIG's mirror
armature and destroy its pose state). The JustJordyn rig makes this worse in
two ways: its mirror object is named skeleton_root, AND the IK_Rig armature's
DATA-BLOCK is also named "skeleton_root" (the importer's data-block fallback
would grab the IK controls). So this script:

  1. renames the mirror object + data-block to rig_armature / rig_armature_data
  2. renames IK_Rig's data-block (if it is "skeleton_root")
  3. imports the reference GLA (fresh skeleton_root is created)
  4. renames the fresh one to reference_humanoid

Nothing is saved; the .blend on disk is never touched.

Usage (headless, run on the rig file):

  blender --background rig.blend --python load_reference.py -- \
      --gla /abs/path/to/ref.gla --basepath /abs/path/to/modfolder \
      --mode range --start 0 --frames 240

  --mode cfg  : per-sequence NLA strips (needs animation.cfg next to the GLA,
                resolved against --basepath in base-relative form; slow for
                26K-frame skeletons)
  --mode all  : every frame in one action (slow)
  --mode range: startFrame..startFrame+frames-1 in one action (fast)

Exporting later in the same session: prepare_rig.py detects rig_armature and
renames it back to skeleton_root automatically.
"""
import os
import sys

import bpy

MIRROR = "skeleton_root"
RIG_NAME = "rig_armature"
REF_NAME = "reference_humanoid"

VALID_MODES = ("none", "cfg", "all", "range")
MODE_TO_OP = {"none": "NONE", "cfg": "CFG", "all": "ALL", "range": "RANGE"}


def _arg(args, name, default=None):
    if name in args:
        i = args.index(name)
        if i + 1 < len(args):
            return args[i + 1]
    return default


def move_rig_armature_away():
    """Rename the mirror object/data-block (and IK_Rig's data-block if it
    squat on the name) so the importer creates a fresh skeleton_root."""
    obj = bpy.data.objects.get(MIRROR)
    if obj is None:
        raise SystemExit("load_reference: no 'skeleton_root' object — open the rig first")
    if obj.type != "ARMATURE":
        raise SystemExit(f"load_reference: '{MIRROR}' is not an armature")
    if bpy.data.objects.get(RIG_NAME) is not None:
        raise SystemExit(f"load_reference: '{RIG_NAME}' already exists — looks like "
                         "a reference was loaded in this session already; close "
                         "without saving and start again")
    obj.name = RIG_NAME
    obj.data.name = RIG_NAME + "_data"
    print(f"load_reference: mirror moved to {RIG_NAME} / {RIG_NAME}_data")
    # the IK control armature's DATA-BLOCK is also named skeleton_root in the
    # JustJordyn rig — the importer's data-block fallback would grab it
    for o in bpy.data.objects:
        if o.type == "ARMATURE" and o.data.name == MIRROR:
            o.data.name = o.name + "_data"
            print(f"load_reference: renamed armature data-block "
                  f"'{MIRROR}' -> '{o.name}_data' (was squatting on the name)")


def _load_addon(args):
    addon_dir = _arg(args, "--addon-dir")
    if not addon_dir:
        raise SystemExit(
            "load_reference: the addon's 'import_scene.gla' operator is not "
            "available. Install jediacademy.zip (User Preferences > Add-ons "
            "> Install from File) and retry, or pass --addon-dir pointing at "
            "the directory that contains the 'jediacademy' package folder.")
    sys.path.insert(0, addon_dir)
    try:
        import jediacademy  # noqa: F401
        jediacademy.register()
    except Exception as e:
        raise SystemExit(f"load_reference: failed to load addon from {addon_dir}: {e}")


def import_reference(args):
    gla = _arg(args, "--gla")
    basepath = _arg(args, "--basepath", "")
    mode = (_arg(args, "--mode", "range") or "range").lower()
    if not gla:
        raise SystemExit("load_reference: --gla <file> is required")
    if basepath:
        basepath = os.path.abspath(basepath)
    if mode not in VALID_MODES:
        raise SystemExit(f"load_reference: --mode must be one of {VALID_MODES}")
    kwargs: dict = dict(filepath=gla, basepath=basepath,
                        loadAnimations=MODE_TO_OP[mode])
    if mode == "range":
        start = _arg(args, "--start", "0") or "0"
        frames = _arg(args, "--frames", "240") or "240"
        kwargs["startFrame"] = int(start)
        kwargs["numFrames"] = int(frames)
    if mode == "cfg" and basepath == "":
        print("load_reference: note: cfg mode resolves the .cfg against "
              "basepath — pass --basepath")
    # hasattr() on bpy.ops proxies is unreliable (lazy generation): probe by
    # calling and recovering once. A failed call executes nothing, so the
    # retry is a clean single import.
    try:
        bpy.ops.import_scene.gla(**kwargs)
    except AttributeError:
        _load_addon(args)
        bpy.ops.import_scene.gla(**kwargs)
    fresh = bpy.data.objects.get(MIRROR)
    if fresh is None:
        raise SystemExit("load_reference: import did not create a "
                         "'skeleton_root' — check the import output above")
    fresh.name = REF_NAME
    print(f"load_reference: reference imported as '{REF_NAME}' "
          f"({len(fresh.data.bones)} bones); frame range "
          f"{bpy.context.scene.frame_start}..{bpy.context.scene.frame_end}")


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if REF_NAME in bpy.data.objects:
        raise SystemExit(f"load_reference: '{REF_NAME}' already exists in this "
                         "scene — close without saving and start again")
    move_rig_armature_away()
    import_reference(args)
    print("load_reference: ready. Scrub the timeline — reference_humanoid "
          "animates, rig_armature is yours to pose. Export with "
          "prepare_rig.py (it renames rig_armature back).")


if __name__ == "__main__":
    main()
