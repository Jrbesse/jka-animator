# SPDX-License-Identifier: MIT
"""The Blender Operators: one button per verified flow step.

Each operator is a thin delegate to the core module of the same job —
the headless blender/ scripts call the SAME functions, so interactive and
automation can never drift.
"""
import bpy

from . import refimport, rigprep, exportop
from .common import JkaError


class JkaAnim_OT_LoadReference(bpy.types.Operator):
    """Import a reference .gla as the 'reference_humanoid' overlay
    (safe around the skeleton_root name trap); scrub it and pose the
    rig to match"""
    bl_idname = "jka_anim.load_reference"
    bl_label = "Load reference GLA"
    bl_description = ("Import a reference .gla into this scene as "
                     "'reference_humanoid' (rename-dance safe)")

    def execute(self, context):
        p = context.scene.jka_anim
        try:
            refimport.load_reference(
                gla=p.ref_gla, basepath=p.ref_basepath,
                mode=p.ref_mode.lower(), start=p.ref_start,
                frames=p.ref_frames, addon_dir=p.addon_dir)
        except JkaError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        return {'FINISHED'}


class JkaAnim_OT_PrepRig(bpy.types.Operator):
    """Strip IK constraints + stored pose offsets from the rig's
    skeleton_root mirror (in memory only; the .blend is never saved)"""
    bl_idname = "jka_anim.prep_rig"
    bl_label = "Prep rig for export"
    bl_description = ("Strip IK constraints and zero the stored pose "
                     "offsets on skeleton_root (in memory only)")

    def execute(self, context):
        try:
            n = rigprep.strip_rig()
        except JkaError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        self.report({'INFO'}, f"Prepped rig ({n} constraints stripped)")
        return {'FINISHED'}


class JkaAnim_OT_ExportGla(bpy.types.Operator):
    """Export skeleton_root to .gla via the installed jediacademy addon
    (restores the legacy g2 scale; validate afterwards with animkit)"""
    bl_idname = "jka_anim.export_gla"
    bl_label = "Export GLA"
    bl_description = ("Export the scene to .gla via the jediacademy addon; "
                     "restore legacy g2 scale; run the animkit gate after")

    def execute(self, context):
        p = context.scene.jka_anim
        if not p.exp_filepath:
            self.report({'ERROR'},
                        "set the Output file first (inside the Base path)")
            return {'CANCELLED'}
        fs = p.exp_frame_start if p.exp_custom_frames else None
        fe = p.exp_frame_end if p.exp_custom_frames else None
        try:
            exportop.export_gla(
                out=p.exp_filepath, basepath=p.exp_basepath,
                glapath=p.exp_glapath, ref=p.exp_ref,
                frame_start=fs, frame_end=fe, addon_dir=p.addon_dir)
        except JkaError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        return {'FINISHED'}

    def invoke(self, context, event):
        return self.execute(context)


CLASSES = (
    JkaAnim_OT_LoadReference,
    JkaAnim_OT_PrepRig,
    JkaAnim_OT_ExportGla,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
