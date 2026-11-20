# SPDX-License-Identifier: MIT
"""The Blender Operators: one button per verified flow step.

Each operator is a thin delegate to the core module of the same job —
the headless blender/ scripts call the SAME functions, so interactive and
automation can never drift.

The operators read the ONE base path + character from the scene
(review item #4): the reference GLA and the export output are derived
(paths.derive_*), never re-entered.
"""
import bpy

from . import refimport, rigprep, exportop, paths
from .cfgops import _sync_results
from .common import JkaError


class JKA_OT_LoadReference(bpy.types.Operator):
    """Import a reference .gla as the 'reference_humanoid' overlay
    (safe around the skeleton_root name trap); scrub it and pose the
    rig to match"""
    bl_idname = "jka_anim.load_reference"
    bl_label = "Load reference GLA"
    bl_description = ("Import a reference .gla into this scene as "
                     "'reference_humanoid' (rename-dance safe)")

    def execute(self, context):
        p = context.scene.jka_anim
        notes = []
        try:
            # one base path: when the user typed a reference GLA file
            # path and left the base path empty, the base path is the
            # folder a few steps up that contains models/players
            # (review item #4: "if not it can throw an error")
            if not p.basepath and p.ref_gla:
                derived = paths.derive_basepath_from_file(p.ref_gla)
                if not derived:
                    raise JkaError(
                        "could not find the mod folder (the one that "
                        f"contains models/players) at or above "
                        f"{p.ref_gla!r} — set the Base Path at the top "
                        "of the panel")
                p.basepath = derived
                notes.append(f"derived Base Path: {derived}")
            gla = paths.derive_ref_gla(p.basepath, p.character, p.ref_gla)
            ref = refimport.load_reference(
                gla=gla, basepath=p.basepath,
                mode=p.ref_mode.lower(), start=p.ref_start,
                frames=p.ref_frames, addon_dir=p.addon_dir)
            notes += self._make_reference_visible(context, ref)
            _sync_results(p, [(n, False) for n in notes])
            self.report({'INFO'}, notes[-1] if notes else "reference loaded")
            return {'FINISHED'}
        except JkaError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

    @staticmethod
    def _make_reference_visible(context, ref):
        """Point the Dope Sheet at the imported animation (review item #6:
        "nothing is keyframed" — the keys ARE there, on the reference
        armature; make sure the editor shows that armature + action).

        Sets the reference's data_action (RANGE mode: the importer's
        action; CFG mode: the first strip's action, since the importer
        clears data.action after building the NLA), selects + activates
        it, and reports what was imported.
        """
        notes = [f"reference imported: '{ref.name}' "
                 f"({len(ref.data.bones)} bones)"]
        ad = ref.animation_data
        action = ad.action if ad else None
        if action is None and ad is not None:
            for track in ad.nla_tracks:
                for strip in track.strips:
                    action = strip.action
                    break
                if action is not None:
                    break
        if ad is not None and action is not None:
            ad.action = action
            n_fc = len(getattr(action, "fcurves", ()) or ())
            sc = context.scene
            notes.append(
                f"action '{action.name}': {n_fc} fcurves, frames "
                f"{sc.frame_start}..{sc.frame_end} — it is now the "
                "ACTIVE object, so the Dope Sheet follows it")
        else:
            notes.append("no animation imported (Mode: None?)")
        try:
            ref.select_set(True)
            context.view_layer.objects.active = ref
        except RuntimeError as e:
            notes.append(f"note: could not activate the reference: {e}")
        return notes


class JKA_OT_PrepRig(bpy.types.Operator):
    """Strip IK constraints + stored pose offsets from the rig's
    skeleton_root mirror (in memory only; the .blend is never saved)"""
    bl_idname = "jka_anim.prep_rig"
    bl_label = "Prep rig for export"
    bl_description = ("Strip IK constraints and zero the stored pose "
                     "offsets on skeleton_root (in memory only)")

    def execute(self, context):
        p = context.scene.jka_anim
        try:
            n = rigprep.strip_rig()
        except JkaError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        _sync_results(p, [(f"Prepped rig ({n} constraints stripped — "
                           "in memory only, the .blend was not saved)",
                           False)])
        self.report({'INFO'}, f"Prepped rig ({n} constraints stripped)")
        return {'FINISHED'}


class JKA_OT_ExportGla(bpy.types.Operator):
    """Export skeleton_root to .gla via the installed jediacademy addon
    (restores the legacy g2 scale; validate afterwards with animkit)"""
    bl_idname = "jka_anim.export_gla"
    bl_label = "Export GLA"
    bl_description = ("Export the scene to .gla via the jediacademy "
                     "addon; restore legacy g2 scale; run the animkit "
                     "gate after")

    def execute(self, context):
        p = context.scene.jka_anim
        try:
            # the output is DERIVED from the one base path + character
            # (review item #4): <base>/models/players/<char>/<char>.gla
            out, base, glapath, ref_gla = paths.derive_export_paths(
                p.basepath, p.character, glapath="", ref=p.exp_ref)
            fs = p.exp_frame_start if p.exp_custom_frames else None
            fe = p.exp_frame_end if p.exp_custom_frames else None
            exportop.export_gla(
                out=out, basepath=base,
                glapath=glapath, ref=ref_gla,
                frame_start=fs, frame_end=fe, addon_dir=p.addon_dir)
            _sync_results(p, [(f"exported {out} ({glapath}) — run the "
                               "check before in-engine use", False)])
            self.report({'INFO'}, f"exported {out}")
            return {'FINISHED'}
        except JkaError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

    def invoke(self, context, event):
        return self.execute(context)


CLASSES = (
    JKA_OT_LoadReference,
    JKA_OT_PrepRig,
    JKA_OT_ExportGla,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
