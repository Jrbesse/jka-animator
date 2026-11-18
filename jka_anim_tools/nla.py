# SPDX-License-Identifier: MIT
"""Blender-side NLA glue for B2: armature, NLA tracks, actions, strips.

One source of logic — the cfgops operators and the headless blender/
driver both call these (B1 pattern). The strip/track mechanics mirror the
installed jediacademy importer (JAG2GLA.py): action named exactly like
the cfg segment, a g2_sequence_prop (loop bool + fps) on the Action
(registered by the jediacademy addon), strips on "Sequences Layer N"
tracks, multi-user action slots on Blender 4.4+.
"""
import bpy

from .common import JkaError, MIRROR


def find_armature(context):
    """The armature NLA strips attach to:
    1. the object named 'skeleton_root' (the export name — what ships),
    2. else the active armature,
    3. else the first armature object.
    """
    objs = context.scene.objects
    mirror = objs.get(MIRROR)
    if mirror is not None and mirror.type == "ARMATURE":
        return mirror
    active = context.active_object
    if active is not None and active.type == "ARMATURE":
        return active
    for o in objs:
        if o.type == "ARMATURE":
            return o
    raise JkaError("no armature object in the scene — import a GLM first")


def _action_slot(action):
    """The 'Armature' object slot for multi-user actions (Blender 4.4+).
    None on older Blenders (no slots concept, none needed)."""
    slot = None
    if hasattr(action, "slots"):
        slot = action.slots.get("Armature")
        if slot is None:
            slot = action.slots.new("OBJECT", "Armature")
    return slot


def set_action_props(action, loop, fps):
    """Write the action's g2_sequence_prop (loop bool, fps int).

    Writing a sub-property auto-allocates the pointer, the importer's own
    idiom. Raises JkaError when the property type is not registered (the
    jediacademy addon is not loaded).
    """
    if not hasattr(bpy.types.Action, "g2_sequence_prop"):
        raise JkaError(
            "the jediacademy addon's g2_sequence_prop Action property is "
            "not registered — enable the jediacademy addon (or set the "
            "'Add-on dir' field)")
    action.g2_sequence_prop.loop_frame = bool(loop)
    action.g2_sequence_prop.fps = int(fps)


def make_action(name, loop, fps):
    """A new action named ``name`` carrying the jediacademy g2_sequence_prop.

    Raises JkaError when the jediacademy addon (which registers the
    property) is not loaded — never writes a bare action that the
    exporter would treat as loop=False/fps=0.
    """
    action = bpy.data.actions.new(name)
    set_action_props(action, loop, fps)
    return action


def get_sequence_track(armature, index=1):
    """The 'Sequences Layer <index>' NLA track on the armature (created if
    missing)."""
    anim = armature.animation_data_create()
    anim.use_nla = True
    track = anim.nla_tracks.get(f"Sequences Layer {index}")
    if track is None:
        track = anim.nla_tracks.new()
        track.name = f"Sequences Layer {index}"
    return track


def add_strip(armature, action, start_frame, num_frames):
    """An NLA strip of ``action`` on the first non-overlapping
    'Sequences Layer' track (Layers 1..8, the importer's walk).

    Raises JkaError when the action already has a strip anywhere on the
    armature (callers must check strip_for_action first) or when every
    layer is occupied.
    """
    if strip_for_action(armature, action) is not None:
        raise JkaError(f"{action.name!r} already has an NLA strip on "
                       f"{armature.name!r}")
    anim = armature.animation_data
    slot = _action_slot(action)
    for i in range(1, 9):
        track = get_sequence_track(armature, i)
        try:
            strip = track.strips.new(action.name, start_frame, action)
        except Exception:
            continue  # overlaps an existing strip — try the next layer
        strip.action_frame_start = 0
        strip.action_frame_end = num_frames - 1
        if hasattr(strip, "action_slot") and slot is not None:
            strip.action_slot = slot
        return track, strip
    raise JkaError(f"no free 'Sequences Layer' track for {action.name!r} "
                   f"(layers 1-8 all occupied/overlapping)")


def strip_for_action(armature, action):
    """The existing strip of ``action`` on any of the armature's NLA
    tracks, or None."""
    anim = armature.animation_data
    if anim is None:
        return None
    for track in anim.nla_tracks:
        for strip in track.strips:
            if strip.action == action:
                return strip
    return None


def scene_action(name):
    """The action named EXACTLY ``name`` (the jediacademy importer names
    actions after cfg segment names), or None."""
    return bpy.data.actions.get(name)


def action_props(action):
    """(loop, fps) from the action's g2_sequence_prop, or None when the
    addon's property is absent (plain Blender action)."""
    if action is None or not hasattr(action, "g2_sequence_prop"):
        return None
    props = action.g2_sequence_prop
    if props is None:
        return None
    return bool(props.loop_frame), int(props.fps)
