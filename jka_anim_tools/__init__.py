# SPDX-License-Identifier: MIT
"""jka_anim_tools — JKA Ghoul2 animation suite (Blender-native).

Suite v1 (B1): authoring operators over the installed mrwonko/cagelight
"Jedi Academy Import/Export Tools" addon (GPL — we call its operators, we
never port its code, decision #9) plus the shared core that the headless
``blender/`` CLI scripts wrap. One source of logic for both faces.

B2 adds the cfg editor: segments / events / saber panel sections over the
shared animkit cfg layer (decision #12) — operators in ``cfgops``, NLA
glue in ``nla``, bpy-free core in ``anims``.

Modules
-------
common        names, modes, JkaError          (bpy-free)
paths         export path shaping/validation  (bpy-free)
animkit_bridge animkit runtime loader         (bpy-free)
anims         cfg authoring core              (bpy-free)
addon_bridge  jediacademy addon registration  (bpy)
rigprep       mirror-armature prep (strip, legacy scale)  (bpy)
refimport     reference GLA import (skeleton_root name trap)  (bpy)
exportop      GLA export orchestration        (bpy)
nla           armature / NLA track / strip glue  (bpy)
operators     the Blender Operators (B1)      (bpy)
cfgops        the cfg editor Operators (B2)   (bpy)
checkop       animkit-check core (B3)         (bpy-free)
fingers       finger preset tables + grasp slerp (B3) (bpy-free)
fingerops     the finger preset Operators (B3) (bpy)
panel         N-panel UI + scene properties   (bpy)
"""

bl_info = {
    "name": "JKA Anim Tools",
    "author": "Jrbesse",
    "version": (0, 2, 4),
    "blender": (4, 1, 0),
    "location": "View3D > Sidebar (N) > JKA",
    "description": "JKA Ghoul2 animation suite: reference matching, rig prep, "
                   "GLA export and named-animation import over the "
                   "separately-installed jediacademy addon; cfg editor "
                   "(segments/events/saber) + timeline labels over bundled "
                   "animkit",
    "category": "Import-Export",
}


def register():
    import bpy
    from . import fingerops, operators, cfgops, panel
    panel.register()
    operators.register()
    cfgops.register()
    fingerops.register()


def unregister():
    import bpy
    from . import fingerops, operators, cfgops, panel
    fingerops.unregister()
    cfgops.unregister()
    operators.unregister()
    panel.unregister()
