# SPDX-License-Identifier: MIT
"""N-panel UI + the scene properties the operators read.

Properties live on bpy.types.Scene so they persist while the file is open
and survive operator invocations; the headless scripts use the same
values via the CLI.

Sections
--------
B1:  Reference (matching) / Rig / Export GLA
B2:  Segments (animation.cfg) / Events (animevents.cfg) /
     Saber (saberanims.cfg) — driven by the cfgops.py operators over the
     shared animkit cfg layer (decision #12).
B3:  Check (animkit-check over the character/skeleton dir) /
     Fingers (grasp / fist / open presets) / Results.
"""
import bpy

from . import animkit_bridge, anims

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
    ("ALL", "All", "every frame in one action (slow)"),
    ("NONE", "None", "geometry only, no animation"),
)

# The editable event types (NPC_stats.cpp switch cases) and the per-type
# data-field help the panel shows under the Data field.
EVT_TYPES = tuple(
    (t, t.replace("AEV_", ""), anims.data_help(t))
    for t in anims.EDITABLE_ETYPES
)


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
    if not p.cfg_basepath:
        return [("", "(set the cfg base path)", "")]
    try:
        ak = animkit_bridge.get_animkit(p.animkit_dir)
        presets = anims.saber_presets(ak, p.cfg_basepath, p.saber_cfg)
        return [(str(i), pr.label, "") for i, pr in enumerate(presets)]
    except Exception:
        return [("", "(animkit unavailable)", "")]


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
    # --- reference (matching) ---
    ref_gla: bpy.props.StringProperty(
        name="Reference GLA", subtype=FILE_ANY,
        description="Reference .gla to import for matching (absolute path)")
    ref_basepath: bpy.props.StringProperty(
        name="Base Path", subtype=FILE_DIR,
        description="Mod folder containing models/... (cfg mode resolves the .cfg against it)")
    ref_mode: bpy.props.EnumProperty(
        name="Import mode", items=MODES, default="RANGE")
    ref_start: bpy.props.IntProperty(
        name="Start frame", default=0, min=0,
        description="Range mode: first frame")
    ref_frames: bpy.props.IntProperty(
        name="Frames", default=240, min=1,
        description="Range mode: frame count")
    # --- export ---
    exp_basepath: bpy.props.StringProperty(
        name="Base Path", subtype=FILE_DIR,
        description="Your mod folder (the folder that contains models/...)")
    exp_filepath: bpy.props.StringProperty(
        name="Output File", subtype=FILE_ANY,
        description="Output .gla — absolute path, INSIDE the Base Path")
    exp_glapath: bpy.props.StringProperty(
        name="GLA Path",
        description="Base-relative in-GLA path, e.g. models/players/mychar/mychar.gla")
    exp_ref: bpy.props.StringProperty(
        name="Reference", default="models/players/_humanoid/_humanoid.gla",
        description="Base-relative reference GLA — copies bone indices")
    exp_custom_frames: bpy.props.BoolProperty(
        name="Custom frame range", default=False,
        description="Off: use the scene's current frame range")
    exp_frame_start: bpy.props.IntProperty(
        name="Frame Start", default=0, min=0)
    exp_frame_end: bpy.props.IntProperty(
        name="Frame End", default=239, min=0)
    # --- addon bridge ---
    addon_dir: bpy.props.StringProperty(
        name="Add-on Dir", subtype=FILE_DIR,
        description="Only needed if jediacademy is not installed: the "
                    "directory that CONTAINS the 'jediacademy' package folder")
    # --- B2: cfg editor (segments / events / saber) ---
    animkit_dir: bpy.props.StringProperty(
        name="AnimKit Dir", subtype=FILE_DIR,
        description="The directory that CONTAINS the 'animkit' package "
                    "(the JKA cfg/GLA format library); empty = $JKA_ANIMKIT_DIR "
                    "or the dev clone")
    cfg_basepath: bpy.props.StringProperty(
        name="Cfg Base Path", subtype=FILE_DIR,
        description="Mod folder containing models/players/<character>/...")
    cfg_character: bpy.props.StringProperty(
        name="Character",
        description="Character folder under models/players, e.g. assassin_droid")
    saber_cfg: bpy.props.StringProperty(
        name="Saber cfg (override)", subtype=FILE_ANY,
        description="Explicit saberanims.cfg path; empty = "
                    "<base>/ext_data/saberanims.cfg")
    segments: bpy.props.CollectionProperty(type=JkaAnim_Segment)
    seg_selected: bpy.props.IntProperty(name="Selected segment")
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
    evt_block: bpy.props.EnumProperty(
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
        layout = self.layout

        box = layout.box()
        box.label(text="Reference (matching)")
        row = box.row(align=True)
        row.prop(p, "ref_gla", text="")
        row.prop(p, "ref_mode", text="")
        box.prop(p, "ref_basepath", text="")
        if p.ref_mode == "RANGE":
            row = box.row(align=True)
            row.prop(p, "ref_start")
            row.prop(p, "ref_frames")
        box.operator("jka_anim.load_reference", icon='IMPORT')

        box = layout.box()
        box.label(text="Rig")
        box.operator("jka_anim.prep_rig", icon='MODIFIER')

        box = layout.box()
        box.label(text="Export GLA")
        box.prop(p, "exp_basepath", text="")
        box.prop(p, "exp_filepath", text="")
        box.prop(p, "exp_glapath", text="")
        box.prop(p, "exp_ref", text="")
        box.prop(p, "exp_custom_frames")
        if p.exp_custom_frames:
            row = box.row(align=True)
            row.prop(p, "exp_frame_start")
            row.prop(p, "exp_frame_end")
        box.operator("jka_anim.export_gla", icon='EXPORT')

        # --- B2: the cfg editor ---
        box = layout.box()
        box.label(text="Segments (animation.cfg)")
        box.prop(p, "cfg_basepath", text="")
        box.prop(p, "cfg_character", text="")
        box.prop(p, "animkit_dir", text="")
        box.operator("jka_anim.segments_load", icon='FILE_REFRESH')
        for i, s in enumerate(p.segments):
            icon = ("MODIFIER_OFF" if s.drift
                    else "ACTION" if s.has_action else "NONE")
            box.prop(p, "seg_selected",
                     text=f"{s.name}  {s.first_frame}.."
                          f"{s.first_frame + s.num_frames - 1}",
                     index=i, icon=icon)
        if p.segments:
            sel = p.segments[min(max(p.seg_selected, 0),
                                 len(p.segments) - 1)]
            row = box.row(align=True)
            row.label(text=f"loop {sel.loop_frames}   fps {sel.fps}")
            row.operator("jka_anim.segment_jump", icon='BACK')
            box.prop(p, "seg_jump_create")
            box.operator("jka_anim.segment_apply", icon='CHECKMARK')
            if sel.drift:
                box.label(text="* action differs from the cfg", icon='ERROR')
            box.label(text="Add segment:")
            row = box.row(align=True)
            row.prop(p, "seg_new_name", text="")
            row.operator("jka_anim.segment_add", icon='ADD')
            row = box.row(align=True)
            row.prop(p, "seg_new_first")
            row.prop(p, "seg_new_num")
            row = box.row(align=True)
            row.prop(p, "seg_new_loop")
            row.prop(p, "seg_new_fps")

        box = layout.box()
        box.label(text="Events (animevents.cfg)")
        row = box.row(align=True)
        row.prop(p, "evt_block", text="")
        box.prop(p, "evt_segment", text="")
        box.operator("jka_anim.events_load", icon='FILE_REFRESH')
        for i, e in enumerate(p.events):
            box.prop(p, "evt_selected",
                     text=f"#{e.key_frame} {e.etype.replace('AEV_', '')} "
                          f"{e.data}",
                     index=i)
        if p.events:
            box.operator("jka_anim.event_remove", icon='X')
        box.label(text="Add event:")
        row = box.row(align=True)
        row.prop(p, "evt_new_type", text="")
        row.prop(p, "evt_new_key")
        box.prop(p, "evt_new_data", text="")
        box.label(text=anims.data_help(p.evt_new_type))
        box.operator("jka_anim.event_add", icon='ADD')
        box.operator("jka_anim.events_save", icon='FILE_TICK')

        box = layout.box()
        box.label(text="Saber (saberanims.cfg)")
        box.prop(p, "saber_cfg", text="")
        box.operator("jka_anim.saber_validate", icon='CHECKMARK')
        box.prop(p, "saber_preset", text="")
        box.operator("jka_anim.saber_preset_apply", icon='PLAY')

        box = layout.box()
        box.label(text="Check (Segments base path + character)")
        box.operator("jka_anim.check_run", icon='CHECKMARK')

        box = layout.box()
        box.label(text="Fingers (12 bones: d1/d2/d4 x j1/j2 per hand)")
        row = box.row(align=True)
        row.operator("jka_anim.finger_preset", text="Grasp", icon='BONE',
                     preset='GRASP')
        row.operator("jka_anim.finger_preset", text="Fist", icon='BONE',
                     preset='FIST')
        row.operator("jka_anim.finger_preset", text="Open", icon='BONE',
                     preset='OPEN')

        box = layout.box()
        box.label(text="Results")
        for r in p.results:
            box.label(text=r.text, icon="ERROR" if r.is_error else "NONE")

        if p.addon_dir:
            layout.prop(p, "addon_dir")


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


def unregister():
    del bpy.types.Scene.jka_anim
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
