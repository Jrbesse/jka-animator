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
  5. re-align the reference onto the rig's mirror armature (see
     ``_align_reference_to_rig``) — the importer parents the fresh
     armature to the scene's ``scene_root`` with an identity local
     transform, so a scene_root carrying a model-convention rotation
     (common for replacement models authored in a different up-axis
     convention) drags the stock reference skeleton off-plane while the
     model's own skeleton stays upright (Sheng review #7/#9, 2026-11-20:
     the reference lay flat on the ground 90 degrees from the model).

Nothing is saved; the .blend on disk is never touched. Verified S2
(2026-11-17): matched-session export byte-identical to a non-matched one.
"""
import os

import bpy
from mathutils import Matrix

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
    _align_reference_to_rig(fresh)
    print(f"jka_anim_tools: reference imported as '{REF_NAME}' "
          f"({len(fresh.data.bones)} bones); frame range "
          f"{bpy.context.scene.frame_start}..{bpy.context.scene.frame_end}")
    return fresh


def _align_reference_to_rig(ref):
    """Give the reference the RIG MIRROR's world transform.

    The importer created the reference under ``scene_root`` with an
    identity local transform — i.e. its world transform IS scene_root's.
    For a replacement model whose package bakes a corrective rotation
    into scene_root (authored in a different up-axis convention), that
    rotates the stock reference skeleton off-plane while the model's
    skeleton (whose bone space is pre-rotated to compensate) stays
    upright — the "reference not on the same plane as the .GLM" bug
    (review #7/#9).

    The model is bound to the mirror skeleton, so the reference must
    occupy the mirror's world transform (scale included) in EVERY case:

    * standard scenes (scene_root = identity + 0.1 scale, mirror local
      identity): the mirror's world transform already equals
      scene_root's — nothing moves and the matched export stays
      byte-identical (the reference is never part of the export);
    * rotated-convention scenes: the reference stands upright with the
      model instead of lying flat.

    The reference's local is identity (the importer's creation), so
    reparenting with an IDENTITY parent inverse makes its world
    transform exactly the mirror's, and keeps them in lockstep if the
    user later moves the rig object. (Do NOT cancel the mirror's world
    via matrix_parent_inverse — that strips the 0.1 engine scale and
    leaves the reference 10x oversized.)"""
    mirror = bpy.data.objects.get(RIG_NAME)
    if mirror is None:
        return
    ref.matrix_parent_inverse = Matrix.Identity(4)
    ref.parent = mirror
