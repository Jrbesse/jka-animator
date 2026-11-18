"""load_reference.py — CLI wrapper over jka_anim_tools (headless automation
face).

Import a reference .gla into the rig scene as an overlay: the rig's mirror
armature + an animated reference armature coexist in one scene, so you can
scrub the reference and pose the rig to match. The logic lives ONCE in the
``jka_anim_tools`` package; this file only parses CLI args and maps
failures to exit codes. The skeleton_root name-trap rationale: see
``jka_anim_tools/refimport.py``.

Usage (headless, run on the rig file):

  blender --background rig.blend --python blender/load_reference.py -- \
      --gla /abs/path/to/ref.gla --basepath /abs/path/to/modfolder \
      --mode range --start 0 --frames 240

  --mode cfg  : per-sequence NLA strips (needs animation.cfg next to the
                GLA, resolved against --basepath in base-relative form;
                slow for 26K-frame skeletons)
  --mode all  : every frame in one action (slow)
  --mode range: startFrame..startFrame+frames-1 in one action (fast)

Exporting later in the same session: prepare_rig.py detects rig_armature
and renames it back to skeleton_root automatically.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jka_anim_tools import refimport  # noqa: E402
from jka_anim_tools.common import JkaError  # noqa: E402


def _arg(args, name, default=None):
    if name in args:
        i = args.index(name)
        if i + 1 < len(args):
            return args[i + 1]
    return default


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    try:
        refimport.load_reference(
            gla=_arg(args, "--gla"),
            basepath=_arg(args, "--basepath", "") or "",
            mode=(_arg(args, "--mode", "range") or "range").lower(),
            start=int(_arg(args, "--start", "0") or "0"),
            frames=int(_arg(args, "--frames", "240") or "240"),
            addon_dir=_arg(args, "--addon-dir"),
        )
        print("load_reference: ready. Scrub the timeline — "
              "reference_humanoid animates, rig_armature is yours to pose. "
              "Export with prepare_rig.py (it renames rig_armature back).")
    except JkaError as e:
        raise SystemExit(f"load_reference: {e}")
    except SystemExit:
        raise
    except Exception as e:
        raise SystemExit(f"load_reference: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
