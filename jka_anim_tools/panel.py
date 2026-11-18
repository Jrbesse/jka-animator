# SPDX-License-Identifier: MIT
"""N-panel UI + the scene properties the operators read.

Properties live on bpy.types.Scene so they persist while the file is open
and survive operator invocations; the headless scripts use the same
values via the CLI.
"""
import bpy

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

        if p.addon_dir:
            layout.prop(p, "addon_dir")


CLASSES = (
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
