#!/usr/bin/env python3
"""Blender register smoke for the SHIPPED jka-anim-tools zip (B4 packaging
gate, 2026-11-20 layout).

Loads jka_anim_tools from a clean extracted zip (NOT the dev clone),
registers it, verifies the JKA_OT_*/JKA_PT_* classes are registered, and
unregisters. The zip ships NO jediacademy (the GPL dep installs
separately — review item #1) and the smoke proves:

  * registration works with jediacademy ABSENT (operators only need it
    at call time),
  * animkit resolves to the COPY BUNDLED inside the add-on
    (jka_anim_tools/lib/animkit) with no env var / field set
    (review item #2),
  * the one-base-path scene properties exist (review item #4).
"""
import glob
import os
import shutil
import sys
import tempfile
import zipfile

import bpy

# zip path: first arg AFTER the '--' separator, else the newest
# dist/jka-anim-tools-*.zip (Blender puts its own CLI args in sys.argv
# before the '--', so argv[1] is NOT the user's argument)
ZIP = None
if "--" in sys.argv:
    _after = sys.argv[sys.argv.index("--") + 1:]
    if _after:
        ZIP = os.path.expanduser(_after[0])
if ZIP is None:
    _cands = sorted(glob.glob(os.path.expanduser(
        "~/work/jka-animator/dist/jka-anim-tools-*.zip")))
    if not _cands:
        print("REGISTER SMOKE: FAIL (no dist/jka-anim-tools-*.zip found)")
        sys.exit(1)
    ZIP = _cands[-1]
print("smoke zip:", ZIP)
base = tempfile.mkdtemp(prefix="b4_test_")
shipped = os.path.join(base, "shipped")
os.makedirs(shipped)
with zipfile.ZipFile(ZIP) as z:
    z.extractall(shipped)

# the dev clone must not leak in: scrub the path + the cached modules
for p in list(sys.path):
    if "jka-animator" in p or p.endswith("jka-animkit"):
        sys.path.remove(p)
for k in list(os.environ):
    if k == "JKA_ANIMKIT_DIR":
        del os.environ[k]
for n in [k for k in list(sys.modules)
          if k == "animkit" or k.startswith("animkit.")
          or k == "jka_anim_tools" or k.startswith("jka_anim_tools.")]:
    del sys.modules[n]
sys.path.insert(0, shipped)

import jka_anim_tools
assert "b4_test" in jka_anim_tools.__file__, \
    f"WRONG addon loaded: {jka_anim_tools.__file__}"
print("loaded shipped addon from:", jka_anim_tools.__file__)

jka_anim_tools.register()
expected_ops = [
    "jka_anim.load_reference", "jka_anim.prep_rig", "jka_anim.export_gla",
    "jka_anim.segments_load", "jka_anim.segment_jump",
    "jka_anim.segment_apply", "jka_anim.segment_add",
    "jka_anim.events_load", "jka_anim.event_add",
    "jka_anim.event_remove", "jka_anim.events_save",
    "jka_anim.saber_validate", "jka_anim.saber_preset_apply",
    "jka_anim.check_run", "jka_anim.finger_preset",
]
missing = []
for idn in expected_ops:
    sub, name = idn.split(".")
    if not hasattr(bpy.ops.jka_anim, name):
        missing.append(idn)
panel_ok = getattr(bpy.types, "JKA_PT_Main", None) is not None

# the bundled animkit must resolve with no env var / field
from jka_anim_tools import animkit_bridge  # noqa: E402
ak = animkit_bridge.get_animkit("")
ak_file = os.path.abspath(ak.__file__ or "")
bundled_ok = ("jka_anim_tools" + os.sep + "lib" + os.sep) in ak_file
print("animkit resolved from:", ak_file)
print("bundled animkit:", "ok" if bundled_ok else "WRONG (not the bundled copy)")

# the one-base-path properties (review item #4)
p = bpy.context.scene.jka_anim
props_ok = all(hasattr(p, k) for k in (
    "basepath", "character", "ref_gla", "seg_filter", "results"))
gone_ok = not any(hasattr(p, k) for k in (
    "ref_basepath", "exp_basepath", "cfg_basepath", "cfg_character",
    "exp_filepath", "exp_glapath"))
print("one-base-path props:", "ok" if props_ok else "MISSING",
      "| old multi-path props removed:", "ok" if gone_ok else "STILL PRESENT")

ok = not missing and panel_ok and bundled_ok and props_ok and gone_ok
jka_anim_tools.unregister()
print("UNREGISTER OK")
print("REGISTER SMOKE:", "PASS" if ok else "FAIL")
if missing:
    print("   missing ops:", missing)
shutil.rmtree(base, ignore_errors=True)
sys.exit(0 if ok else 1)
