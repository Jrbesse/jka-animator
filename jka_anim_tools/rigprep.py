# SPDX-License-Identifier: MIT
"""Rig prep for GLA export (in-memory only — the .blend is never saved).

Why this exists
---------------
The JustJordyn rig .blend's SAVED pose state is contaminated: the
``skeleton_root`` mirror armature carries a stored pose offset from rest
plus 82 IK constraints, and the file has no actions. Exporting it as-is
writes a degenerate frame stream (every bone decodes near the root).
Prep does the non-destructive equivalent of the author's "delete the RIG
collection" step, in memory only (verified S1, 2026-11-17).
"""
import bpy

from .common import MIRROR, RIG_NAME, REF_NAME, JkaError


def find_mirror():
    """Return the export armature, restoring the matched-session layout
    (load_reference moves the mirror away so the importer can create a
    fresh ``skeleton_root`` — put it back before exporting)."""
    arm = bpy.data.objects.get(MIRROR)
    if arm is None:
        cand = bpy.data.objects.get(RIG_NAME)
        if cand is None or cand.type != "ARMATURE":
            raise JkaError(
                f"no armature object named '{MIRROR}' found — is the IK rig "
                "file open in this scene?")
        ref = bpy.data.objects.get(REF_NAME)
        if ref is not None and ref.data.name == MIRROR:
            ref.data.name = REF_NAME + "_data"
        cand.data.name = MIRROR
        cand.name = MIRROR
        print(f"jka_anim_tools: renamed '{RIG_NAME}' back to '{MIRROR}' "
              "(matched-session layout from load_reference)")
        arm = cand
    if arm.type != "ARMATURE":
        raise JkaError(f"'{MIRROR}' is not an armature")
    return arm


def strip_rig(arm=None):
    """Remove IK constraints + stored pose offsets from the mirror
    armature. In-memory only; never saves the .blend.

    Returns the number of constraints removed."""
    if arm is None:
        arm = find_mirror()
    removed = 0
    for pb in arm.pose.bones:
        for c in list(pb.constraints):
            pb.constraints.remove(c)
            removed += 1
        pb.location = (0.0, 0.0, 0.0)
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)
    print(f"jka_anim_tools: stripped {removed} constraints from "
          f"{len(arm.pose.bones)} pose bones of '{MIRROR}' "
          "(in-memory only; .blend not saved)")
    return removed


def restore_legacy_scale(arm):
    """Re-apply the author's legacy g2 scale if the addon never migrated it.

    The addon's legacy('g2_prop_scale') -> g2_prop scale migration only runs
    when the addon was registered BEFORE the .blend loaded. Registered
    later (headless --python after a command-line file open, or a dev
    session where the addon loaded after the file), g2_prop materializes at
    its default (100) and the author's stored scale (64 for the _humanoid
    rig) is silently lost -> the export header carries scale 1.0 instead of
    0.64. Must run AFTER any late addon registration.

    Returns True when the value was changed."""
    legacy = arm.get("g2_prop_scale", None)
    if legacy is None:
        return False  # migrated at load time (or never set) — leave it alone
    try:
        if arm.g2_prop.scale != float(legacy):
            arm.g2_prop.scale = float(legacy)
            print(f"jka_anim_tools: restored author's g2 scale {legacy} "
                  "(legacy key not migrated in this session)")
            return True
    except AttributeError:
        pass  # addon operators unavailable — export_gla will error clearly
    return False
