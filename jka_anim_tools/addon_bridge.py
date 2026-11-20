# SPDX-License-Identifier: MIT
"""Registration bridge for the jediacademy (mrwonko/cagelight) addon.

GPL dependency: installed and run as a separate addon — this module only
adds its directory to sys.path and calls its own register(), it never
imports or copies its code (decisions #1/#9).
"""
import sys

from .common import JkaError


def ensure_addon(addon_dir, op):
    """Register the jediacademy addon (idempotent) so ``op`` becomes
    available on bpy.ops.

    ``addon_dir`` is the directory that CONTAINS the ``jediacademy``
    package folder (the unzipped zip's top level). Raises JkaError when it
    is missing or the addon fails to load.
    """
    if not addon_dir:
        raise JkaError(
            f"the jediacademy addon's {op!r} operator is not available in "
            "this Blender. jediacademy is a SEPARATE add-on (it is not "
            "bundled with JKA Anim Tools): install it once from its own "
            "repository (https://github.com/mrwonko/Blender-Jedi-Academy-"
            "Tools, tag v2.1.0) via Edit > Preferences > Add-ons > "
            "Install from Disk, then enable it — or set the 'Add-on dir' "
            "field in the JKA N-panel (CLI: --addon-dir) to the directory "
            "that CONTAINS the 'jediacademy' package folder.")
    if addon_dir not in sys.path:
        sys.path.insert(0, addon_dir)
    try:
        import jediacademy
        jediacademy.register()
    except Exception as e:
        raise JkaError(f"failed to load the jediacademy addon from {addon_dir}: {e}")
