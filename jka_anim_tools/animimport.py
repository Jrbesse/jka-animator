"""animimport — bring a NAMED animation (or a custom frame range) from the
character's .gla onto any rig in the scene.

The engine GLA import is the proven jediacademy `import_scene.gla` RANGE
import (loadAnimations='RANGE', startFrame/numFrames): it keys a FRESH
'skeleton_root' armature, one location + rotation_quaternion key per bone
per frame, pose-local — which is exactly the form the GLA exporter re-samples
(and what the working skeleton's pose is defined in).

Flow:
  1. free the name 'skeleton_root' (the working mirror, if it still wears
     it, moves to 'rig_armature' — the same rename the reference load does)
  2. RANGE-import the frame range -> throwaway armature + imported action
  3. retarget_action: copy the action onto the TARGET rig (the panel's
     'Rig target'; default the working skeleton). Same hierarchy => exact
     copy; the IK rig's finger chains get re-aimed (j2 under j1, not the
     hand), IK control bones untouched
  4. timeline marker at the range's first frame (the in-plugin analogue
     of the user's 'timeline markers from animation.cfg' script), NLA
     strip, throwaway deleted

bpy-only: the operator (cfgops.JKA_OT_AnimImport) and the headless CLI
(blender/b5_import_check.py) are thin wrappers.
"""

import bpy
from pathlib import Path

from . import addon_bridge, animkit_bridge, nla
from .common import JkaError, MIRROR, RIG_NAME

TMP_NAME = "_jka_import_tmp"


# ---------------------------------------------------------------------------
# Name hygiene
# ---------------------------------------------------------------------------

def free_mirror_name():
    """Guarantee no OBJECT (and no armature data squatting the name) occupies
    'skeleton_root', so the throwaway import creates a fresh one.

    The working mirror, if it still wears the name, moves to
    'rig_armature' (the same move refimport.move_rig_armature_away makes
    for a reference load). Unlike that function this one is allowed to
    run with the reference already present — importing must work in any
    scene state, not only before the reference load.
    """
    obj = bpy.data.objects.get(MIRROR)
    if obj is not None and obj.type == "ARMATURE":
        if bpy.data.objects.get(RIG_NAME) is not None:
            raise JkaError(
                f"both {MIRROR!r} and {RIG_NAME!r} objects exist — "
                "one of them should be the reference; load the reference "
                "GLA first (it renames the mirror)")
        obj.name = RIG_NAME
        obj.data.name = RIG_NAME + "_data"
    # armature DATA blocks squatting the object name (the IK rig's
    # squat, or a reference whose data was never renamed) — the importer
    # would key its animation onto that data.
    for o in bpy.data.objects:
        if o.type == "ARMATURE" and o.data.name == MIRROR:
            o.data.name = o.name + "_data"


# ---------------------------------------------------------------------------
# The import
# ---------------------------------------------------------------------------

def _ensure_importer(addon_dir):
    """The RANGE import lives in the jediacademy addon (the GLA/GLM
    importer) — same ensure-addon pattern as the reference load.
    Registering the addon also registers its g2_sequence_prop Action
    property, which the importer writes. (Do NOT probe
    ``bpy.ops.import_scene.gla`` for availability — 5.x ops access is
    lazy and unvalidated; the bridge's g2-property probe is the truth.)"""
    addon_bridge.ensure_addon(addon_dir, "import_scene.gla")


def _imported_action(throw):
    """The action the RANGE import keyed: the throwaway's active action,
    or its NLA strip's action."""
    ad = throw.animation_data
    if ad is None:
        raise JkaError("import created no animation data on the throwaway")
    action = ad.action
    if action is not None:
        return action
    for track in ad.nla_tracks:
        for strip in track.strips:
            if strip.action is not None:
                return strip.action
    raise JkaError(
        "the import keyed no action on the throwaway armature — "
        "check the frame range against the GLA")


def _cleanup_throwaway(throw, action):
    data = throw.data  # capture BEFORE the object removal dangles it
    bpy.data.objects.remove(throw, do_unlink=True)
    if action is not None and action.users == 0:
        bpy.data.actions.remove(action)
    if data is not None and data.users == 0:
        bpy.data.armatures.remove(data)


def _gl_frame_count(gla, animkit_dir):
    """Total frames in the GLA (validation for custom ranges)."""
    import importlib
    animkit_bridge.get_animkit(animkit_dir)
    gla_mod = importlib.import_module("animkit.gla")
    hdr = gla_mod.parse_gla(Path(gla).read_bytes())
    return int(hdr.num_frames)


def import_range(gla, target, name, first, num, loop, fps,
                 addon_dir="", animkit_dir="", context=None):
    """Import GLA frames ``first .. first+num-1`` as a new action on
    ``target``. Returns (action, notes).

    ``name`` is the action/marker name — the segment name for a named
    import, the user's choice for a custom range. ``loop``/``fps`` come
    from the segment for named imports (the exporter reads them off the
    action, exactly like the reference import does).
    """
    context = context or bpy.context
    if num <= 0:
        raise JkaError(f"frame count must be positive (got {num})")
    total = _gl_frame_count(gla, animkit_dir)
    if first < 0 or first + num > total:
        raise JkaError(
            f"frames {first}..{first + num - 1} are outside the GLA "
            f"(it holds {total})")

    free_mirror_name()
    _ensure_importer(addon_dir)
    bpy.ops.import_scene.gla(
        filepath=gla, basepath="", loadAnimations="RANGE",
        startFrame=int(first), numFrames=int(num))

    throw = bpy.data.objects.get(MIRROR)
    if throw is None or throw.type != "ARMATURE":
        raise JkaError(
            "the import did not create a throwaway "
            f"{MIRROR!r} armature — check the GLA path: {gla}")
    throw.name = TMP_NAME

    src_action = _imported_action(throw)
    try:
        action, _strip, notes = nla.retarget_action(
            src_action, throw, target, name, first, num, loop, fps)
    except Exception:
        _cleanup_throwaway(throw, src_action)
        raise
    _cleanup_throwaway(throw, src_action)

    _add_marker(name, int(first))
    return action, notes


# ---------------------------------------------------------------------------
# Timeline markers — the in-plugin analogue of the user's
# 'timeline markers from animation.cfg' script.
# ---------------------------------------------------------------------------

def add_markers_from_segments(p, names=None):
    """One timeline marker per segment (all loaded, or ``names`` filtered).
    The GLA workflow is 0-based like the engine, so markers land EXACTLY
    on the segment's first frame by default — the script's +1 (1-based
    manual work) is available as the offset field in the panel.
    Markers whose name matches an existing one are moved, not duplicated.
    Returns (created, moved)."""
    markers = bpy.context.scene.timeline_markers
    by_name = {m.name: m for m in markers}
    created = moved = 0
    for seg in p.segments:
        if names is not None and seg.name not in names:
            continue
        if seg.name in by_name:
            m = by_name[seg.name]
            m.frame = seg.first_frame + p.marker_offset
            moved += 1
        else:
            m = markers.new(name=seg.name, frame=seg.first_frame)
            m.frame = seg.first_frame + p.marker_offset
            by_name[seg.name] = m
            created += 1
    return created, moved


def clear_markers():
    """Remove every timeline marker. Returns the count removed."""
    markers = bpy.context.scene.timeline_markers
    n = len(markers)
    markers.clear()
    return n


def _add_marker(name, frame):
    """A marker for one imported range (deduped by name)."""
    markers = bpy.context.scene.timeline_markers
    for m in markers:
        if m.name == name:
            m.frame = frame
            return
    m = markers.new(name=name, frame=frame)
    m.frame = frame
