# SPDX-License-Identifier: MIT
"""Reference GLA import for animation matching.

Builds the matching setup (decision #10): the rig's mirror armature + an
animated reference armature coexisting in one scene, so you can scrub the
reference and pose the rig to match.

Why the rename dance
--------------------
The addon's GLA importer REUSES any existing object or armature data-block
named "skeleton_root" (it would keyframe the reference onto the RIG's
mirror armature and destroy its pose state). The JustJordyn rig makes this
worse in two ways: its mirror object is named skeleton_root, AND the IK_Rig
armature's DATA-BLOCK is also named "skeleton_root" (the importer's
data-block fallback would grab the IK controls). So we:

  1. rename the mirror object + data-block to rig_armature / rig_armature_data
  2. rename IK_Rig's data-block (if it squats on the name)
  3. import the reference GLA (a fresh skeleton_root is created)
  4. rename the fresh one to reference_humanoid

Nothing is saved; the .blend on disk is never touched. Verified S2
(2026-11-17): matched-session export byte-identical to a non-matched one.
"""
import os

import bpy

from .addon_bridge import ensure_addon
from .common import MIRROR, RIG_NAME, REF_NAME, VALID_MODES, MODE_TO_OP, JkaError


def move_rig_armature_away():
    """Rename the mirror object/data-block (and any other armature
    data-block squatting on the name) so the importer creates a fresh
    ``skeleton_root``."""
    obj = bpy.data.objects.get(MIRROR)
    if obj is None:
        raise JkaError("no 'skeleton_root' object — open the rig first")
    if obj.type != "ARMATURE":
        raise JkaError(f"'{MIRROR}' is not an armature")
    if bpy.data.objects.get(RIG_NAME) is not None:
        raise JkaError(
            f"'{RIG_NAME}' already exists — looks like a reference was "
            "loaded in this session already; close without saving and start "
            "again")
    obj.name = RIG_NAME
    obj.data.name = RIG_NAME + "_data"
    print(f"jka_anim_tools: mirror moved to {RIG_NAME} / {RIG_NAME}_data")
    # the IK control armature's DATA-BLOCK is also named skeleton_root in
    # the JustJordyn rig — the importer's data-block fallback would grab it
    for o in bpy.data.objects:
        if o.type == "ARMATURE" and o.data.name == MIRROR:
            o.data.name = o.name + "_data"
            print(f"jka_anim_tools: renamed armature data-block "
                  f"'{MIRROR}' -> '{o.name}_data' (was squatting on the name)")


def load_reference(gla, basepath="", mode="range", start=0, frames=240,
                   addon_dir=None):
    """Import a reference .gla into the scene as the ``reference_humanoid``
    armature (the full flow: guard + rename dance + import + rename).

    ``gla``: the reference .gla file (absolute path).
    ``basepath``: absolute mod folder (needed by cfg mode for the .cfg).
    ``mode``: none|cfg|all|range — cfg = one NLA strip per animation.cfg
      segment; range = start..start+frames-1 in one action (fast);
      all = every frame in one action (slow).
    ``addon_dir``: see addon_bridge.ensure_addon (None = expect the addon
      installed).

    Returns the imported armature object."""
    if not gla:
        raise JkaError("a reference GLA path is required")
    mode = (mode or "range").lower()
    if mode not in VALID_MODES:
        raise JkaError(f"mode must be one of {VALID_MODES}")
    if REF_NAME in bpy.data.objects:
        raise JkaError(
            f"'{REF_NAME}' already exists in this scene — close without "
            "saving and start again")
    if basepath:
        basepath = os.path.abspath(basepath)
    kwargs: dict = dict(filepath=gla, basepath=basepath,
                        loadAnimations=MODE_TO_OP[mode])
    if mode == "range":
        kwargs["startFrame"] = int(start)
        kwargs["numFrames"] = int(frames)
    if mode == "cfg" and basepath == "":
        print("jka_anim_tools: note: cfg mode resolves the .cfg against "
              "basepath — set a basepath")
    move_rig_armature_away()
    # hasattr() on bpy.ops proxies is unreliable (lazy generation): probe
    # by calling and recovering once. A failed call executes nothing, so
    # the retry is a clean single import.
    try:
        bpy.ops.import_scene.gla(**kwargs)
    except AttributeError:
        ensure_addon(addon_dir, "import_scene.gla")
        bpy.ops.import_scene.gla(**kwargs)
    fresh = bpy.data.objects.get(MIRROR)
    if fresh is None:
        raise JkaError("import did not create a 'skeleton_root' — check "
                       "the import output above")
    fresh.name = REF_NAME
    print(f"jka_anim_tools: reference imported as '{REF_NAME}' "
          f"({len(fresh.data.bones)} bones); frame range "
          f"{bpy.context.scene.frame_start}..{bpy.context.scene.frame_end}")
    return fresh
