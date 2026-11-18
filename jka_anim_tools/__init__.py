# SPDX-License-Identifier: MIT
"""jka_anim_tools — JKA Ghoul2 animation suite (Blender-native).

Suite v1 (B1): authoring operators over the installed mrwonko/cagelight
"Jedi Academy Import/Export Tools" addon (GPL — we call its operators, we
never port its code, decision #9) plus the shared core that the headless
``blender/`` CLI scripts wrap. One source of logic for both faces.

Modules
-------
common        names, modes, JkaError          (bpy-free)
paths         export path shaping/validation  (bpy-free)
addon_bridge  jediacademy addon registration  (bpy)
rigprep       mirror-armature prep (strip, legacy scale)  (bpy)
refimport     reference GLA import (skeleton_root name trap)  (bpy)
exportop      GLA export orchestration        (bpy)
operators     the Blender Operators           (bpy)
panel         N-panel UI + scene properties   (bpy)
"""

bl_info = {
    "name": "JKA Anim Tools",
    "author": "Jrbesse",
    "version": (0, 1, 0),
    "blender": (4, 1, 0),
    "location": "View3D > Sidebar (N) > JKA",
    "description": "JKA Ghoul2 animation suite: reference matching, rig prep "
                   "and GLA export over the installed jediacademy addon",
    "category": "Import-Export",
}


def register():
    import bpy
    from . import operators, panel
    panel.register()
    operators.register()


def unregister():
    import bpy
    from . import operators, panel
    operators.unregister()
    panel.unregister()
