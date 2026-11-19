# SPDX-License-Identifier: MIT
"""B3 operators: finger presets (the bpy face).

Thin delegate to the bpy-free core (fingers.py — the hand-relative
tables + the grasp slerp; one source of logic, the B1 pattern).
Applying follows the core's apply contract: per hand, topological
order [d1_j1, d1_j2, d2_j1, d2_j2, d4_j1, d4_j2], M_target =
M_parent @ REL_b where M_parent is the hand's evaluated pose matrix
(read once before the hand's loop) for _j1 bones and the bone's j1
TARGET for _j2 bones (a deterministic chain, not the live parent).
pb.matrix = M_target with a view-layer update after each assignment —
Blender resolves the pose's local offset against the LIVE parent, so
the update keeps the j2 assignments (and any downstream read)
correct. The hand bones are never touched: the preset only curls the
fingers relative to wherever the hand currently is. The headless
blender/b3_finger_apply_check.py driver invokes these same bpy.ops.
"""
import bpy

from mathutils import Matrix

from . import fingers, nla
from .cfgops import _sync_results
from .common import JkaError


def _rel_mat(preset, bone):
    """mathutils 4x4 from the core's flat 16-float row-major REL matrix."""
    m = fingers.preset_matrix(preset, bone)
    return Matrix((
        (m[0], m[1], m[2], m[3]),
        (m[4], m[5], m[6], m[7]),
        (m[8], m[9], m[10], m[11]),
        (m[12], m[13], m[14], m[15]),
    ))


def _driver_armature(arm):
    """The armature to actually pose. The export/bind skeleton (what
    find_armature returns — the object named 'skeleton_root') is often a
    PASSIVE MIRROR: its bones carry COPY_ROTATION/COPY_LOCATION
    constraints that copy a working rig (the IK rig), so setting their
    matrices has no effect. Follow a finger bone's copy constraint to its
    target armature and pose THAT (the driver); fall back to `arm` if it
    isn't constrained (already the driver)."""
    for bone in fingers.FINGER_BONES:
        pb = arm.pose.bones.get(bone)
        if pb is None:
            continue
        for c in pb.constraints:
            if c.type in ("COPY_ROTATION", "COPY_LOCATION") and c.target is not None:
                return c.target
    return arm


def apply_preset(preset, context):
    """Pose the 12 finger bones to `preset` ('fist'/'open'/'grasp')
    relative to each hand's current pose and key them at the current
    frame when the armature has an active action (never creates one).
    Returns report notes."""
    bind = nla.find_armature(context)
    if bind is None:
        raise JkaError("no armature in the scene (load the IK rig first)")
    arm = _driver_armature(bind)
    frame = int(context.scene.frame_current)
    has_action = (arm.animation_data is not None
                  and arm.animation_data.action is not None)
    for bone in fingers.HAND_BONES + fingers.FINGER_BONES:
        if arm.pose.bones.get(bone) is None:
            raise JkaError(f"bone {bone!r} missing from {arm.name} — "
                           "the rig must be the _humanoid skeleton")

    # targets, per hand: each _j1's parent is the hand (read once); each
    # _j2 chains from its _j1's TARGET (deterministic, not the live parent)
    targets = {}
    for hand in fingers.HAND_BONES:
        m_hand = arm.pose.bones[hand].matrix.to_4x4()
        for j1 in fingers.FINGER_BONES:
            if fingers.PARENT_BONE[j1] != hand:
                continue
            t1 = m_hand @ _rel_mat(preset, j1)
            targets[j1] = t1
            j2 = [b for b in fingers.FINGER_BONES
                  if fingers.PARENT_BONE[b] == j1]
            if j2:
                targets[j2[0]] = t1 @ _rel_mat(preset, j2[0])

    for bone in fingers.FINGER_BONES:
        pb = arm.pose.bones[bone]
        pb.matrix = targets[bone]
        bpy.context.view_layer.update()
        if has_action:
            pb.keyframe_insert("matrix", frame=frame)

    keyed = (f"keyed at frame {frame}" if has_action
             else "NOT keyed (no active action on the armature)")
    return [f"{preset}: {len(fingers.FINGER_BONES)} finger bones set on "
            f"{arm.name!r}", keyed]


class JKA_OT_FingerPreset(bpy.types.Operator):
    """Curl the 12 engine finger bones to a canonical hand-relative
    position (grasp / fist / open — the core's tables) and key them
    at the current frame when an action is active"""
    bl_idname = "jka_anim.finger_preset"
    bl_label = "Finger preset"
    bl_description = ("Set the 12 finger bones (d1/d2/d4 x j1/j2 per "
                      "hand) to a canonical curl relative to each "
                      "hand's current pose and key at the current "
                      "frame (fist = BOTH_P6_S6_TR blaster grip + "
                      "mirror, open = BOTH_STAND1 relaxed, grasp = "
                      "midpoint)")

    preset: bpy.props.EnumProperty(
        name="Preset", default="GRASP",
        items=(("GRASP", "Grasp", "halfway between fist and open"),
               ("FIST", "Fist", "clenched blaster grip (P6_S6_TR, mirrored)"),
               ("OPEN", "Open", "relaxed weapon-stand hand (BOTH_STAND1)")))

    def execute(self, context):
        p = context.scene.jka_anim
        try:
            notes = apply_preset(self.preset.lower(), context)
        except JkaError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        _sync_results(p, [(n, False) for n in notes])
        self.report({'INFO'}, notes[0])
        return {'FINISHED'}


CLASSES = (
    JKA_OT_FingerPreset,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
