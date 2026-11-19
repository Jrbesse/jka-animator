#!/usr/bin/env python3
"""Blender register smoke for the SHIPPED jka-anim-suite zip (B4 packaging gate).

Loads jka_anim_tools from a clean extracted zip (NOT the dev clone), registers
it, verifies the JKA_OT_*/JKA_PT_* classes are registered, and unregisters.
"""
import os
import sys
import bpy

base = os.path.expanduser("~/work/b4_test")
addons = os.path.join(base, "addons")
lib = os.path.join(base, "lib")

# Point ONLY at the shipped components
for p in list(sys.path):
    if "jka-animator" in p or p.endswith("jka-animkit"):
        sys.path.remove(p)
sys.path.insert(0, addons)
os.environ["JKA_ANIMKIT_DIR"] = lib
for n in [k for k in list(sys.modules) if k == "animkit" or k.startswith("animkit.")]:
    del sys.modules[n]
# the jediacademy dep (the shipped one)
sys.path.insert(0, addons)

import jka_anim_tools
assert "b4_test" in jka_anim_tools.__file__, f"WRONG addon loaded: {jka_anim_tools.__file__}"
print("loaded shipped addon from:", jka_anim_tools.__file__)

jka_anim_tools.register()
# verify the operators are actually registered + callable (dir(bpy.types)
# doesn't enumerate dynamically-registered op classes reliably)
expected_ops = [
    "jka_anim.load_reference", "jka_anim.prep_rig", "jka_anim.export_gla",
    "jka_anim.segments_load", "jka_anim.segment_jump", "jka_anim.segment_apply",
    "jka_anim.segment_add", "jka_anim.events_load", "jka_anim.event_add",
    "jka_anim.event_remove", "jka_anim.events_save", "jka_anim.saber_validate",
    "jka_anim.saber_preset_apply", "jka_anim.check_run", "jka_anim.finger_preset",
]
missing = []
for idn in expected_ops:
    sub, name = idn.split(".")
    if not hasattr(bpy.ops.jka_anim, name):
        missing.append(idn)
panel_ok = getattr(bpy.types, "JKA_PT_Main", None) is not None
print(f"REGISTER OK: {len(expected_ops) - len(missing)}/{len(expected_ops)} operators, panel={'ok' if panel_ok else 'MISSING'}")
if missing:
    print("   missing:", missing)
jka_anim_tools.unregister()
print("UNREGISTER OK")
print("REGISTER SMOKE:", "PASS" if (not missing and panel_ok) else "FAIL")
