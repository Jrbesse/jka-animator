# SPDX-License-Identifier: MIT
"""N-panel UI + the scene properties the operators read.

Properties live on bpy.types.Scene so they persist while the file is open
and survive operator invocations; the headless scripts use the same
values via the CLI. Top-level fields are also mirrored to a user-config
JSON across Blender restarts (persist.py, review item #10).

ONE base path (review item #4): ``basepath`` (the mod folder containing
``models/players/``) + ``character`` are the only location fields; the
reference GLA, the export output and the in-GLA path are DERIVED from
them (paths.py) and every field that used to ask for a folder again is
gone.

Labels (review item #3): every property row carries an explicit text
label — nothing relies on hover tooltips.

Icons (review item #5): icons validate per-Blender-version enum lists;
``_op`` drops the icon instead of crashing the panel draw when a value
is missing on the user's Blender (the 5.1 crash was icon='BONE').

Sections
--------
Base:  Base Path + Character (the only location fields)
B1:    Reference (matching) / Rig / Export GLA
B2:    Segments (animation.cfg) / Events (animevents.cfg) /
       Saber (saberanims.cfg) — cfgops.py operators over the
       bundled animkit cfg layer (decision #12)
B3:    Check (animkit-check) / Fingers (presets) / Results
Deps:  jediacademy Add-on Dir + animkit override (rarely needed)
"""
import bpy

from . import animkit_bridge, anims, persist

# File-browser subtypes: bpy.props.FileType was removed in Blender 5.3 —
# the raw subtype identifiers survive (in 4.x FileType.ANY/.DIRECTORY are
# exactly these strings), so they work on both.
try:
    _FT = bpy.props.FileType
    FILE_ANY = _FT.ANY        # 'FILE_PATH' on 4.x
    FILE_DIR = _FT.DIRECTORY  # 'DIR_PATH' on 4.x
except AttributeError:
    FILE_ANY = "FILE_PATH"    # Blender 5.3+
    FILE_DIR = "DIR_PATH"

MODES = (
    ("RANGE", "Range", "start..start+frames-1 in one action (fast)"),
    ("CFG", "Cfg", "one NLA strip per animation.cfg segment (slow on big skeletons)"),
    ("ALL", "All", "every frame in one action (slow — do not use on stock files)"),
    ("NONE", "None", "geometry only, no animation"),
)

# How many segment rows to draw at most (stock _humanoid has 1668 —
# drawing them all is what made the panel sluggish, review item #6).
SEG_ROW_CAP = 50

# The editable event types (NPC_stats.cpp switch cases) and the per-type
# data-field help the panel shows under the Data field.
EVT_TYPES = tuple(
    (t, t.replace("AEV_", ""), anims.data_help(t))
    for t in anims.EDITABLE_ETYPES
)


# The only kwargs UILayout.operator accepts on every supported Blender —
# everything else is an OPERATOR PROPERTY and must be set on the returned
# op object (5.3 rejects property kwargs outright; older versions happened
# to forward them, so this split is the portable form).
_UI_KWARG_NAMES = ("text_ctxt", "translate", "emboss", "depress",
                   "icon_value", "search_weight")


def _op(layout, op_idname, icon=None, text=None, **kw):
    """``layout.operator`` that is safe across Blender 4.x/5.x.

    Two crash classes this kills (review item #5):

    * an icon enum value missing on the RUNNING Blender raises TypeError
      at draw time (the 5.1 ``icon='BONE'`` crash) — a bad icon is
      dropped and the button stays functional;
    * operator PROPERTIES (``preset='GRASP'`` etc.) passed as kwargs:
      5.3 raises ``invalid keyword argument(s)``. Properties are set on
      the returned op object instead, which every version accepts.
    """
    props = {k: v for k, v in kw.items() if k not in _UI_KWARG_NAMES}
    uikw = {k: v for k, v in kw.items() if k in _UI_KWARG_NAMES}

    def _finish(op):
        for k, v in props.items():
            setattr(op, k, v)
        return op

    if icon is not None:
        try:
            return _finish(layout.operator(op_idname, text=text,
                                           icon=icon, **uikw))
        except TypeError:
            pass  # icon missing on this Blender — retry without it
    return _finish(layout.operator(op_idname, text=text, **uikw))


def _evt_segment_items(prop, context):
    """The Events dropdown: the loaded Segments (id = collection index).

    Callback arg order is version-dependent (4.x: (context, prop),
    5.3+: (prop, context)) — resolve whichever arg is the real context.
    """
    if hasattr(prop, "scene"):
        context = prop
    p = context.scene.jka_anim
    items = [(str(i), s.name, "") for i, s in enumerate(p.segments)]
    return items or [("", "(load segments first)", "")]


def _saber_preset_items(prop, context):
    """The Saber preset dropdown: guard + one attack per saber style
    (re-read from the cfg on each redraw; never raises into the UI)."""
    if hasattr(prop, "scene"):
        context = prop
    p = context.scene.jka_anim
    if not p.basepath:
        return [("", "(set the base path first)", "")]
    try:
        ak = animkit_bridge.get_animkit(p.animkit_dir)
        presets = anims.saber_presets(ak, p.basepath, p.saber_cfg)
        return [(str(i), pr.label, "") for i, pr in enumerate(presets)]
    except Exception:
        return [("", "(animkit unavailable)", "")]


def _matched_segments(p):
    """Indices of the segment rows matching the filter (case-insensitive
    substring; empty filter = all). The list can be 1600+ rows — this is
    the only per-redraw work, and it is a plain string scan."""
    f = p.seg_filter.strip().lower()
    if not f:
        return list(range(len(p.segments)))
    return [i for i, s in enumerate(p.segments) if f in s.name.lower()]


class JkaAnim_Segment(bpy.types.PropertyGroup):
    """One animation.cfg segment. Read-only here — the row is the cfg's
    display (Load refreshes it); Jump/Apply touch the scene, the file is
    edited via the core (anims.py) and written by the add/save ops."""
    name: bpy.props.StringProperty(name="Name")
    first_frame: bpy.props.IntProperty(name="First")
    num_frames: bpy.props.IntProperty(name="Frames")
    loop_frames: bpy.props.IntProperty(name="Loop")
    fps: bpy.props.IntProperty(name="FPS")
    has_action: bpy.props.BoolProperty(name="Has action")
    drift: bpy.props.BoolProperty(name="Drift")


class JkaAnim_Event(bpy.types.PropertyGroup):
    """One animevents.cfg event (one block+segment pair's view)."""
    etype: bpy.props.StringProperty(name="Type")
    key_frame: bpy.props.IntProperty(name="Key frame")
    data: bpy.props.StringProperty(name="Data")
    line: bpy.props.IntProperty(name="Line")
    # position in the BLOCK's event list (what remove_event takes)
    block_index: bpy.props.IntProperty(name="Block index")


class JkaAnim_Result(bpy.types.PropertyGroup):
    """One Results line (operator output: notes, warnings, errors)."""
    text: bpy.props.StringProperty(name="Result")
    is_error: bpy.props.BoolProperty(name="Error")


class JkaAnim_PropGroup(bpy.types.PropertyGroup):
    # --- the ONE location (persisted) ---
    basepath: bpy.props.StringProperty(update=persist.on_change,
        name="Base Path", subtype=FILE_DIR,
        description="The mod folder that CONTAINS models/players — set it "
                    "once; the reference GLA, output and cfgs all derive "
                    "from it")
    character: bpy.props.StringProperty(update=persist.on_change,
        name="Character", default="_humanoid",
        description="The folder under models/players you are working on "
                    "(a real character or _humanoid)")
    # --- reference (matching) ---
    ref_gla: bpy.props.StringProperty(update=persist.on_change,
        name="Reference GLA", subtype=FILE_ANY,
        description="The reference .gla to import for matching. Leave "
                    "empty to use <base>/models/players/<character>/ "
                    "<character>.gla (or the stock _humanoid GLA)")
    ref_mode: bpy.props.EnumProperty(update=persist.on_change,
        name="Import mode", items=MODES, default="RANGE")
    ref_start: bpy.props.IntProperty(update=persist.on_change,
        name="Start frame", default=0, min=0,
        description="Range mode: first frame")
    ref_frames: bpy.props.IntProperty(update=persist.on_change,
        name="Frames", default=240, min=1,
        description="Range mode: frame count")
    # --- export ---
    exp_ref: bpy.props.StringProperty(update=persist.on_change,
        name="Reference GLA (in-GLA)",
        default="models/players/_humanoid/_humanoid.gla",
        description="Base-relative reference GLA — copies bone indices. "
                    "The stock _humanoid is right for character work")
    exp_custom_frames: bpy.props.BoolProperty(update=persist.on_change,
        name="Custom frame range", default=False,
        description="Off: use the scene's current frame range")
    exp_frame_start: bpy.props.IntProperty(update=persist.on_change,
        name="Frame Start", default=0, min=0)
    exp_frame_end: bpy.props.IntProperty(update=persist.on_change,
        name="Frame End", default=239, min=0)
    # --- dependencies (rarely needed; persisted) ---
    addon_dir: bpy.props.StringProperty(update=persist.on_change,
        name="Jedi Academy Add-on Dir", subtype=FILE_DIR,
        description="Only when the separately-installed jediacademy "
                    "add-on is NOT enabled in Preferences: the directory "
                    "that CONTAINS the 'jediacademy' package folder")
    animkit_dir: bpy.props.StringProperty(update=persist.on_change,
        name="AnimKit Dir (override)", subtype=FILE_DIR,
        description="Leave empty: the copy bundled with this add-on is "
                    "used. Override only to test a different animkit")
    # --- B2: cfg editor (segments / events / saber) ---
    saber_cfg: bpy.props.StringProperty(update=persist.on_change,
        name="Saber cfg (override)", subtype=FILE_ANY,
        description="Explicit saberanims.cfg path; empty = "
                    "<base>/ext_data/saberanims.cfg")
    segments: bpy.props.CollectionProperty(type=JkaAnim_Segment)
    seg_selected: bpy.props.IntProperty(name="Selected segment")
    seg_filter: bpy.props.StringProperty(
        name="Filter",
        description="Substring filter for the segment list (e.g. "
                    "BOTH_SPRINT)")
    seg_jump_create: bpy.props.BoolProperty(
        name="Create action/strip if missing", default=True,
        description="Jump: also create the segment's action + NLA strip "
                    "when missing")
    seg_new_name: bpy.props.StringProperty(name="Segment name")
    seg_new_first: bpy.props.IntProperty(name="First frame", default=0, min=0)
    seg_new_num: bpy.props.IntProperty(name="Frames", default=20, min=1)
    seg_new_loop: bpy.props.IntProperty(
        name="Loop point", default=-1, min=-1,
        description="-1 no loop, 0 loop at frame 0, N>0 loop point N "
                    "(a GLA export through Blender can only write "
                    "loop yes/no — N>0 is kept in the cfg, read-only here)")
    seg_new_fps: bpy.props.IntProperty(name="FPS", default=20, min=1)
    events: bpy.props.CollectionProperty(type=JkaAnim_Event)
    evt_selected: bpy.props.IntProperty(name="Selected event")
    evt_block: bpy.props.EnumProperty(update=persist.on_change,
        name="Block", default="LOWER",
        items=(("LOWER", "LOWER", "the LOWEREVENTS block"),
               ("UPPER", "UPPER", "the UPPEREVENTS block")))
    evt_segment: bpy.props.EnumProperty(
        name="Segment", items=_evt_segment_items,
        description="The segment whose events are listed")
    evt_new_type: bpy.props.EnumProperty(
        name="Type", default="AEV_SOUND", items=EVT_TYPES,
        description="The event type (the engine's AEV_* switch cases)")
    evt_new_key: bpy.props.IntProperty(name="Key frame", default=0, min=0)
    evt_new_data: bpy.props.StringProperty(
        name="Data",
        description="Space-separated data fields — see the help line")
    saber_preset: bpy.props.EnumProperty(
        name="Preset", items=_saber_preset_items,
        description="Guard + one attack per saber style (openAnim from "
                    "saberanims.cfg, built-in sheet fallback)")
    results: bpy.props.CollectionProperty(type=JkaAnim_Result)


class JKA_PT_Main(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'JKA'
    bl_label = "JKA Anim Tools"

    def draw(self, context):
        p = context.scene.jka_anim
        # first-draw settings restore (persist.py safety net)
        persist.ensure_restored(context.scene)
        layout = self.layout

        box = layout.box()
        box.label(text="Base (set once — everything derives from it)",
                  icon='FILE_FOLDER')
        box.prop(p, "basepath", text="Base Path")
        box.prop(p, "character", text="Character")

        box = layout.box()
        box.label(text="Reference (matching)")
        box.prop(p, "ref_gla", text="Reference GLA")
        box.prop(p, "ref_mode", text="Mode")
        if p.ref_mode == "RANGE":
            row = box.row(align=True)
            row.prop(p, "ref_start", text="Start")
            row.prop(p, "ref_frames", text="Frames")
        _op(box, "jka_anim.load_reference", icon='IMPORT',
            text="Load reference GLA")
        box.label(text="the reference is a SEPARATE armature — scrub it "
                    "and pose the rig to match", icon='INFO')

        box = layout.box()
        box.label(text="Rig")
        _op(box, "jka_anim.prep_rig", icon='MODIFIER',
            text="Prep rig for export")
        box.label(text="strips IK constraints + the saved pose (in "
                    "memory); do this first — a freshly opened rig "
                    "displays collapsed until you do", icon='INFO')

        box = layout.box()
        box.label(text="Export GLA")
        if p.basepath and p.character:
            box.label(text=f"output: {p.basepath}/models/players/"
                          f"{p.character}/{p.character}.gla",
                     icon='FILE_TEXT')
        else:
            box.label(text="output derives from Base Path + Character",
                     icon='FILE_TEXT')
        box.prop(p, "exp_ref", text="Ref GLA (in-GLA path)")
        box.prop(p, "exp_custom_frames", text="Custom frame range")
        if p.exp_custom_frames:
            row = box.row(align=True)
            row.prop(p, "exp_frame_start", text="Start")
            row.prop(p, "exp_frame_end", text="End")
        _op(box, "jka_anim.export_gla", icon='EXPORT', text="Export GLA")

        # --- B2: the cfg editor ---
        box = layout.box()
        box.label(text="Segments (animation.cfg)")
        _op(box, "jka_anim.segments_load", icon='FILE_REFRESH',
            text="Load segments")
        if p.segments:
            box.prop(p, "seg_filter", text="Filter")
        for i in _matched_segments(p)[:SEG_ROW_CAP]:
            s = p.segments[i]
            icon = ("MODIFIER_OFF" if s.drift
                    else "ACTION" if s.has_action else "NONE")
            box.prop(p, "seg_selected",
                     text=f"{s.name}  {s.first_frame}..",
                     index=i, icon=icon)
        matched = len(_matched_segments(p))
        if p.segments and matched > SEG_ROW_CAP:
            box.label(text=f"… {matched - SEG_ROW_CAP} more match the "
                          "filter", icon='NONE')
        if p.segments:
            sel = p.segments[min(max(p.seg_selected, 0),
                                 len(p.segments) - 1)]
            row = box.row(align=True)
            row.label(text=f"loop {sel.loop_frames}   fps {sel.fps}")
            _op(row, "jka_anim.segment_jump", icon='BACK',
                text="Jump to segment")
            box.prop(p, "seg_jump_create", text="Create action/strip if missing")
            _op(box, "jka_anim.segment_apply", icon='CHECKMARK',
                text="Apply to action")
            if sel.drift:
                box.label(text="* action differs from the cfg", icon='ERROR')
            box.label(text="Add segment:")
            row = box.row(align=True)
            row.prop(p, "seg_new_name", text="Name")
            _op(row, "jka_anim.segment_add", icon='ADD', text="Add")
            row = box.row(align=True)
            row.prop(p, "seg_new_first", text="First frame")
            row.prop(p, "seg_new_num", text="Frames")
            row = box.row(align=True)
            row.prop(p, "seg_new_loop", text="Loop point")
            row.prop(p, "seg_new_fps", text="FPS")

        box = layout.box()
        box.label(text="Events (animevents.cfg)")
        box.prop(p, "evt_block", text="Block")
        box.prop(p, "evt_segment", text="Segment")
        _op(box, "jka_anim.events_load", icon='FILE_REFRESH',
            text="Load events")
        for i, e in enumerate(p.events):
            box.prop(p, "evt_selected",
                     text=f"#{e.key_frame} {e.etype.replace('AEV_', '')} "
                          f"{e.data}",
                     index=i)
        if p.events:
            _op(box, "jka_anim.event_remove", icon='X', text="Remove event")
        box.label(text="Add event:")
        row = box.row(align=True)
        row.prop(p, "evt_new_type", text="Type")
        row.prop(p, "evt_new_key", text="Key frame")
        box.prop(p, "evt_new_data", text="Data")
        box.label(text=anims.data_help(p.evt_new_type))
        _op(box, "jka_anim.event_add", icon='ADD', text="Add event")
        _op(box, "jka_anim.events_save", icon='FILE_TICK', text="Save events")

        box = layout.box()
        box.label(text="Saber (saberanims.cfg)")
        box.prop(p, "saber_cfg", text="Saber cfg (override)")
        _op(box, "jka_anim.saber_validate", icon='CHECKMARK',
            text="Validate saber cfg")
        box.prop(p, "saber_preset", text="Preset")
        _op(box, "jka_anim.saber_preset_apply", icon='PLAY',
            text="Apply saber preset")

        box = layout.box()
        box.label(text="Check (Base Path + Character)")
        _op(box, "jka_anim.check_run", icon='CHECKMARK', text="Run check")

        box = layout.box()
        box.label(text="Fingers (12 bones: d1/d2/d4 x j1/j2 per hand)")
        row = box.row(align=True)
        _op(row, "jka_anim.finger_preset", icon='BONE_DATA', text="Grasp",
            preset='GRASP')
        _op(row, "jka_anim.finger_preset", icon='BONE_DATA', text="Fist",
            preset='FIST')
        _op(row, "jka_anim.finger_preset", icon='BONE_DATA', text="Open",
            preset='OPEN')

        box = layout.box()
        box.label(text="Results")
        for r in p.results:
            box.label(text=r.text, icon="ERROR" if r.is_error else "NONE")

        box = layout.box()
        box.label(text="Dependencies (leave empty when installed in "
                      "Preferences)")
        box.prop(p, "addon_dir", text="Jedi Academy Add-on Dir")
        box.prop(p, "animkit_dir", text="AnimKit Dir (override)")


CLASSES = (
    JkaAnim_Segment,
    JkaAnim_Event,
    JkaAnim_Result,
    JkaAnim_PropGroup,
    JKA_PT_Main,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.jka_anim = bpy.props.PointerProperty(
        type=JkaAnim_PropGroup)
    persist.register()


def unregister():
    persist.unregister()
    del bpy.types.Scene.jka_anim
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
