"""prepare_rig.py — prep a JustJordyn-style IK rig for GLA export (optionally export).

Why this exists
---------------
The rig .blend's SAVED pose state is contaminated: the `skeleton_root` mirror
armature carries a stored pose offset from rest plus IK constraints, and the
file has no actions. Exporting it as-is writes a degenerate frame stream
(every bone decodes near the root). The author's guide works around this with
a destructive "delete the RIG collection before export" step; this script does
the non-destructive equivalent IN MEMORY — the .blend is never saved.

Caveat C2 (read before exporting real animations)
-------------------------------------------------
The addon encodes each frame as deltas from the Blender rest pose. A frame
EXACTLY at rest encodes to an all-identity pool, which the engine decodes as
all bones at the root origin (a single point). Near-rest frames are fine.

Usage
-----
Headless (prep + export):

  blender --background rig.blend --python prepare_rig.py -- \
      --export out.gla \
      --basepath /path/to/modfolder \
      --glapath models/players/mychar/mychar.gla \
      --ref     models/players/_humanoid/_humanoid.gla \
      --frame-start 0 --frame-end 239

Headless (prep only, then export manually or via another script):

  blender --background rig.blend --python prepare_rig.py

Inside a running Blender (prep the open file, then use the addon's
File > Export > JA Ghoul 2 operator): open this file in the Text Editor
and press Run. The scene is modified in memory only.

Notes
-----
* `--ref` (the addon's "gla reference") is BASEPATH-RELATIVE, not absolute.
* `--export out.gla` must resolve to a path INSIDE `--basepath` (the addon
  derives the relative name from it; `--glapath` overrides the derived name).
* If the addon is not installed, pass --addon-dir pointing at the directory
  that CONTAINS the `jediacademy` package folder (i.e. the unzipped zip's
  top level).
"""
import os
import sys

import bpy

MIRROR = "skeleton_root"
RIG_NAME = "rig_armature"
REF_NAME = "reference_humanoid"


def strip_rig():
    """Remove IK constraints + stored pose offsets from the mirror armature.
    In-memory only; never saves the .blend."""
    arm = bpy.data.objects.get(MIRROR)
    if arm is None:
        # matched-session layout (load_reference.py): the mirror was renamed
        # away to keep the importer from reusing it — put it back
        cand = bpy.data.objects.get(RIG_NAME)
        if cand is None or cand.type != "ARMATURE":
            raise SystemExit(
                f"prepare_rig: no armature object named '{MIRROR}' found — "
                "is the IK rig file open in this scene?")
        ref = bpy.data.objects.get(REF_NAME)
        if ref is not None and ref.data.name == MIRROR:
            ref.data.name = REF_NAME + "_data"
        cand.data.name = MIRROR
        cand.name = MIRROR
        print(f"prepare_rig: renamed '{RIG_NAME}' back to '{MIRROR}' "
              "(matched-session layout from load_reference.py)")
        arm = cand
    if arm.type != "ARMATURE":
        raise SystemExit(f"prepare_rig: '{MIRROR}' is not an armature")
    removed = 0
    for pb in arm.pose.bones:
        for c in list(pb.constraints):
            pb.constraints.remove(c)
            removed += 1
        pb.location = (0.0, 0.0, 0.0)
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)
    print(f"prepare_rig: stripped {removed} constraints from "
          f"{len(arm.pose.bones)} pose bones of '{MIRROR}' "
          "(in-memory only; .blend not saved)")


def _arg(args, name, default=None):
    if name in args:
        i = args.index(name)
        if i + 1 < len(args):
            return args[i + 1]
    return default


def _fix_legacy_scale(arm):
    """The addon's legacy('g2_prop_scale') -> g2_prop scale migration only
    runs when the addon was registered BEFORE the .blend loaded. Registered
    later (headless --python after a command-line file open), g2_prop
    materializes at its default (100) and the author's stored scale (64 for
    the _humanoid rig) is silently lost -> export header gets scale 1.0
    instead of 0.64. Re-apply the legacy value if it is still there."""
    legacy = arm.get("g2_prop_scale", None)
    if legacy is None:
        return  # migrated at load time (or never set) — leave it alone
    try:
        if arm.g2_prop.scale != float(legacy):
            arm.g2_prop.scale = float(legacy)
            print(f"prepare_rig: restored author's g2 scale {legacy} "
                  "(legacy key not migrated in this session)")
    except AttributeError:
        pass  # addon operators unavailable — export_gla will error clearly


def _call_export(out, basepath, glapath, ref):
    return bpy.ops.export_scene.gla(
        filepath=os.path.abspath(out),
        basepath=basepath,
        glapath=glapath,
        glareference=ref)


def export_gla(args):
    out = _arg(args, "--export")
    if not out:
        raise SystemExit("prepare_rig: --export needs a filepath")
    basepath = _arg(args, "--basepath", "")
    if basepath:
        # the addon matches paths by string prefix — relative basepath
        # never matches the absolute export path ("Invalid Base Path")
        basepath = os.path.abspath(basepath)
    glapath = _arg(args, "--glapath", "")
    ref = _arg(args, "--ref", "")
    fs = _arg(args, "--frame-start", "")
    fe = _arg(args, "--frame-end", "")

    scene = bpy.context.scene
    if fs != "":
        scene.frame_start = int(fs)
    if fe != "":
        scene.frame_end = int(fe)
    if scene.frame_end < scene.frame_start:
        raise SystemExit(
            "prepare_rig: frame range is empty — pass --frame-start/--frame-end")
    if scene.frame_end == scene.frame_start:
        raise SystemExit(
            "prepare_rig: refusing to export a 1-frame GLA — pass "
            "--frame-end (and note caveat C2: a frame exactly at rest "
            "encodes degenerate)")

    # NOTE: hasattr() on bpy.ops proxies is unreliable (lazy generation),
    # so probe by calling and recovering once from AttributeError.
    arm = bpy.data.objects[MIRROR]
    try:
        _fix_legacy_scale(arm)
        _call_export(out, basepath, glapath, ref)
    except AttributeError:
        addon_dir = _arg(args, "--addon-dir")
        if not addon_dir:
            raise SystemExit(
                "prepare_rig: the addon's 'export_scene.gla' operator is "
                "not available. Install jediacademy.zip (User Preferences "
                "> Add-ons > Install from File) and retry, or pass "
                "--addon-dir pointing at the directory that contains the "
                "'jediacademy' package folder.")
        sys.path.insert(0, addon_dir)
        try:
            import jediacademy  # noqa: F401
            jediacademy.register()
        except Exception as e:
            raise SystemExit(f"prepare_rig: failed to load addon from {addon_dir}: {e}")
        _fix_legacy_scale(arm)
        _call_export(out, basepath, glapath, ref)

    print(f"prepare_rig: exported {os.path.abspath(out)} "
          f"({scene.frame_start}..{scene.frame_end})")
    print("prepare_rig: VALIDATE with the animkit gate, e.g.\n"
          "  python -m animkit check <character-dir>")


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    strip_rig()
    if "--export" in args:
        export_gla(args)
    else:
        print("prepare_rig: scene ready — export via the addon's "
              "'Export JA Ghoul 2 Skeleton & Animation' operator "
              "(or rerun with --export ...).")


if __name__ == "__main__":
    main()
