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
from mathutils import Matrix, Quaternion, Vector

from .common import JkaError, MIRROR, RIG_NAME, REF_NAME


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


def target_armature(p, context):
    """The armature the JKA NLA ops (jump / saber / import) act on.

    The panel's `target_arm` names the object; empty or stale falls back
    to the working skeleton ('skeleton_root' or 'rig_armature' — the
    export mirror, under either name), then to find_armature. Defaulting
    to the working skeleton (not the active object) is deliberate: after
    a reference load the active armature is the reference, and keying
    presets/imports onto it was Sheng retest #3.
    """
    name = p.target_arm
    if name not in ("", "AUTO"):
        o = context.scene.objects.get(name)
        if o is not None and o.type == "ARMATURE":
            return o
    for nm in (MIRROR, RIG_NAME):
        o = context.scene.objects.get(nm)
        if o is not None and o.type == "ARMATURE":
            return o
    return find_armature(context)


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


def purge_action(name):
    """Remove the action named ``name`` and every NLA strip that uses it
    (on any armature in the scene). Re-importing a segment replaces its
    action rather than producing ``NAME.001``. Returns the removed action
    (or None when there was none); JkaError when something still uses the
    action and it cannot be removed safely."""
    old = scene_action(name)
    if old is None:
        return None
    for o in bpy.data.objects:
        if o.type != "ARMATURE" or o.animation_data is None:
            continue
        ad = o.animation_data
        for track in list(ad.nla_tracks):
            for s in list(track.strips):
                if s.action is old:
                    track.strips.remove(s)
        if ad.action is old:
            ad.action = None
            if hasattr(ad, "action_slot"):
                ad.action_slot = None
    for slot in list(old.slots):
        try:
            old.slots.remove(slot)
        except (RuntimeError, ValueError):
            pass
    if old.users > 0:
        raise JkaError(
            f"action {name!r} is still in use by something outside the "
            "JKA NLA tracks — delete those references first")
    bpy.data.actions.remove(old)
    return old


def action_props(action):
    """(loop, fps) from the action's g2_sequence_prop, or None when the
    addon's property is absent (plain Blender action)."""
    if action is None or not hasattr(bpy.types.Action, "g2_sequence_prop"):
        return None
    props = action.g2_sequence_prop
    if props is None:
        return None
    return bool(props.loop_frame), int(props.fps)


# ---------------------------------------------------------------------------
# Named-animation retarget (Sheng retest #2/#4): the GLA importer keys a
# fresh throwaway armature; this moves that action onto any target rig.
# ---------------------------------------------------------------------------

def _topo_order(arm):
    """The armature's pose bones, parents before children (the armature's
    own hierarchy order already satisfies this; verified defensively)."""
    bones = list(arm.data.bones)
    parents = {b.name: (b.parent.name if b.parent else None) for b in bones}
    order = []
    seen = set()

    def visit(name):
        if name in seen or name not in parents:
            return
        par = parents[name]
        if par is not None:
            visit(par)
        seen.add(name)
        order.append(name)

    for b in bones:
        visit(b.name)
    missing = [b.name for b in bones if b.name not in seen]
    if missing:  # a cycle in the hierarchy — fall back to file order
        return list(arm.pose.bones)
    return [arm.pose.bones[n] for n in order]


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
    """The action's fcurve value for (bone, property) at ``frame``: one
    fcurve per array index (location = 3, quaternion = 4) — the tuple of
    component values, or None when the channel is unkeyed. This is pure
    keyed data (``fc.evaluate`` interpolates), never an evaluated
    depsgraph read — reliable in ``--background`` where
    ``pose_bone.matrix`` is not."""
    want = f'pose.bones["{bone}"].{prop}'
    vals = {}
    for fc in _action_fcurves(action):
        if fc.data_path == want:
            vals[fc.array_index] = fc.evaluate(frame)
    if not vals:
        return None
    n = max(vals) + 1
    return tuple(vals.get(i, 0.0) for i in range(n))


def _pose_local_matrix(loc, quat):
    """The pose-local (matrix_basis) 4x4 from location + rotation
    quaternion (scale 1 — the GLA importer keys location +
    rotation_quaternion only)."""
    return (Matrix.Translation(Vector(loc))
            @ Quaternion(quat).to_matrix().to_4x4())


def _full_chain_bones(src_arm, tgt_arm):
    """Names whose ENTIRE ancestor chain matches name-for-name in both
    rigs — only for these does the retarget reduce to a plain local copy
    (a diverging higher chain re-aims through the divergence)."""
    out = set()
    for b in src_arm.data.bones:
        if b.name not in tgt_arm.data.bones:
            continue
        s, t = b, tgt_arm.data.bones[b.name]
        ok = True
        while s.parent is not None:
            tp = t.parent.name if t.parent else None
            if tp != s.parent.name:
                ok = False
                break
            s, t = s.parent, t.parent
        if ok:
            out.add(b.name)
    return out


def _rest_data(arm):
    """(rest, rel, restworld) per bone name, from the REST
    ``bone.matrix_local`` (static, never evaluated):
      rest      bone.matrix_local (armature space)
      rel       bone.matrix_local @ parent.matrix_local⁻¹ (root: I)
      restworld composed rest world (root: rest; child: parent @ rel)
    """
    rest, rel, restworld = {}, {}, {}
    for b in arm.data.bones:
        par = b.parent
        rest[b.name] = b.matrix_local.copy()
        rel[b.name] = (Matrix.Identity(4) if par is None
                       else b.matrix_local @ par.matrix_local.inverted())
        restworld[b.name] = (rest[b.name].copy() if par is None
                             else restworld[par.name] @ rel[b.name])
    return rest, rel, restworld


def retarget_action(src_action, src_arm, target_arm, name, first, num,
                    loop, fps):
    """Copy ``src_action`` (keyed on ``src_arm``) into a NEW action on
    ``target_arm`` named ``name``, with the g2 props + an NLA strip.

    Per frame, per bone, in the TARGET's topological order:

        W_t = M_t(parent_t) @ M_src(parent_src)⁻¹ @ W_src(bone)

    (root bone: W_t = W_src). All matrices are armature-space pose
    matrices, so object scale/parenting never enter.

    The source is evaluated at action-local frame ``f`` (the RANGE
    import keys 0..num-1); the target is keyed at ``first + f``.

    Two execution paths, no evaluated depsgraph reads (``pose_bone.matrix``
    is stale/unstable in ``--background`` — it is the root cause of the
    Sheng-retest fidelity divergence):

    * full-chain bones (the entire ancestor chain matches name-for-name):
      the source's keyed location + rotation_quaternion are copied
      VERBATIM onto the target. Bit-exact — this is the form the GLA
      importer keyed and the exporter re-samples, so the re-exported GLA
      round-trips unchanged.
    * divergent-chain bones (the IK rig's finger chains: j2 under j1,
      not the hand): the world formula above, with every read composed
      from keyed fcurve locals + rest ``matrix_local`` (pure math).
      ``M_t(parent_t)`` is the target parent's world computed earlier in
      this same pass (topological order); a parent absent from the
      source (an IK control) falls back to its rest world.

    Bones of the target that do not exist in the source (IK controls)
    are never touched. Keys are location + rotation_quaternion — the
    importer's keyform, one key per frame.
    """
    scene = bpy.context.scene
    ad = target_arm.animation_data or target_arm.animation_data_create()
    prev_action = ad.action
    prev_slot = getattr(ad, "action_slot", None)
    ad.use_nla = True
    action = make_action(name, loop, fps)
    slot = _action_slot(action)
    ad.action = action
    if hasattr(ad, "action_slot"):
        ad.action_slot = slot

    sad = src_arm.animation_data
    prev_src_action = sad.action if sad is not None else None
    if sad is not None:
        sad.action = src_action

    # The RANGE import keys the throwaway at ACTION-LOCAL frames
    # (0..num-1 — JAG2GLA's else branch enumerates self.frames from 0),
    # so the source is read at local frame f while the target is
    # keyed at the absolute frame first+f.
    src_names = {b.name for b in src_arm.data.bones}
    full_chain = _full_chain_bones(src_arm, target_arm)
    src_rest, src_rel, _ = _rest_data(src_arm)
    tgt_rest, tgt_rel, tgt_restworld = _rest_data(target_arm)
    tgt_order = _topo_order(target_arm)
    scene.frame_start = 0
    scene.frame_end = max(int(scene.frame_end), int(num) - 1)
    for f in range(int(num)):
        frame = int(first) + f
        scene.frame_set(f)
        memo = {}

        def src_world(bname):
            """The source bone's pose world at local frame ``f`` —
            composed from keyed locals + rest, no evaluation."""
            if bname in memo:
                return memo[bname]
            loc = _fc_value(src_action, bname, "location", f)
            quat = _fc_value(src_action, bname, "rotation_quaternion", f)
            if loc is None or quat is None:
                memo[bname] = None
                return None
            P = _pose_local_matrix(loc, quat)
            b = src_arm.data.bones[bname]
            par = b.parent
            w = (src_rest[bname] @ P if par is None
                 else src_world(par.name) @ src_rel[bname] @ P)
            memo[bname] = w
            return w

        tgt_world = {}
        for pb in tgt_order:
            bname = pb.name
            if bname not in src_names:
                continue  # IK control — never touched
            par_t = pb.bone.parent
            par_t_name = par_t.name if par_t else None
            if bname in full_chain:
                loc = _fc_value(src_action, bname, "location", f)
                quat = _fc_value(src_action, bname,
                                 "rotation_quaternion", f)
                if loc is None or quat is None:
                    continue
                pb.location = Vector(loc)
                pb.rotation_quaternion = Quaternion(quat)
                P = _pose_local_matrix(loc, quat)
                w = (tgt_rest[bname] @ P if par_t_name is None
                     else tgt_world.get(par_t_name,
                                        tgt_restworld[par_t_name])
                     @ tgt_rel[bname] @ P)
            else:
                w_src = src_world(bname)
                if w_src is None:
                    continue
                if par_t_name is None:
                    w = w_src
                else:
                    sb = src_arm.data.bones[bname]
                    src_par_name = sb.parent.name if sb.parent else None
                    m_par_src = (src_world(src_par_name) if src_par_name
                                 else Matrix.Identity(4))
                    m_par_t = tgt_world.get(par_t_name,
                                            tgt_restworld[par_t_name])
                    w = m_par_t @ m_par_src.inverted() @ w_src
                pb.matrix = w
            tgt_world[bname] = w
        for pb in tgt_order:
            if pb.name in tgt_world:
                pb.keyframe_insert('location', frame=frame)
                pb.keyframe_insert('rotation_quaternion', frame=frame)
        bpy.context.view_layer.update()

    # restore both armatures' active-action state (the slot is restored
    # WHILE an action is still assigned — Blender refuses a slot on a
    # bare action-less anim data)
    if prev_action is not None and hasattr(ad, "action_slot"):
        ad.action_slot = prev_slot
    ad.action = prev_action
    if sad is not None:
        sad.action = prev_src_action

    track, strip = add_strip(target_arm, action, int(first), int(num))
    scene.frame_current = int(first)
    notes = [f"action {name!r}: {num} frames on {target_arm.name!r} "
             f"(track {track.name!r})"]
    return action, strip, notes
