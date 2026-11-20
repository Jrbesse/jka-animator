# SPDX-License-Identifier: MIT
"""B2 operators: animation.cfg segments, animevents.cfg events, saber;
B3: the check operator (animkit-check over the character/skeleton dir).

Thin delegates to the bpy-free core (anims.py — one source of logic,
B1 pattern) plus the Blender-side NLA glue (nla.py). The headless
blender/b2_cfg_check.py driver invokes these same bpy.ops.

Rules of the face: operators never parse cfg text themselves — all
format logic is animkit (via anims.py); all Blender data-model logic is
nla.py. Operators only map scene properties -> core calls -> back, and
report via self.report() + the scene's results collection.
"""
import bpy
import os

from . import addon_bridge, animimport, animkit_bridge, anims, checkop, nla, paths
from .common import JkaError


# ---------------------------------------------------------------------------
# helpers (face only — no format logic here)
# ---------------------------------------------------------------------------

def _p(context):
    return context.scene.jka_anim


def _ak(p):
    return animkit_bridge.get_animkit(p.animkit_dir)


def _need_cfg(p):
    if not p.basepath or not p.character:
        raise JkaError(
            "set the Base Path (top of the panel, the mod folder that "
            "contains models/players) and the Character")


def _need_base(p):
    if not p.basepath:
        raise JkaError(
            "set the Base Path (top of the panel, the mod folder that "
            "contains models/players)")


def _ensure_g2(p):
    """Make the jediacademy g2_sequence_prop Action property available.

    No-op when the addon is already registered (enabled in prefs);
    otherwise loads it from the 'Add-on dir' field (B1 pattern).
    """
    if not hasattr(bpy.types.Action, "g2_sequence_prop"):
        addon_bridge.ensure_addon(p.addon_dir, "g2_sequence_prop")


def _sel_segment(p):
    """The selected Segments row (the cfg's SegmentInfo, mirrored)."""
    if not p.segments:
        raise JkaError("no segments loaded — press Load in the Segments box")
    i = min(max(p.seg_selected, 0), len(p.segments) - 1)
    return p.segments[i]


def _evt_target(p):
    """The segment the Events section edits (the Events dropdown)."""
    if not p.segments:
        raise JkaError("no segments loaded — press Load in the Segments box")
    if not p.evt_segment:
        raise JkaError("pick the target segment (Events box)")
    try:
        i = int(p.evt_segment)
    except ValueError:
        raise JkaError("no target segment selected (Events box)")
    if not (0 <= i < len(p.segments)):
        raise JkaError("target segment selection is stale — press Load (Segments)")
    return p.segments[i]


def _sync_segments(p, segs, drift):
    """Mirror the core's SegmentInfos into the scene collection.

    ``drift`` maps segment name -> (has_action, drift).
    """
    p.segments.clear()
    for s in segs:
        it = p.segments.add()
        it.name = s.name
        it.first_frame = int(s.first_frame)
        it.num_frames = int(s.num_frames)
        it.loop_frames = int(s.loop_frames)
        it.fps = int(s.fps)
        has_action, drifted = drift.get(s.name, (False, False))
        it.has_action = has_action
        it.drift = drifted
    if p.seg_selected > len(p.segments) - 1:
        p.seg_selected = max(0, len(p.segments) - 1)


def _drift_map(p, segs):
    """Per-segment (has_action, drift) vs the scene's actions: the
    jediacademy importer names actions after cfg segments and stores
    (loop bool, fps) in the action's g2_sequence_prop; a loop point N>0
    is not expressible in Blender, so both 0 and N>0 read back as loop."""
    out = {}
    for s in segs:
        props = nla.action_props(nla.scene_action(s.name))
        if props is None:
            out[s.name] = (False, False)
        else:
            loop, fps = props
            cfg_loop, cfg_fps = s.expected_props()
            out[s.name] = (True, loop != cfg_loop or fps != cfg_fps)
    return out


def _sync_events(p, pairs):
    """Mirror (block_index, EventInfo) pairs into the scene collection."""
    p.events.clear()
    for idx, ev in pairs:
        it = p.events.add()
        it.etype = ev.etype
        it.key_frame = ev.key_frame
        it.data = ev.data_str
        it.line = ev.line
        it.block_index = idx
    if p.evt_selected > len(p.events) - 1:
        p.evt_selected = max(0, len(p.events) - 1)


def _sync_results(p, lines):
    """``lines``: list of (text, is_error)."""
    p.results.clear()
    for text, is_error in lines:
        it = p.results.add()
        it.text = text
        it.is_error = is_error


# ---------------------------------------------------------------------------
# Segments
# ---------------------------------------------------------------------------

class JKA_OT_SegmentsLoad(bpy.types.Operator):
    """Load animation.cfg into the Segments list (drift-checks the scene's
    actions against the cfg)"""
    bl_idname = "jka_anim.segments_load"
    bl_label = "Load segments"
    bl_description = "Parse the character's animation.cfg and refresh the " \
                     "Segments list + action drift flags"

    def execute(self, context):
        p = _p(context)
        try:
            _need_cfg(p)
            ak = _ak(p)
            segs, warns = anims.load_segments(ak, p.basepath, p.character)
            _sync_segments(p, segs, _drift_map(p, segs))
            _sync_results(p, [(f"{len(segs)} segments loaded", False)]
                          + [(w, False) for w in warns])
            return {"FINISHED"}
        except JkaError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


class JKA_OT_SegmentJump(bpy.types.Operator):
    """Set the frame to the selected segment's start; create its action +
    NLA strip when missing"""
    bl_idname = "jka_anim.segment_jump"
    bl_label = "Jump to segment"
    bl_description = "Move to the selected segment's first frame; create " \
                     "its action + NLA strip when missing"

    def execute(self, context):
        p = _p(context)
        try:
            _need_cfg(p)
            seg = _sel_segment(p)
            context.scene.frame_current = seg.first_frame
            notes = [f"frame -> {seg.first_frame} ({seg.name})"]
            if p.seg_jump_create:
                action = nla.scene_action(seg.name)
                if action is None:
                    _ensure_g2(p)
                    loop, fps = seg.expected_props()
                    action = nla.make_action(seg.name, loop, fps)
                    notes.append(f"created action {seg.name!r}")
                elif nla.action_props(action) is None:
                    _ensure_g2(p)
                    loop, fps = seg.expected_props()
                    nla.set_action_props(action, loop, fps)
                    notes.append(f"g2_sequence_prop set on {seg.name!r}")
                arm = nla.target_armature(p, context)
                if nla.strip_for_action(arm, action) is None:
                    track, _strip = nla.add_strip(arm, action,
                                                  seg.first_frame, seg.num_frames)
                    notes.append(f"NLA strip on {track.name!r}")
                else:
                    notes.append("NLA strip already present")
            _sync_results(p, [(n, False) for n in notes])
            return {"FINISHED"}
        except JkaError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


class JKA_OT_SegmentApply(bpy.types.Operator):
    """Write the selected segment's cfg loop/fps into its action's
    g2_sequence_prop"""
    bl_idname = "jka_anim.segment_apply"
    bl_label = "Apply to action"
    bl_description = "Write this segment's loop/fps from the cfg into the " \
                     "action's g2_sequence_prop (Blender can only express " \
                     "loop yes/no, not a loop point)"

    def execute(self, context):
        p = _p(context)
        try:
            _need_cfg(p)
            seg = _sel_segment(p)
            action = nla.scene_action(seg.name)
            if action is None:
                raise JkaError(f"no action named {seg.name!r} — press Jump "
                               "(create) first")
            if nla.action_props(action) is None:
                _ensure_g2(p)
            if nla.action_props(action) is None:
                raise JkaError(f"action {seg.name!r} has no g2_sequence_prop "
                               "(created outside the jediacademy importer)")
            loop, fps = seg.expected_props()
            nla.set_action_props(action, loop, fps)
            row = p.segments[min(max(p.seg_selected, 0), len(p.segments) - 1)]
            row.has_action = True
            row.drift = False
            _sync_results(p, [(f"{seg.name!r}: loop={loop} fps={fps} "
                               f"written to the action", False)])
            return {"FINISHED"}
        except JkaError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


class JKA_OT_SegmentAdd(bpy.types.Operator):
    """Append a new segment to animation.cfg (line-preserving write)"""
    bl_idname = "jka_anim.segment_add"
    bl_label = "Add segment"
    bl_description = "Append the named segment to animation.cfg (saved " \
                     "immediately; untouched lines are preserved)"

    def execute(self, context):
        p = _p(context)
        try:
            _need_cfg(p)
            name = p.seg_new_name.strip()
            if not name:
                raise JkaError("give the new segment a name")
            for s in p.segments:
                if s.name == name:
                    raise JkaError(f"segment {name!r} already exists")
            ak = _ak(p)
            info, _text = anims.add_segment(
                ak, p.basepath, p.character,
                name, p.seg_new_first, p.seg_new_num, p.seg_new_loop,
                p.seg_new_fps)
            path = anims.save_segment_doc(ak, p.basepath, p.character)
            row = p.segments.add()
            row.name = info.name
            row.first_frame = int(info.first_frame)
            row.num_frames = int(info.num_frames)
            row.loop_frames = int(info.loop_frames)
            row.fps = int(info.fps)
            row.has_action = nla.scene_action(info.name) is not None
            row.drift = False
            p.seg_selected = len(p.segments) - 1
            p.seg_new_name = ""
            _sync_results(p, [(f"added {name!r} @ {info.first_frame} and "
                               f"saved {path}", False)])
            return {"FINISHED"}
        except JkaError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

class JKA_OT_EventsLoad(bpy.types.Operator):
    """Load the animevents.cfg events of one block+segment into the list"""
    bl_idname = "jka_anim.events_load"
    bl_label = "Load events"
    bl_description = "Parse animevents.cfg and list the events of the " \
                     "selected block + segment"

    def execute(self, context):
        p = _p(context)
        try:
            _need_cfg(p)
            ak = _ak(p)
            anims.load_events(ak, p.basepath, p.character)
            seg = _evt_target(p)
            pairs = anims.events_for(ak, p.basepath, p.character,
                                     p.evt_block, seg.name)
            _sync_events(p, pairs)
            p.evt_selected = 0
            _sync_results(p, [(f"{len(pairs)} events in {p.evt_block} / "
                               f"{seg.name}", False)])
            return {"FINISHED"}
        except JkaError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


class JKA_OT_EventAdd(bpy.types.Operator):
    """Append an event to the target block (unsaved until Save)"""
    bl_idname = "jka_anim.event_add"
    bl_label = "Add event"
    bl_description = "Append the typed event to the target block (in " \
                     "memory — press Save to write)"

    def execute(self, context):
        p = _p(context)
        try:
            _need_cfg(p)
            ak = _ak(p)
            seg = _evt_target(p)
            info = anims.add_event(ak, p.basepath, p.character,
                                   p.evt_block, seg.name, p.evt_new_type,
                                   p.evt_new_key, p.evt_new_data)
            pairs = anims.events_for(ak, p.basepath, p.character,
                                     p.evt_block, seg.name)
            _sync_events(p, pairs)
            p.evt_selected = len(p.events) - 1
            _sync_results(p, [(f"added {info.label()} to {p.evt_block} / "
                               f"{seg.name} — unsaved, press Save", False)])
            return {"FINISHED"}
        except JkaError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


class JKA_OT_EventRemove(bpy.types.Operator):
    """Remove the selected event from its block (unsaved until Save)"""
    bl_idname = "jka_anim.event_remove"
    bl_label = "Remove event"
    bl_description = "Remove the selected event from the block (in memory " \
                     "— press Save to write)"

    def execute(self, context):
        p = _p(context)
        try:
            _need_cfg(p)
            if not p.events:
                raise JkaError("no events loaded — press Load (Events)")
            ak = _ak(p)
            seg = _evt_target(p)
            row = p.events[min(max(p.evt_selected, 0), len(p.events) - 1)]
            anims.remove_event(ak, p.basepath, p.character,
                               p.evt_block, row.block_index)
            pairs = anims.events_for(ak, p.basepath, p.character,
                                     p.evt_block, seg.name)
            _sync_events(p, pairs)
            _sync_results(p, [(f"removed {row.etype} @ {row.key_frame} — "
                               f"unsaved, press Save", False)])
            return {"FINISHED"}
        except JkaError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


class JKA_OT_EventsSave(bpy.types.Operator):
    """Validate-on-write: reparse + validate against the segment table,
    then write animevents.cfg (errors land in the Results box)"""
    bl_idname = "jka_anim.events_save"
    bl_label = "Save events"
    bl_description = "Validate the edited events against the segment " \
                     "table and write animevents.cfg (the file is not " \
                     "touched when validation fails)"

    def execute(self, context):
        p = _p(context)
        try:
            _need_cfg(p)
            ak = _ak(p)
            warns, path = anims.save_events(ak, p.basepath, p.character)
            _sync_results(p, [(f"saved {path}", False)]
                          + [(w, False) for w in warns])
            return {"FINISHED"}
        except JkaError as e:
            # every validation error goes to the Results box, not one
            # popup
            lines = str(e).splitlines()
            _sync_results(p, [(l, True) for l in lines])
            self.report({'ERROR'}, "write blocked — see the Results box")
            return {'CANCELLED'}


# ---------------------------------------------------------------------------
# Saber
# ---------------------------------------------------------------------------

class JKA_OT_SaberValidate(bpy.types.Operator):
    """Parse + validate saberanims.cfg (a missing file is not an error)"""
    bl_idname = "jka_anim.saber_validate"
    bl_label = "Validate saber cfg"
    bl_description = "Validate ext_data/saberanims.cfg (or the override " \
                     "path); a missing file falls back to the engine's " \
                     "built-in style sheet"

    def execute(self, context):
        p = _p(context)
        try:
            _need_base(p)
            ak = _ak(p)
            styles, errors, warnings, path = anims.validate_saberanims(
                ak, p.basepath, p.saber_cfg)
            lines = []
            if not styles:
                lines.append((f"no saberanims.cfg at {path} — the engine "
                              f"uses its built-in style sheet", False))
            for st in styles:
                lines.append((f"style {st.name}: openAnim="
                              f"{st.values.get('openanim', '')}", False))
            lines += [(e, True) for e in errors]
            lines += [(w, False) for w in warnings]
            _sync_results(p, lines)
            return {"FINISHED"}
        except JkaError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


class JKA_OT_SaberPresetApply(bpy.types.Operator):
    """Apply a saber preset: action + g2 props + NLA strip, and the cfg
    segment (added + saved when new)"""
    bl_idname = "jka_anim.saber_preset_apply"
    bl_label = "Apply saber preset"
    bl_description = "Create the preset's action (g2_sequence_prop " \
                     "loop=False, fps=20) + NLA strip on the armature, and " \
                     "its animation.cfg segment (next free frame, " \
                     "num=20, loop=-1)"

    def execute(self, context):
        p = _p(context)
        try:
            _need_cfg(p)
            ak = _ak(p)
            presets = anims.saber_presets(ak, p.basepath, p.saber_cfg)
            try:
                idx = int(p.saber_preset or 0)
            except ValueError:
                raise JkaError("no saber preset selected")
            if not (0 <= idx < len(presets)):
                raise JkaError("saber preset selection is stale — "
                               "re-open the preset dropdown")
            preset = presets[idx]

            # 1. the cfg segment (the engine fires the saber from the cfg).
            #    For an EXISTING segment the cfg is the truth (loop/fps come
            #    from it — e.g. BOTH_STAND1 loops in the cfg); the preset's
            #    defaults (num=20, fps=20, loop=-1) apply to new segments.
            segs, _warns = anims.load_segments(ak, p.basepath, p.character)
            existing = next((s for s in segs if s.name == preset.name), None)
            if existing is None:
                first = anims.next_free_frame(ak, p.basepath, p.character)
                info, _text = anims.add_segment(
                    ak, p.basepath, p.character, preset.name,
                    first, preset.num_frames, preset.loop_frames, preset.fps)
                path = anims.save_segment_doc(ak, p.basepath, p.character)
                first, num = first, preset.num_frames
                loop, fps = preset.loop_frames != -1, preset.fps
                cfg_note = (f"added segment {preset.name!r} @ {first} to "
                            f"animation.cfg (saved)")
                row = p.segments.add()
                row.name = info.name
                row.first_frame = int(info.first_frame)
                row.num_frames = int(info.num_frames)
                row.loop_frames = int(info.loop_frames)
                row.fps = int(info.fps)
                row.has_action = False
                row.drift = False
                p.seg_selected = len(p.segments) - 1
            else:
                first, num = existing.first_frame, existing.num_frames
                loop, fps = existing.loop_frames != -1, existing.fps
                cfg_note = (f"segment {preset.name!r} already in "
                            f"animation.cfg (unchanged)")

            # 2. the action (named exactly like the cfg segment)
            action = nla.scene_action(preset.name)
            if action is None:
                _ensure_g2(p)
                action = nla.make_action(preset.name, loop, fps)
                action_note = f"created action {preset.name!r}"
            else:
                action_note = f"reused action {preset.name!r}"

            # 3. the NLA strip (Sequences Layer 1 when free)
            arm = nla.target_armature(p, context)
            if nla.strip_for_action(arm, action) is None:
                track, _strip = nla.add_strip(arm, action, first, num)
                strip_note = f"NLA strip on {track.name!r}"
            else:
                strip_note = "NLA strip already present"

            context.scene.frame_current = first
            _sync_results(p, [(action_note, False), (strip_note, False),
                              (cfg_note, False)])
            return {"FINISHED"}
        except JkaError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


# ---------------------------------------------------------------------------
# Import a named animation (or a custom range) onto the target rig
# ---------------------------------------------------------------------------

class JKA_OT_AnimImport(bpy.types.Operator):
    """Import the picked segment (or the typed custom range) from the
    character's GLA as a new action on the target rig"""
    bl_idname = "jka_anim.anim_import"
    bl_label = "Import animation"
    bl_description = ("Pull the picked segment (or the typed custom range) out "
                      "of the character's GLA as a new action on the target "
                      "rig — with a timeline marker at the range's first "
                      "frame and an NLA strip. A re-import replaces the "
                      "existing action of the same name")

    custom: bpy.props.BoolProperty(
        name="Custom range", default=False,
        description="Import the typed custom range instead of the picked "
                    "segment")

    def execute(self, context):
        p = _p(context)
        try:
            _need_cfg(p)
            # "" survives only in stale saved files; "CUSTOM" is the
            # live sentinel (RNA drops empty enum ids).
            use_segment = (not self.custom) and \
                p.imp_segment not in ("", "CUSTOM")
            if use_segment:
                try:
                    i = int(p.imp_segment)
                except ValueError:
                    raise JkaError("no segment picked (Import box)")
                if not p.segments or not (0 <= i < len(p.segments)):
                    raise JkaError(
                        "segment selection is stale — press Load (Segments)")
                seg = p.segments[i]
                name = seg.name
                first, num = int(seg.first_frame), int(seg.num_frames)
                loop, fps = seg.expected_props()
            else:
                name = p.imp_name.strip()
                if not name:
                    raise JkaError(
                        "pick a segment, or give the custom import a name")
                first, num = int(p.imp_first), int(p.imp_frames)
                if num < 1:
                    raise JkaError("the custom range needs at least 1 frame")
                loop, fps = False, int(p.imp_fps)
            if nla.scene_action(name) is not None:
                nla.purge_action(name)
            gla = paths.derive_ref_gla(p.basepath, p.character, p.ref_gla)
            target = nla.target_armature(p, context)
            _ensure_g2(p)
            _action, notes = animimport.import_range(
                gla, target, name, first, num, loop, fps,
                addon_dir=p.addon_dir, animkit_dir=p.animkit_dir)
            context.scene.frame_current = first
            _sync_results(p, [(n, False) for n in notes] + [
                (f"{name!r}: {num} frames from {os.path.basename(gla)} "
                 f"imported into {target.name!r}", False)])
            return {"FINISHED"}
        except JkaError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


# ---------------------------------------------------------------------------
# Timeline markers (labels) — the in-plugin analogue of the user's
# 'timeline markers from animation.cfg' script
# ---------------------------------------------------------------------------

class JKA_OT_MarkersFromSegments(bpy.types.Operator):
    """One timeline marker per loaded segment, on its first frame
    (+ the offset field)"""
    bl_idname = "jka_anim.markers_from_segments"
    bl_label = "Markers from segments"
    bl_description = ("One timeline marker per loaded segment, on the "
                      "segment's first frame plus the offset field. The GLA "
                      "workflow is 0-based like the engine, so the offset "
                      "defaults to 0 (the +1 of 1-based manual scripts is "
                      "one click away). Markers that already exist are "
                      "moved, not duplicated")

    def execute(self, context):
        p = _p(context)
        try:
            if not p.segments:
                raise JkaError(
                    "no segments loaded — press Load in the Segments box")
            created, moved = animimport.add_markers_from_segments(p)
            _sync_results(p, [
                (f"{created} markers created, {moved} moved "
                 f"(offset {p.marker_offset})", False)])
            return {"FINISHED"}
        except JkaError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


class JKA_OT_MarkersClear(bpy.types.Operator):
    """Remove every timeline marker in the scene"""
    bl_idname = "jka_anim.markers_clear"
    bl_label = "Clear markers"
    bl_description = "Remove every timeline marker in the scene"

    def execute(self, context):
        p = _p(context)
        n = animimport.clear_markers()
        _sync_results(p, [(f"{n} markers removed", False)])
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# B3: check
# ---------------------------------------------------------------------------

class JKA_OT_CheckRun(bpy.types.Operator):
    """Run animkit's check (GLA/GLM + cfgs + skin) over the character or
    skeleton dir; the findings land in the Results collection (the
    bpy-free core is checkop.py — no format logic in this face)"""
    bl_idname = "jka_anim.check_run"
    bl_label = "Run check"
    bl_description = ("Run animkit's check over models/players/<character> "
                      "(GLA/GLM + cfgs + skin) and list the findings in "
                      "the Results collection")

    def execute(self, context):
        p = _p(context)
        try:
            _need_cfg(p)
            ak = _ak(p)
            d = checkop.resolve_char_dir(p.basepath, p.character)
            res = checkop.check_dir(ak, d)
            _sync_results(p, res.lines())
            self.report({'INFO'} if res.ok else {'WARNING'}, res.summary())
            return {'FINISHED'}
        except JkaError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


CLASSES = (
    JKA_OT_SegmentsLoad,
    JKA_OT_SegmentJump,
    JKA_OT_SegmentApply,
    JKA_OT_SegmentAdd,
    JKA_OT_EventsLoad,
    JKA_OT_EventAdd,
    JKA_OT_EventRemove,
    JKA_OT_EventsSave,
    JKA_OT_SaberValidate,
    JKA_OT_SaberPresetApply,
    JKA_OT_AnimImport,
    JKA_OT_MarkersFromSegments,
    JKA_OT_MarkersClear,
    JKA_OT_CheckRun,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
