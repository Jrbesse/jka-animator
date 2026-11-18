"""prepare_rig.py — CLI wrapper over jka_anim_tools (headless automation face).

Prep a JustJordyn-style IK rig for GLA export (optionally export). The
logic lives ONCE in the ``jka_anim_tools`` package (the Blender addon);
this file only parses CLI args and maps failures to exit codes, so the
headless flow and the N-panel operators can never drift. Rig-prep
rationale + caveat C2: see ``jka_anim_tools/rigprep.py`` / ``exportop.py``.

Usage
-----
Headless (prep + export):

  blender --background rig.blend --python blender/prepare_rig.py -- \
      --export out.gla \
      --basepath /path/to/modfolder \
      --glapath models/players/mychar/mychar.gla \
      --ref     models/players/_humanoid/_humanoid.gla \
      --frame-start 0 --frame-end 239

Headless (prep only, then export manually or via another script):

  blender --background rig.blend --python blender/prepare_rig.py

Notes
-----
* ``--ref`` (the addon's "gla reference") is BASEPATH-RELATIVE, not absolute.
* ``--export out.gla`` must resolve to a path INSIDE ``--basepath`` (the
  addon derives the relative name from it; ``--glapath`` overrides the
  derived name).
* If the addon is not installed, pass --addon-dir pointing at the
  directory that CONTAINS the ``jediacademy`` package folder (i.e. the
  unzipped zip's top level).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jka_anim_tools import rigprep, exportop  # noqa: E402
from jka_anim_tools.common import JkaError  # noqa: E402


def _arg(args, name, default=None):
    if name in args:
        i = args.index(name)
        if i + 1 < len(args):
            return args[i + 1]
    return default


def _opt_int(args, name):
    v = _arg(args, name, "")
    return int(v) if v != "" else None


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    try:
        rigprep.strip_rig()
        if "--export" in args:
            exportop.export_gla(
                out=_arg(args, "--export"),
                basepath=_arg(args, "--basepath", "") or "",
                glapath=_arg(args, "--glapath", "") or "",
                ref=_arg(args, "--ref", "") or "",
                frame_start=_opt_int(args, "--frame-start"),
                frame_end=_opt_int(args, "--frame-end"),
                addon_dir=_arg(args, "--addon-dir"),
            )
        else:
            print("prepare_rig: scene ready — export via the addon's "
                  "'Export JA Ghoul 2 Skeleton & Animation' operator "
                  "(or rerun with --export ...).")
    except JkaError as e:
        raise SystemExit(f"prepare_rig: {e}")
    except SystemExit:
        raise
    except Exception as e:
        raise SystemExit(f"prepare_rig: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
