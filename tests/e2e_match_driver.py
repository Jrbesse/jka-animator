# SPDX-License-Identifier: MIT
"""B1 headless E2E regression driver (ONE Blender process).

Simulates one session of load_reference + prepare_rig — the Text Editor
equivalent, since two ``--python`` blocks do not chain on the Blender CLI
— and exports a GLA. Run on a pristine (unsaved-changes) rig .blend:

  blender --background RIG.blend --python tests/e2e_match_driver.py -- \
      --base /staging/mod-folder --out /staging/mod-folder/b1_e2e.gla \
      --addon-dir /path/containing/jediacademy-package

The ``--base`` folder must stage ``models/players/_humanoid/_humanoid.gla``
(the reference). Env fallbacks: ``JKA_E2E_BASE``, ``JKA_E2E_ADDON_DIR``.

Gate (B1 exit criterion): the exported GLA must be BYTE-IDENTICAL to the
pre-refactor script-flow baseline — sha256
``6b0e2cecc28af4f703b268a2e095dd31897386c4452672a859d521b941326cd0``
(Blender 5.3.0, the doc_9f2fca7e JustJordyn rig, gabase staging,
frame 0..239). The plain (non-matched) flow must produce the same bytes:
run ``blender/prepare_rig.py`` with the identical export args.
"""
import os
import runpy
import sys


def _arg(args, name, default):
    if name in args:
        i = args.index(name)
        if i + 1 < len(args):
            return args[i + 1]
    return default


args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
HERE = os.path.dirname(os.path.abspath(__file__))
BL = os.path.join(os.path.dirname(HERE), "blender")
G = _arg(args, "--base", os.environ.get("JKA_E2E_BASE", ""))
ADDON = _arg(args, "--addon-dir", os.environ.get("JKA_E2E_ADDON_DIR", ""))
OUT = _arg(args, "--out", "")
if not (G and OUT):
    raise SystemExit("e2e_match_driver: pass --base <staging mod folder> "
                     "--out <abs path inside it> "
                     "(or set JKA_E2E_BASE / JKA_E2E_ADDON_DIR)")

sys.argv = ["blender", "--",
            "--gla", G + "/models/players/_humanoid/_humanoid.gla",
            "--basepath", G, "--mode", "range", "--start", "0", "--frames", "240",
            "--addon-dir", ADDON]
runpy.run_path(os.path.join(BL, "load_reference.py"), run_name="__main__")

sys.argv = ["blender", "--",
            "--export", OUT, "--basepath", G,
            "--glapath", "models/players/humanoid/humanoid.gla",
            "--ref", "models/players/_humanoid/_humanoid.gla",
            "--frame-start", "0", "--frame-end", "239",
            "--addon-dir", ADDON]
runpy.run_path(os.path.join(BL, "prepare_rig.py"), run_name="__main__")
